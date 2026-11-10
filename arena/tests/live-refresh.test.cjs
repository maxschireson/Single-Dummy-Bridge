const assert=require('node:assert/strict');
const {createHash}=require('node:crypto');
const modulePath=require.resolve('../reporting.js');
const fresh=()=>{delete require.cache[modulePath];return require(modulePath);};
const row=(i,epoch=10)=>({id:String(i),index:i,family:'family-'+i,pair:'5R32~4b',imps:i%3,own_imps:-(i%3),scores:[0,0],contracts:[],completed_epoch:epoch});
function fixture(R,rows,epoch,checksums=false){
 const source=R.sources.find(s=>s.key==='gen5r'),base='arena/replays/data/'+source.cohort+'/',files={};
 const index={cohort:source.cohort,record_shards:[]};if(checksums)index.record_shard_sha256={};
 for(let i=0;i<rows.length;i+=100){const name='index-'+String(i/100).padStart(5,'0')+'.json',body=JSON.stringify(rows.slice(i,i+100));files[base+name]=body;index.record_shards.push(name);if(checksums)index.record_shard_sha256[name]=createHash('sha256').update(body).digest('hex');}
 files[base+'index.json']=JSON.stringify(index);
 files['arena/data.json']=JSON.stringify({manifest_identity:source.cohort,generated_epoch:epoch,completed:rows.length,views:{0:R.view(rows)},own_views:{0:R.view(rows.map(r=>({...r,imps:r.own_imps})))}});
 return {source,files};
}
function transport(current,counts){return async url=>{const path=new URL(url).pathname.split('/').slice(4).join('/');counts[path]=(counts[path]||0)+1;return new Response(current().files[path]??'missing',{status:Object.hasOwn(current().files,path)?200:404});};}
(async()=>{
 let R=fresh(),stage=fixture(R,[...Array.from({length:100},(_,i)=>row(i+1)),row(1000)],20),counts={};
 global.fetch=transport(()=>stage,counts);
 const first=await R.loadSource(stage.source);assert.equal(first.data.completed,101);
 stage=fixture(R,[row(0,30),...Array.from({length:100},(_,i)=>row(i+1)),row(1000)],40);
 const second=await R.loadSource(stage.source);assert.equal(second.data.completed,102);assert.equal(new Set(second.index.records.map(r=>r.id)).size,102);assert.ok(second.index.records.some(r=>r.id==='0'));
 console.log('PASS repeated refresh handles out-of-order completions without stale full pages');

 R=fresh();stage=fixture(R,Array.from({length:201},(_,i)=>row(i)),20,true);counts={};global.fetch=transport(()=>stage,counts);
 await R.loadSource(stage.source);const stable='arena/replays/data/'+stage.source.cohort+'/index-00000.json';
 stage=fixture(R,[...Array.from({length:201},(_,i)=>row(i)),row(300,30)],40,true);
 await R.loadSource(stage.source);assert.equal(counts[stable],1);
 stage=fixture(R,[row(-1,50),...Array.from({length:201},(_,i)=>row(i)),row(300,30)],60,true);
 await R.loadSource(stage.source);assert.equal(counts[stable],2);
 console.log('PASS unchanged shards reuse verified hashes and changed shards refresh');

 R=fresh();stage=fixture(R,Array.from({length:101},(_,i)=>row(i)),20,true);counts={};const good=transport(()=>stage,counts);let corrupt=true;
 global.fetch=async url=>new URL(url).pathname.endsWith('index-00000.json')&&corrupt?new Response('[]'):good(url);
 await assert.rejects(()=>R.loadSource(stage.source),/checksum/i);corrupt=false;
 assert.equal((await R.loadSource(stage.source)).data.completed,101);
 console.log('PASS a stale CDN response cannot poison the next refresh');

 R=fresh();stage=fixture(R,[row(1)],20);counts={};const requests=[],fetchFresh=transport(()=>stage,counts),now=Date.now;Date.now=()=>123456;
 try{global.fetch=async url=>{requests.push(String(url));return fetchFresh(url);};await R.loadSource(stage.source);await R.loadSource(stage.source);const data=requests.filter(url=>new URL(url).pathname.endsWith('/arena/data.json'));assert.equal(data.length,2);assert.notEqual(data[0],data[1]);}
 finally{Date.now=now;}
 console.log('PASS metadata checks never share a stale URL, even within the same clock tick');

 R=fresh();const a='a'.repeat(40),b='b'.repeat(40),versions={[a]:fixture(R,[row(1)],20),[b]:fixture(R,[row(1),row(2,30)],40)};let head=a,apiCalls=0,clock=100000;Date.now=()=>clock;
 try{
  global.fetch=async url=>{const u=new URL(url);if(u.hostname==='api.github.com'){apiCalls++;return Response.json({object:{sha:head}});}const parts=u.pathname.split('/'),ref=parts[3];assert.ok(versions[ref],'Every score and replay request must use an immutable revision');return new Response(versions[ref].files[parts.slice(4).join('/')]);};
  const source=R.sources[0],first=await R.loadLiveSource(source);assert.equal(first.revision,a);head=b;
  assert.equal((await R.loadLiveSource(source)).data.completed,1);assert.equal(apiCalls,1);
  clock+=91000;const latest=await R.loadLiveSource(source);assert.equal(latest.revision,b);assert.equal(latest.data.completed,2);assert.equal(apiCalls,2);
  const report=R.build([latest],'gen5r',null,clock/1000);assert.equal(report.report.revisions[source.cohort],b);assert.equal(R.rowsFor([latest],'gen5r').rows[0]._revision,b);
  assert.equal((await R.loadLiveSource(source,{revision:a})).data.completed,1);assert.equal(apiCalls,2);
 }finally{Date.now=now;}
 console.log('PASS a refresh pins scores, hands and drill-downs to one publication without excessive API requests');

 R=fresh();const c='c'.repeat(40),sources={[a]:fixture(R,Array.from({length:101},(_,i)=>row(i)),20,true),[b]:fixture(R,Array.from({length:102},(_,i)=>row(i)),40,true),[c]:fixture(R,[row(-1),...Array.from({length:102},(_,i)=>row(i))],60,true)};let firstPageFetches=0;
 global.fetch=async url=>{const parts=new URL(url).pathname.split('/'),path=parts.slice(4).join('/');if(path.endsWith('index-00000.json'))firstPageFetches++;return new Response(sources[parts[3]].files[path]);};
 for(const revision of [a,b])await R.loadSource(R.sources[0],{revision});assert.equal(firstPageFetches,1);
 await R.loadSource(R.sources[0],{revision:c});await R.loadSource(R.sources[0],{revision:a});assert.equal(firstPageFetches,3);
 console.log('PASS verified pages are reused across publications and obsolete versions are evicted');
})().catch(error=>{console.error(error);process.exitCode=1;});
