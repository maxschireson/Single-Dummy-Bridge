const assert=require('node:assert/strict');
const R=require('../reporting.js');
const source=R.sources.find(s=>s.key==='gen6');
const now=10000;
const data={manifest_identity:source.cohort,generated_epoch:now-20,completed:0,feed:{published_epoch:now-20,interval_seconds:60},collection:{updated_epoch:now-25,running:true},views:{0:{groups:{}}},own_views:{0:{groups:{}}}};
assert.equal(R.feedHealth(source,data,now).state,'live');
assert.equal(R.feedHealth(source,{...data,feed:{published_epoch:now-1800}},now).state,'overdue');
assert.equal(R.feedHealth({...source,retired:true},data,now+100000).state,'archived');
assert.equal(R.feedHealth(source,{...data,collection:{updated_epoch:now-700,running:false}},now).state,'no-heartbeat');
assert.equal(R.feedHealth(source,{...data,collection:{updated_epoch:now,status:'stopped'}},now+100000).state,'paused');
assert.equal(R.feedHealth(source,{...data,target:10,completed:10},now+100000).state,'complete');
assert.equal(R.feedHealth(source,{...data,collection:{status:'not_running'}},now).state,'stopped');
assert.equal(R.feedHealth(source,null,now).state,'pending');
assert.equal(R.feedHealth(source,{...data,collection:{status:'draining'}},now).state,'draining');
console.log('PASS heartbeat, publication delay, deliberate stop and archived snapshots have distinct health states');

(async()=>{
 const archived={...source,retired:true,revision:'a'.repeat(40)};
 const originalFetch=global.fetch;let reads=0;
 global.fetch=async url=>{reads++;return Response.json(new URL(url).pathname.endsWith('data.json')?data:{cohort:source.cohort,records:[],supports_own_bidding:true});};
 try{
  await Promise.all([R.loadLiveSource(archived),R.loadLiveSource(archived)]);
  const x=await R.loadLiveSource({...archived,name:'Retired after transition'});
  assert.equal(reads,2,'A pinned archived score/index is fetched once across refreshes');
  assert.equal(x.source.name,'Retired after transition','Registry metadata stays current when cached bytes are reused');
 }finally{global.fetch=originalFetch;}
 R.applyRegistry({schema:'arena-gen6-source-registry-v1',sources:[archived]});
 const result=R.build([{source,data:{...data,target:1,failures:0,order:[]},index:{records:[]}}],'latest',null,now+10000);
 assert.equal(result.report.health[source.key].state,'archived');
 assert.equal(result.report.stale.length,0,'A cached source object cannot keep an intentionally retired feed in the stale list');
 console.log('PASS immutable archives are cached and source retirement immediately updates health');
})().catch(e=>{console.error(e);process.exitCode=1;});
