const assert=require('node:assert/strict');
const modulePath=require.resolve('../reporting.js');
const fresh=()=>{delete require.cache[modulePath];return require(modulePath);};
const R=fresh();
const timing=seconds=>({by_bot:{'6-32':{decisions:1,total_seconds:seconds,opening_lead:{decisions:0,total_seconds:0},play:{decisions:1,total_seconds:seconds}}}});
const row=(id,pair,family,epoch,imps,own_imps,seconds)=>({id:String(id),index:id,pair,family,completed_epoch:epoch,imps,own_imps,scores:[0,0],contracts:[],decision_timing:timing(seconds)});
const input=(key,records)=>({source:R.sources.find(s=>s.key===key),revision:'a'.repeat(40),data:{generated_epoch:100,target:records.length,failures:0,order:['6-32','6-256','5RZ32','ben','3'],own_views:{},decision_timing:timing(99999)},index:{supports_own_bidding:true,records}});
const inputs=[
 input('gen6',[row(0,'6-32~5RZ32','shared',10,2,3,2)]),
 input('gen6independent',[row(0,'6-32~5RZ32','shared',11,99,99,1),row(1,'6-256~ben','medium-ben',12,4,6,3)]),
 input('gen6chatgpt',[row(0,'6-32~ben','mistake',10,1000,1000,10000),row(1,'6-32~3','three',13,-1,0,4)]),
 input('gen6initial',[row(2,'6-32~5RZ32','early-compatible',1,1,1,5)]),
 input('gen5rz',[row(5,'5RZ32~5R32','old-generation',1,999,999,999)])
];
const d=R.build(inputs,'latest',null,100);
assert.equal(R.latestScope,'gen6');assert.equal(d.completed,4);assert.equal(d.report.observations,5);assert.equal(d.report.duplicates,1);
assert.deepEqual(d.report.sources,['gen6','gen6independent','gen6chatgpt','gen6initial']);
assert.equal(d.views[0].groups['6-32~ben'],undefined);
assert.equal(d.views[0].groups['6-256~ben'].total,4);
assert.equal(d.views[0].groups['6-32~5RZ32'].total,3);
assert.equal(d.difference_views[0].groups['6-256~ben'].bidding.total,2);
assert.equal(d.decision_timing.by_bot['6-32'].total_seconds,15);
assert.equal(R.build(inputs,'all',null,100).views[0].groups['6-32~ben'],undefined);
assert.equal(inputs[2].index.records.length,2,'Archive data must remain untouched');
console.log('PASS compatible Gen6 streams combine; duplicates and accidental fast/BEN scores and timing are excluded');

(async()=>{
 const Q=fresh(),sources=Q.pickSources('latest').filter(s=>!s.retired),files={};
 const heads=Object.fromEntries(sources.map((s,i)=>[s.branch,String(i+1).repeat(40)]));
 for(const [i,source]of sources.entries()){
  const records=[row(i,'6-32~5RZ32','network-'+i,10,i,i,1)],ref=heads[source.branch];
  files[ref+'/arena/data.json']={manifest_identity:source.cohort,generated_epoch:20,completed:1,views:{0:Q.view(records)},own_views:{0:Q.view(records)}};
  files[ref+'/arena/replays/data/'+source.cohort+'/index.json']={cohort:source.cohort,records,supports_own_bidding:true};
 }
 let apiCalls=0;const realFetch=global.fetch;
 global.fetch=async url=>{const u=new URL(url);if(u.hostname==='api.github.com'){apiCalls++;return Response.json(Object.entries(heads).map(([name,sha])=>({name,commit:{sha}})));}const key=u.pathname.split('/').slice(3).join('/');assert.ok(files[key],'Every producer must use its immutable revision');return Response.json(files[key]);};
 try{
  const loaded=await Promise.all(sources.map(s=>Q.loadLiveSource(s)));
  assert.equal(apiCalls,1);assert.equal(loaded.length,3);
  for(const x of loaded)assert.equal(x.revision,heads[x.source.branch]);
  await Promise.all(sources.map(s=>Q.loadLiveSource(s)));assert.equal(apiCalls,1);
 }finally{global.fetch=realFetch;}
 console.log('PASS all three active producers share a single branch-head refresh and preserve immutable replay revisions');
})().catch(error=>{console.error(error);process.exitCode=1;});
