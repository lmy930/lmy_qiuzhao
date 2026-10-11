// Dependency-free regression tests for tracking and daily updates.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=fs.readFileSync('index.html','utf8').match(/<script>([\s\S]*?)<\/script>/i)[1];
const db=JSON.parse(fs.readFileSync('data/companies.json','utf8'));
// Keep the interaction fixture stable as live recruiting data and deadlines change.
db.companies.find(c=>c.name==='中国长江三峡集团有限公司').status='已发布公告（网申待核验）';
const history={events:[{name:'中国长江三峡集团有限公司',date:'2026-10-11',kind:'first_confirmed',opening_date:null}]};
const key='qiuzhao-2027-tracker-v1';
async function boot(storage=new Map(),instant='2026-10-11T09:00:00Z',historyFails=false){
 const elements=new Map();
 function el(id){if(!elements.has(id))elements.set(id,{value:'',textContent:'',innerHTML:'',disabled:false,dataset:{},listeners:new Map(),addEventListener(type,fn){this.listeners.set(type,fn)},click(){this.clicked=true}});return elements.get(id)}
 class Clock extends Date{constructor(...args){super(...(args.length?args:[instant]))}static now(){return new Date(instant).valueOf()}}
 const ctx={Date:Clock,console,Blob,URL,setInterval(){},atob,localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},document:{getElementById:el,querySelectorAll:()=>[],addEventListener(){},createElement:()=>({click(){}})},fetch:async url=>{
  if(String(url).includes('daily_changes.json')){if(historyFails)throw Error('unreachable');return {ok:true,json:async()=>history}}
  if(String(url).includes('page_verification_report.json'))return {ok:true,json:async()=>({scanned_at:'2026-10-11T17:00:00+08:00',pages_read:0,pages_attempted:1})};
  if(String(url).includes('companies.json'))return {ok:true,json:async()=>db};
  return {ok:true,json:async()=>({})};
 }};
 vm.runInNewContext(source,ctx);await new Promise(r=>setTimeout(r,10));
 return {ctx,el,storage,click(name,action){el('applicationList').listeners.get('click')({target:{closest:()=>({dataset:{company:encodeURIComponent(name),action}})}})}};
}
const name='中国长江三峡集团有限公司';
let app=await boot();
assert.match(app.el('scanNotice').textContent,/自动更新暂受影响/,'Failed verification must not look like a successful empty update');
const originalPending=app.el('pendingCount').textContent;
assert.match(app.el('applicationList').innerHTML,/中国长江三峡集团有限公司/);
app.click(name,'applied');
assert.equal(app.el('pendingCount').textContent,originalPending-1);
assert.ok(!app.el('applicationList').innerHTML.includes(name));
app=await boot(app.storage);
assert.ok(!app.el('applicationList').innerHTML.includes(name),'Applied status lost on reload');
app.el('applicationFilter').value='applied';app.el('applicationFilter').listeners.get('change')();
assert.match(app.el('applicationList').innerHTML,/中国长江三峡集团有限公司/);
app.click(name,'pending');
assert.equal(app.el('pendingCount').textContent,originalPending);
app.click(name,'later');
app=await boot(app.storage);
app.el('applicationFilter').value='later';app.el('applicationFilter').listeners.get('change')();
assert.match(app.el('applicationList').innerHTML,/中国长江三峡集团有限公司/);
app.click(name,'pending');
app.el('readUpdates').onclick();
assert.equal(app.el('unreadCount').textContent,0);
app=await boot(app.storage);
assert.equal(app.el('unreadCount').textContent,0,'Read updates lost on reload');
assert.equal(app.el('pendingCount').textContent,originalPending,'Reading updates removed pending companies');
app.el('updateWindow').value='today';app.el('updateWindow').listeners.get('change')();
assert.match(app.el('confirmationUpdates').innerHTML,/中国长江三峡集团有限公司/,'Today view should retain previously read updates');
const midnight=await boot(new Map(),'2026-10-11T16:30:00Z');
assert.match(midnight.el('boardDate').textContent,/2026-10-12/);
assert.equal(midnight.el('todayConfirmed').textContent,0,'Daily changes must use Beijing time');
const failed=await boot(new Map(),undefined,true);
assert.equal(failed.el('todayConfirmed').textContent,'—','History failure must not be called zero new employers');
assert.match(failed.el('confirmationUpdates').innerHTML,/未读取成功/);
const corrupted=new Map([[key,'invalid-json']]);
const fallback=await boot(corrupted);
assert.equal(corrupted.get(key),'invalid-json','Corrupted user records must not be overwritten on load');
assert.match(fallback.el('trackingNote').textContent,/导出备份/);
const newer={version:1,applications:{[name]:{state:'applied',marked_at:'2026-10-11T11:00:00Z'}},read_updates:[]};
await app.el('trackerFile').listeners.get('change')({target:{value:'backup.json',files:[{size:300,text:async()=>JSON.stringify(newer)}]}});
assert.equal(JSON.parse(app.storage.get(key)).applications[name].state,'applied');
const older={...newer,applications:{[name]:{state:'later',marked_at:'2026-10-10T11:00:00Z'}}};
await app.el('trackerFile').listeners.get('change')({target:{value:'backup.json',files:[{size:300,text:async()=>JSON.stringify(older)}]}});
assert.equal(JSON.parse(app.storage.get(key)).applications[name].state,'applied','Older import overwrote newer status');
console.log('PASS: dashboard tracking, reload persistence, read updates, Beijing day, failed history, backup merge');
