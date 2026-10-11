// Run with: node tests/check_frontend.mjs
// No third-party libraries. Checks parse errors and live data rendering.
import fs from "node:fs";
import vm from "node:vm";
import assert from "node:assert/strict";
const html=fs.readFileSync("index.html","utf8");
const match=html.match(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/i);
assert.ok(match,"Inline browser script is missing");
const script=match[1];
new vm.Script(script,{filename:"index.html inline script"});
const db=JSON.parse(fs.readFileSync("data/companies.json","utf8"));
const history=JSON.parse(fs.readFileSync("data/daily_changes.json","utf8"));
const elements=new Map();
function el(id) {
  if(!elements.has(id))elements.set(id,{
    value:"",textContent:"",innerHTML:"",disabled:false,onclick:null,
    addEventListener(){}, dataset:{}
  });
  return elements.get(id);
}
let fetches=[];
const doc={
  hidden:false,
  getElementById:el,
  querySelectorAll(){return []},
  addEventListener(){}
};
const ctx={
  document:doc,
  Date,
  console,
  setInterval(){},
  atob(x){return Buffer.from(x,"base64").toString("binary")},
  fetch:async (url)=>{
    fetches.push(String(url));
    if(String(url).includes("companies.json"))return {ok:true,json:async()=>db};
    if(String(url).includes("daily_changes.json"))return {ok:true,json:async()=>history};
    if(String(url).includes("leads.json"))return {ok:true,json:async()=>({
      scanned_at:"2026-10-11T07:48:00Z",
      searches_succeeded:657,
      searches_attempted:657,
      searches_failed:0,
      companies_with_any_leads:32
    })};
    throw Error("Unknown fetch: "+url);
  }
};
vm.runInNewContext(script,ctx,{filename:"index.html inline script"});
await new Promise(resolve=>setTimeout(resolve,10));
assert.equal(el("total").textContent,657,"Company total failed to load");
const parts=new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Shanghai",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date());
const dateParts=Object.fromEntries(parts.map(p=>[p.type,p.value]));
const today=new Date(Number(dateParts.year),Number(dateParts.month)-1,Number(dateParts.day));
const day=[today.getFullYear(),String(today.getMonth()+1).padStart(2,"0"),String(today.getDate()).padStart(2,"0")].join("-");
assert.equal(el("newly").textContent,history.events.filter(e=>e.date===day).length,"First-confirmed count must follow event history, not employer opening dates");
assert.equal(el("dated").textContent,db.companies.filter(c=>c.open_date_evidence?.date===c.open_date&&c.open_date_evidence?.scope==="employer").length,"Calendar must exclude historical dates lacking application evidence");
const launched=db.companies.filter(x=>["已开启","已结束","已发布公告（网申待核验）"].includes(x.status)||x.announcement_date).length;
assert.equal(el("launched").textContent,launched,"Launched count is incorrect");
assert.match(el("month").textContent,/20\d{2}年\d{1,2}月/);
assert.match(el("calendar").innerHTML,/class="day/,"Calendar day buttons were not rendered");
assert.ok(el("dayTitle").textContent.includes("确切开启")&&el("dayTitle").textContent.includes("新确认"),"Clicked-day details not rendered");
assert.ok(el("list").innerHTML.includes("企业")||el("list").innerHTML.length>200,"Enterprise list missing");
assert.equal(typeof el("refreshNow").onclick,"function","Reload button not wired");
await el("refreshNow").onclick();
assert.ok(fetches.filter(x=>x.includes("companies.json")).length>=2,"Manual refresh did not request data");
console.log("PASS: frontend JS parses, loads "+db.companies.length+" companies, renders calendar and refreshes data.");
