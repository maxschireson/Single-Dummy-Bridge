const assert=require('node:assert/strict');
const R=require('../reporting.js');
const fixtures=require(process.argv[2]||'./reporting-fixtures.json');
const inputs=fixtures.map(f=>({...f,source:R.sources.find(s=>s.branch===f.ref)}));
let checks=0;function test(name,fn){fn();checks++;console.log('PASS '+name);}
test('source scores reproduce published n, IMP totals, variance, and SE',()=>{
 for(const input of inputs)for(const condition of ['common','own']){
  const published=condition==='common'?input.data.views:input.data.own_views;if(!published)continue;
  const computed=R.view(R.rowsFor([input],input.source.key,condition).rows);
  for(const [p,s] of Object.entries(published[0].groups)){
   const {pair,flip}=R.normalizePair(p),actual=computed.groups[pair];assert.equal(actual.n,s.n);
   assert.equal(actual.total,s.total==null?null:flip?-s.total:s.total);
   if(s.variance!=null)assert.ok(Math.abs(actual.variance-s.variance)<1e-8);
   if(s.se!=null)assert.ok(Math.abs(actual.se-s.se)<1e-8);
  }
 }
});
test('ChatGPT main and both components appear together',()=>{
 const d=R.build(inputs,'chatgpt');const n=inputs.filter(x=>x.source.environment==='chatgpt').reduce((n,x)=>n+x.index.records.length,0);assert.equal(d.report.observations,n);assert.equal(d.completed,n);
 for(const p of ['43','4p~3','4b~3','4~4p','4~4b','4p~4b'])assert.ok(d.views[0].groups[p]);
 assert.equal(d.views[0].groups['43'].n,inputs.find(x=>x.source.key==='supplement').data.views[0].groups['43'].n+inputs.find(x=>x.source.key==='components').data.views[0].groups['43'].n);
});
test('Codex P/Q use the same 4p/4b names and orientations',()=>{
 const d=R.build(inputs,'codex');for(const p of ['4p~3','4b~3','4~4p','4~4b','4p~4b'])assert.ok(d.views[0].groups[p]);
 assert.ok(!Object.keys(d.views[0].groups).some(p=>/[PQ]/.test(p)));
 assert.ok(d.report.observations>=d.completed);
});
test('missing native-bidder condition is excluded, never copied from common',()=>{
 const d=R.build(inputs,'codex');assert.deepEqual(d.report.own_excluded,['Codex six-bot mix']);
 assert.equal(d.own_views[0].groups['43'].n,inputs.find(x=>x.source.key==='primary').data.own_views[0].groups['43'].n);
 assert.equal(d.own_views[0].groups['4p~3'],undefined);
});
test('repeated family and reversed alias count once, earliest independent of IMPs',()=>{
 const source=R.sources.find(s=>s.key==='recovery');const rows=[{id:'1',index:1,pair:'P4',family:'same',completed_epoch:2,imps:12,own_imps:12,scores:[620,-100],contracts:[]},{id:'0',index:0,pair:'4P',family:'same',completed_epoch:1,imps:3,own_imps:3,scores:[110,0],contracts:[]}];
 const x={source,data:{generated_epoch:10},index:{records:rows}};
 const r=R.rowsFor([x]);assert.equal(r.rows.length,1);assert.equal(r.duplicates,1);assert.equal(r.rows[0].imps,3);assert.equal(r.rows[0].pair,'4~4p');
});
test('snapshot cutoff stays exact as new records arrive',()=>{
 const d=R.build(inputs);const future=structuredClone(inputs);future[0].index.records.push({...future[0].index.records[0],id:'future',family:'future',completed_epoch:d.generated_epoch+100});
 const a=R.rowsFor(inputs,'all','common',d.report.snapshots),b=R.rowsFor(future,'all','common',d.report.snapshots);assert.deepEqual(a,b);
});
test('aggregate replay windows reproduce every displayed n and total',()=>{
 for(const scope of ['all','chatgpt','codex']){
 const d=R.build(inputs,scope);for(const condition of ['common','own']){
 const rows=R.rowsFor(inputs,scope,condition,d.report.snapshots).rows;
 for(const n of [0,100,500,1000])for(const [p,s]of Object.entries((condition==='common'?d.views:d.own_views)[n].groups)){
 let selected=rows.filter(r=>r.pair===p);if(n)selected=selected.slice(-n);assert.equal(selected.length,s.n);assert.equal(selected.every(r=>r.imps==null)?null:selected.reduce((a,b)=>a+b.imps,0),s.total);
 }
 }}
});
test('Student-t intervals include small-sample correction',()=>{assert.ok(Math.abs(R.stats([1,3]).ci[1]-(2+12.706204736))<1e-8);assert.equal(R.stats([2]).ci,null);assert.equal(R.stats([null,null]).mean,null);});
test('score/replay verification rejects changed outcomes and missing records',()=>{
 for(const input of inputs){R.verify(input.data,input.index.records);assert.throws(()=>R.verify(input.data,input.index.records.slice(1)),/synchronized/);const changed=structuredClone(input.index.records),r=changed.find(r=>r.imps!=null);r.imps+=1;assert.throws(()=>R.verify(input.data,changed),/totals/);}
});
test('rates use actual completion timestamps and stale streams decay to zero',()=>{
 const now=Math.max(...inputs.map(x=>x.data.generated_epoch))+1,d=R.build(inputs,'all',null,now);
 for(const m of [5,15,30,60]){const count=inputs.flatMap(x=>x.index.records).filter(r=>r.completed_epoch>=now-m*60&&r.completed_epoch<=now).length;assert.equal(d.rates[m].pairs,count);assert.equal(d.rates[m].per_hour,count*60/m);}
 const stale=R.build(inputs,'all',null,now+3601);assert.equal(stale.rates[5].per_hour,0);assert.equal(stale.report.stale.length,4);
});
test('empty and partial reports disclose the streams actually included',()=>{
 const empty=R.build([],'all');assert.equal(empty.completed,0);assert.deepEqual(empty.report.sources,[]);assert.equal(empty.own_views,null);
 const partial=R.build(inputs.slice(0,2));assert.equal(partial.report.sources.length,2);assert.equal(Object.keys(partial.report.snapshots).length,2);
});
console.log(JSON.stringify({checks,summary:['all','chatgpt','codex'].map(s=>{const d=R.build(inputs,s);return {scope:s,completed:d.completed,observations:d.report.observations,duplicates:d.report.duplicates,matchups:Object.keys(d.views[0].groups).length};})}));

