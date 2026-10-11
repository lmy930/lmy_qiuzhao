// Dependency-free frontend smoke check against real HTML IDs and current data.
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const html=fs.readFileSync('index.html','utf8');const script=html.match(/<script>([\s\S]*?)<\/script>/i)[1];new vm.Script(script);
const ids=new Set([...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]));
const elements=new Map();function el(id){assert.ok(ids.has(id),'Script references missing element '+id);if(!elements.has(id))elements.set(id,{value:'',textContent:'',innerHTML:'',disabled:false,addEventListener(){},dataset:{}});return elements.get(id)}
const db=JSON.parse(fs.readFileSync('data/companies.json','utf8')),baseline=JSON.parse(fs.readFileSync('data/launch_baseline.json','utf8'));let requests=[];
vm.runInNewContext(script,{document:{hidden:false,getElementById:el,querySelectorAll:()=>[],addEventListener(){}},Date,console,setInterval(){},atob:x=>Buffer.from(x,'base64').toString('binary'),fetch:async url=>{requests.push(String(url));if(String(url).includes('companies.json'))return {ok:true,json:async()=>db};if(String(url).includes('launch_baseline.json'))return {ok:true,json:async()=>baseline};if(String(url).includes('page_verification_report.json'))return {ok:true,json:async()=>({scanned_at:new Date().toISOString(),pages_attempted:1,pages_read:1})};throw Error('unexpected resource '+url)}});
await new Promise(r=>setTimeout(r,10));const confirmed=db.companies.filter(c=>['已开启','已结束','已发布公告（网申待核验）'].includes(c.status));
assert.equal(el('categoryAll').textContent,confirmed.length);assert.equal(el('visibleCount').textContent,confirmed.length);assert.ok(el('applicationList').innerHTML.includes('company-card'));
assert.equal(el('boardNew').textContent,confirmed.filter(c=>!baseline.known_launch_names.includes(c.name)).length);
assert.ok(!html.includes('<details'),'Removed directory/calendar must not remain hidden in the page');assert.ok(!ids.has('calendar')&&!ids.has('total'));
await el('refreshNow').onclick();assert.ok(requests.filter(x=>x.includes('companies.json')).length>=2);console.log('PASS: actual HTML IDs, confirmed board, no directory/calendar, fixed baseline and refresh');
