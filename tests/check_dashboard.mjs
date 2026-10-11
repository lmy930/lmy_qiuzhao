// Dependency-free checks for persistent tracking, category filters and fixed-baseline colors.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=fs.readFileSync('index.html','utf8').match(/<script>([\s\S]*?)<\/script>/i)[1];
const database=JSON.parse(fs.readFileSync('data/companies.json','utf8'));
const baseline=JSON.parse(fs.readFileSync('data/launch_baseline.json','utf8'));
const key='qiuzhao-2027-tracker-v1',name='中国长江三峡集团有限公司';
async function boot(storage=new Map(),{baselineFails=false,companiesFail=false,healthyScan=false,unverifiedAnnouncement=false,simulateNew=false,unsafeLinks=false,updates=[]}={}){
 const db=structuredClone(database),snapshot=structuredClone(baseline);
 db.companies.find(c=>c.name===name).status='已发布公告（网申待核验）';
 // This interaction fixture has its own initial snapshot; production data may
 // legitimately contain companies discovered after the real fixed baseline.
 snapshot.known_launch_names=db.companies.filter(c=>['已开启','已结束','已发布公告（网申待核验）'].includes(c.status)).map(c=>c.name);
 if(simulateNew)snapshot.known_launch_names=snapshot.known_launch_names.filter(n=>n!==name);
 const unverifiedName=db.companies.find(c=>c.status==='待核验').name;
 if(unverifiedAnnouncement)db.companies.find(c=>c.name===unverifiedName).announcement_date='2026-10-11';
 if(unsafeLinks){const c=db.companies.find(c=>c.name===name);c.page_verification={url:'javascript:alert(1)',title:'<script>unsafe</script>'};c.announcement_source_url='javascript:alert(1)';c.application_channels=[{company:name,url:'javascript:alert(2)',proof_url:'https://example.com/proof',proof_sha256:'abc'}]}
 const elements=new Map();
 function el(id){if(!elements.has(id))elements.set(id,{value:'',textContent:'',innerHTML:'',disabled:false,dataset:{},listeners:new Map(),addEventListener(type,fn){this.listeners.set(type,fn)},click(){this.clicked=true}});return elements.get(id)}
 const categories=['','银行','央企','民营500'].map(category=>({dataset:{category},listeners:new Map(),attributes:{},setAttribute(k,v){this.attributes[k]=v},addEventListener(k,v){this.listeners.set(k,v)}}));
 const directoryCategories=['民营500','银行','央企'].map(directoryCategory=>({dataset:{directoryCategory},listeners:new Map(),attributes:{},setAttribute(k,v){this.attributes[k]=v},addEventListener(k,v){this.listeners.set(k,v)}}));
 const ctx={Date,console,Blob,URL,setInterval(){},atob,localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},document:{getElementById:el,querySelectorAll:selector=>selector==='[data-category]'?categories:selector==='[data-directory-category]'?directoryCategories:[],addEventListener(){},createElement:()=>({click(){}})},fetch:async url=>{
  if(String(url).includes('launch_baseline.json')){if(baselineFails)throw Error('unreachable');return {ok:true,json:async()=>snapshot}}
  if(String(url).includes('company_order.json'))return {ok:true,json:async()=>JSON.parse(fs.readFileSync('data/company_order.json','utf8'))};if(String(url).includes('daily_changes.json'))return {ok:true,json:async()=>({events:updates})};
  if(String(url).includes('page_verification_report.json'))return {ok:true,json:async()=>({scanned_at:new Date().toISOString(),pages_read:healthyScan?1:0,pages_attempted:1})};
  if(String(url).includes('companies.json')){if(companiesFail)throw Error('unreachable');return {ok:true,json:async()=>db}};
  throw Error('unexpected resource');
 }};
 vm.runInNewContext(source,ctx);await new Promise(r=>setTimeout(r,10));
 return {ctx,el,storage,db,unverifiedName,directory(value){directoryCategories.find(c=>c.dataset.directoryCategory===value).listeners.get('click')()},category(value){categories.find(c=>c.dataset.category===value).listeners.get('click')()},select(id,value){el(id).value=value;el(id).listeners.get('change')()},click(name,action){el('applicationList').listeners.get('click')({target:{closest:()=>({dataset:{company:encodeURIComponent(name),action}})}})}};
}
let app=await boot();
assert.match(app.el('scanNotice').textContent,/自动更新暂受影响/);
assert.equal(app.el('boardNew').textContent,0,'Initial companies must never be shown as newly confirmed');
app.select('applicationFilter','pending');
const originalPending=app.el('pendingCount').textContent;
app.click(name,'applied');assert.equal(app.el('pendingCount').textContent,originalPending-1);assert.ok(!app.el('applicationList').innerHTML.includes(name));
app=await boot(app.storage);app.select('applicationFilter','applied');assert.match(app.el('applicationList').innerHTML,/中国长江三峡集团有限公司/);
app.click(name,'pending');assert.equal(app.el('pendingCount').textContent,originalPending);
app.click(name,'later');app=await boot(app.storage);app.select('applicationFilter','later');assert.match(app.el('applicationList').innerHTML,/中国长江三峡集团有限公司/);
app.click(name,'pending');
for(const group of ['银行','央企','民营500']){
 app.select('applicationFilter','all');app.category(group);
 const names=[...app.el('applicationList').innerHTML.matchAll(/data-name="([^"]+)"/g)].map(m=>m[1]);
 assert.ok(names.length>0,'Category must show actual confirmed employers');
 assert.ok(names.every(n=>app.db.companies.find(c=>c.name===n)?.groups.includes(group)),'Category leaked other groups');
}
app.category('');app.el('boardQuery').value='中国长江三峡';app.el('boardQuery').listeners.get('input')();assert.equal(app.el('visibleCount').textContent,1);
let future=await boot(new Map(),{simulateNew:true});
assert.equal(future.el('boardNew').textContent,1);assert.match(future.el('applicationList').innerHTML,/company-card new-company/);
future.select('boardRange','new');assert.equal(future.el('visibleCount').textContent,1);assert.match(future.el('applicationList').innerHTML,/中国长江三峡集团有限公司/);
future.click(name,'applied');future=await boot(future.storage,{simulateNew:true});assert.equal(future.el('boardNew').textContent,1,'Application state must not reset baseline color');
future.select('boardRange','baseline');assert.ok(!future.el('applicationList').innerHTML.includes(name));
const failed=await boot(new Map(),{baselineFails:true});assert.equal(failed.el('boardNew').textContent,'—');assert.match(failed.el('baselineWarning').textContent,/新旧标记暂不可用/);assert.ok(failed.el('visibleCount').textContent>0);
failed.select('boardRange','new');assert.match(failed.el('applicationList').innerHTML,/无法区分新旧企业/);
const saved=new Map([[key,JSON.stringify({version:1,applications:{[name]:{state:'applied',marked_at:'2026-10-11T11:00:00Z'}},read_updates:[]})]]);const noData=await boot(saved,{companiesFail:true});assert.equal(noData.el('categoryAll').textContent,'—');assert.match(noData.el('dataNotice').textContent,/未读取成功/);assert.equal(JSON.parse(saved.get(key)).applications[name].state,'applied');
const unverified=await boot(new Map(),{unverifiedAnnouncement:true});assert.ok(!unverified.el('applicationList').innerHTML.includes(unverified.unverifiedName),'Publication date cannot promote an unverified company');
const healthy=await boot(new Map(),{healthyScan:true});assert.equal(healthy.el('scanNotice').textContent,'');assert.match(healthy.el('health').textContent,/最近核验/);
const corrupted=new Map([[key,'invalid-json']]);const fallback=await boot(corrupted);assert.equal(corrupted.get(key),'invalid-json');assert.match(fallback.el('trackingNote').textContent,/备份记录/);
const newer={version:1,applications:{[name]:{state:'applied',marked_at:'2026-10-11T11:00:00Z'}},read_updates:[]};
await app.el('trackerFile').listeners.get('change')({target:{value:'backup.json',files:[{size:300,text:async()=>JSON.stringify(newer)}]}});
assert.equal(JSON.parse(app.storage.get(key)).applications[name].state,'applied');
const older={...newer,applications:{[name]:{state:'later',marked_at:'2026-10-10T11:00:00Z'}}};
await app.el('trackerFile').listeners.get('change')({target:{value:'backup.json',files:[{size:300,text:async()=>JSON.stringify(older)}]}});
assert.equal(JSON.parse(app.storage.get(key)).applications[name].state,'applied');
console.log('PASS: fixed baseline, future colors, category/search filters, tracking persistence, baseline failure, backup merge');

const statusBoard=await boot();
assert.match(statusBoard.el('coverageNotice').textContent,/待核验不代表未开招/);
for(const [filter,status] of [['open','已开启'],['unknown','已发布公告（网申待核验）'],['ended','已结束']]){
 statusBoard.select('recruitmentFilter',filter);
 const names=[...statusBoard.el('applicationList').innerHTML.matchAll(/data-name="([^"]+)"/g)].map(m=>m[1]);
 assert.equal(names.length,statusBoard.db.companies.filter(c=>c.status===status).length);
 assert.ok(names.every(n=>statusBoard.db.companies.find(c=>c.name===n).status===status));
}
statusBoard.select('recruitmentFilter','evidence');assert.match(statusBoard.el('applicationList').innerHTML,/完整正文证据待自动补齐/);
assert.ok(!statusBoard.el('applicationList').innerHTML.includes('javascript:'));
const unsafe=await boot(new Map(),{unsafeLinks:true});assert.ok(!unsafe.el('applicationList').innerHTML.includes('href="javascript:'));assert.ok(!unsafe.el('applicationList').innerHTML.includes('<script>unsafe</script>'));
console.log('PASS: recruitment availability filters, missing body warnings and safe source links');

const today=new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Shanghai'});
const updated=await boot(new Map(),{updates:[{name,kind:'recruitment_updated',date:today,observed_at:new Date().toISOString()}]});
updated.select('boardRange','updated');assert.equal(updated.el('visibleCount').textContent,1);assert.match(updated.el('applicationList').innerHTML,/updated-company/);
updated.select('boardRange','all');assert.match(updated.el('uncertainSummary').innerHTML,/尚未确认启动/);
const sortedNames=[...updated.el('applicationList').innerHTML.matchAll(/data-name="([^"]+)"/g)].map(m=>m[1]);
let sawUncertain=false;for(const n of sortedNames){const c=updated.db.companies.find(c=>c.name===n);const uncertain=c.status==='已发布公告（网申待核验）'||!c.page_verification?.sha256;if(uncertain)sawUncertain=true;else assert.equal(sawUncertain,false,'Certain record appeared below uncertain records')}
updated.directory('银行');assert.ok(!updated.el('uncertainSummary').innerHTML.includes('华为投资控股有限公司'));
console.log('PASS: uncertain records last, grouped name summary and actual daily update colors');

const freshToday=await boot(new Map(),{simulateNew:true,updates:[{name,kind:'first_confirmed',date:today,observed_at:new Date().toISOString()}]});freshToday.select('boardRange','updated');assert.equal(freshToday.el('visibleCount').textContent,1);assert.match(freshToday.el('applicationList').innerHTML,/new-company/);
console.log('PASS: today filter also includes newly confirmed employers');

const directory=await boot();
for(const group of ['民营500','银行','央企']){
 directory.directory(group);const html=directory.el('uncertainSummary').innerHTML;
 const expected=JSON.parse(fs.readFileSync('data/company_order.json','utf8')).groups[group];
 assert.equal((html.match(/<tr(?: class="unconfirmed-row")?>/g)||[]).length,expected.length+1);
 for(const row of expected)assert.ok(html.includes('<td>'+row.number+'</td><td>'+row.name.replaceAll('&','&amp;')),'Missing original catalog ordinal');
}
directory.directory('民营500');assert.match(directory.el('uncertainSummary').innerHTML,/<td>67<\/td><td>中国民生银行股份有限公司/);
directory.el('boardQuery').value='华为';directory.el('boardQuery').listeners.get('input')();assert.match(directory.el('uncertainSummary').innerHTML,/<td>4<\/td>/);assert.ok(!directory.el('uncertainSummary').innerHTML.includes('class="unconfirmed-row"'));
console.log('PASS: three complete directory tables, preserved ordinals, private rank 67 recovery and honest highlighting');

let tableTracker=await boot();
const tableName='中国民生银行股份有限公司';
function tableClick(app,name,action){app.el('uncertainSummary').listeners.get('click')({target:{closest:()=>({dataset:{company:encodeURIComponent(name),action}})}})}
tableTracker.directory('银行');tableClick(tableTracker,tableName,'applied');
assert.equal(JSON.parse(tableTracker.storage.get(key)).applications[tableName].state,'applied');
tableTracker=await boot(tableTracker.storage);tableTracker.directory('民营500');
let tableRow=tableTracker.el('uncertainSummary').innerHTML.split('<tr').find(row=>row.includes('<td>'+tableName+'</td>'));
assert.match(tableRow,/data-action="applied"[^>]+aria-pressed="true"/);
assert.match(tableTracker.el('applicationList').innerHTML.split('<article').find(row=>row.includes('data-name="'+tableName+'"')),/application-state">已投递/);
tableClick(tableTracker,tableName,'pending');tableTracker=await boot(tableTracker.storage);
assert.ok(!JSON.parse(tableTracker.storage.get(key)).applications[tableName]);
tableClick(tableTracker,tableTracker.unverifiedName,'applied');tableTracker=await boot(tableTracker.storage);
assert.equal(JSON.parse(tableTracker.storage.get(key)).applications[tableTracker.unverifiedName].state,'applied','Unconfirmed employers can also be tracked without promoting recruitment status');
assert.equal(tableTracker.db.companies.find(c=>c.name===tableTracker.unverifiedName).status,'待核验');
console.log('PASS: table application buttons persist, sync with cards and categories, reset and support unconfirmed employers');
