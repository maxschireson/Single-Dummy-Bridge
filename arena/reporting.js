/* Shared reporting rules for the dashboard and its exact replay drill-downs. */
(function(root){'use strict';
 const base='https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/';
 const sources=[
  {key:'gen5r',generation:5,variant:'5R',environment:'codex',name:'Gen 5R · current round',branch:'arena-gen5r-feed',cohort:'cdd9bbb2359f172f69cb19708e8ec8efd2ce4dbb784113a5c3a7b58a347d49a3'},
  {key:'gen5',generation:5,retired:true,environment:'codex',name:'Gen 5 · previous round',branch:'arena-gen5-codex-32-feed',cohort:'c31501047e52a6caa99473dc39262578977def53742387afa9f0d1237e30dc59'},
  {key:'gen5initial',generation:5,retired:true,allowed_pairs:['5~ben','5~5-32'],environment:'codex',name:'Gen 5 · retained BEN/control games',branch:'arena-gen5-codex-feed',cohort:'bdf0a63bd89b013cb918c966663f02dab5c049652da3df9f6198e52f84e3e14f'},
  {key:'primarycomponents',environment:'codex',name:'Codex primary 4p / 4b (no self-play)',branch:'arena-primary-components-feed',cohort:'4f43d6f3f234b9e561671f6958bbe2785e8896181791632ee4b1569a5ab062e0'},
  {key:'primary',environment:'codex',name:'Codex main',branch:'arena-feed',cohort:'7559edd31715b71f77a47af22a87cb64b2a72c3da4b0cf262fd76003628f2404'},
  {key:'recovery',environment:'codex',name:'Codex six-bot mix',branch:'arena-recovery-feed',cohort:'7729472d36914fd1dce8ecfcc2d520cfc1c03ce737ac99511093e94ebce33a4c'},
  {key:'supplement',environment:'chatgpt',name:'ChatGPT main',branch:'arena-local-feed',cohort:'b1e339d361600d6ba1fb7ad8058ae9fead50b247a0dd7c12f806a2293f06370d'},
  {key:'components',environment:'chatgpt',name:'ChatGPT 4p / 4b',branch:'arena-components-feed',cohort:'749485be7d6882791e79bf2ce4fbbd8ca9a7a9403ca6784e29fdc53cce2043b9'}
 ];
 const labels={'5R32':'Gen 5R (32)','5R192':'Gen 5R (192)','5':'Gen 5 (192)','5-32':'Gen 5 (32)','ben':'BEN (16)','4':'Gen 4','4p':'Gen 4p','4b':'Gen 4b','3':'Gen 3','2':'Gen 2','1':'Gen 1'},order=['5R32','5R192','5','5-32','4','4p','4b','3','2','1','ben'];
 const names={all:'All streams (rollup)',chatgpt:'ChatGPT',codex:'Codex',...Object.fromEntries(sources.map(s=>[s.key,s.name]))};
 const canonical=k=>({P:'4p',Q:'4b'}[k]||k),members=p=>(p.includes('~')?p.split('~'):[...p]).map(canonical);
 const pairID=(a,b)=>a.length===1&&b.length===1?a+b:a+'~'+b;
 function normalizePair(p){const [a,b]=members(p),flip=order.indexOf(a)>order.indexOf(b);return {pair:flip?pairID(b,a):pairID(a,b),flip};}
 const byTime=(a,b)=>a.completed_epoch-b.completed_epoch||a._cohort.localeCompare(b._cohort)||a.index-b.index;
 const pickSources=scope=>sources.filter(s=>scope==='all'||s.environment===scope||s.key===scope||(scope==='gen5'&&s.generation===5&&s.variant!=='5R'));
 const t95=[0,12.706204736,4.30265273,3.182446305,2.776445105,2.570581836,2.446911851,2.364624252,2.306004135,2.262157163,2.228138852,2.20098516,2.17881283,2.160368656,2.144786688,2.131449546,2.119905299,2.109815578,2.10092204,2.093024054,2.085963447,2.079613845,2.073873068,2.06865761,2.063898562,2.059538553,2.055529439,2.051830516,2.048407142,2.045229642,2.042272456];
 function critical(df){if(df<=30)return t95[df];const z=1.95996398454;return z+(z**3+z)/(4*df)+(5*z**5+16*z**3+3*z)/(96*df**2)+(3*z**7+19*z**5+17*z**3-15*z)/(384*df**3);}
 function stats(values){const n=values.length,v=values.filter(Number.isFinite);if(!v.length)return {n,total:null,mean:null,variance:null,sd:null,se:null,ci:null,wins:0,ties:0,losses:0};
  if(v.length!==n)throw Error('Missing scored outcome');const total=v.reduce((a,b)=>a+b,0),mean=total/n,variance=n>1?v.reduce((s,x)=>s+(x-mean)**2,0)/(n-1):null,sd=variance===null?null:Math.sqrt(variance),se=sd===null?null:sd/Math.sqrt(n),half=se===null?null:critical(n-1)*se;
  return {n,total,mean,variance,sd,se,ci:half===null?null:[mean-half,mean+half],wins:v.filter(x=>x>0).length,ties:v.filter(x=>x===0).length,losses:v.filter(x=>x<0).length};
 }
 function rowsFor(inputs,scope='all',condition='common',snapshots=null){const allowed=new Set(pickSources(scope).map(s=>s.key)),rows=[];
  for(const input of inputs){const {source,data,index}=input;if(!allowed.has(source.key))continue;if(condition==='own'&&(!data.own_views||index.supports_own_bidding===false))continue;
   const cutoff=snapshots? snapshots[source.cohort]:data.generated_epoch;if(cutoff==null)continue;
   for(const r of index.records){if(r.completed_epoch>cutoff||source.allowed_pairs&&!source.allowed_pairs.includes(r.pair))continue;if(!r.family)throw Error('Missing deal-family identity');const {pair,flip}=normalizePair(r.pair),value=condition==='own'?r.own_imps:r.imps;
    if(condition==='own'&&!Object.hasOwn(r,'own_imps'))continue;
    rows.push({...r,pair,imps:value==null?null:flip?-value:value,scores:[...(condition==='own'?r.own_scores||r.scores:r.scores)].slice()[flip?'reverse':'slice'](),contracts:[...(condition==='own'?r.own_contracts||r.contracts:r.contracts)].slice()[flip?'reverse':'slice'](),_pair:r.pair,_flip:flip,_cohort:source.cohort,_source:source.key,_environment:source.environment,_title:source.name});
   }
  }
  // One observation per family and matchup, independent of the outcome. Earliest wins.
  rows.sort(byTime);const seen=new Set(),result=[];for(const row of rows){const key=row.family+'|'+row.pair;if(!seen.has(key)){seen.add(key);result.push(row);}}
  return {rows:result,duplicates:rows.length-result.length,observations:rows.length};
 }
 function view(rows,windowSize=0){const groups={},matrix=Object.fromEntries(order.map(k=>[k,{}])),pairs=[...new Set(rows.map(r=>r.pair))].sort((a,b)=>{const [a0,a1]=members(a),[b0,b1]=members(b);return order.indexOf(a0)-order.indexOf(b0)||order.indexOf(a1)-order.indexOf(b1);});
  for(const pair of pairs){let selected=rows.filter(r=>r.pair===pair);if(windowSize)selected=selected.slice(-windowSize);const values=selected.map(r=>r.imps),s=stats(values),[a,b]=members(pair);groups[pair]=s;matrix[a][b]=s;if(a!==b)matrix[b][a]=stats(values.map(x=>-x));}return {groups,matrix};
 }

 function decisionTiming(inputs){const totals={schema:'arena-decision-timing-v1',by_bot:{},sources:[],missing_sources:[]};
  for(const input of inputs){const data=input.data.decision_timing;if(!data){totals.missing_sources.push(input.source.name);continue;}totals.sources.push(input.source.name);
   for(const [id,row] of Object.entries(data.by_bot||{})){const key=canonical(id),out=totals.by_bot[key]||={decisions:0,total_seconds:0,forced_decisions:0,opening_lead:{decisions:0,total_seconds:0},play:{decisions:0,total_seconds:0}};
    for(const field of ['decisions','total_seconds','forced_decisions'])out[field]+=row[field]||0;
    for(const phase of ['opening_lead','play'])for(const field of ['decisions','total_seconds'])out[phase][field]+=row[phase]?.[field]||0;
   }
  }
  for(const row of Object.values(totals.by_bot))for(const part of [row,row.opening_lead,row.play])part.mean_seconds=part.decisions?part.total_seconds/part.decisions:null;
  return totals;
 }
 function build(inputs,scope='all',snapshots=null,now=Date.now()/1000){const chosen=inputs.filter(x=>pickSources(scope).some(s=>s.key===x.source.key));
  const common=rowsFor(chosen,scope,'common',snapshots),own=rowsFor(chosen,scope,'own',snapshots),views={},own_views={},curves={},own_curves={};
  for(const n of [0,100,500,1000]){views[n]=view(common.rows,n);own_views[n]=view(own.rows,n);}
  for(const [rowsSource,targetCurves] of [[common.rows,curves],[own.rows,own_curves]])for(const p of Object.keys(view(rowsSource).groups)){if(members(p)[0]===members(p)[1])continue;const rows=rowsSource.filter(r=>r.pair===p);targetCurves[p]=[];for(let n=10;n<rows.length;n+=Math.max(10,Math.floor(rows.length/50)))targetCurves[p].push({index:n,...stats(rows.slice(0,n).map(r=>r.imps))});targetCurves[p].push({index:rows.length,...stats(rows.map(r=>r.imps))});}
  const generated_epoch=chosen.length?Math.max(...chosen.map(x=>x.data.generated_epoch)):now,rates={};
  const observations=chosen.flatMap(x=>x.index.records.filter(r=>r.completed_epoch<=x.data.generated_epoch&&(!x.source.allowed_pairs||x.source.allowed_pairs.includes(r.pair))));
  for(const m of [5,15,30,60]){const pairs=observations.filter(r=>r.completed_epoch>=now-m*60&&r.completed_epoch<=now).length;rates[m]={pairs,per_hour:pairs*60/m,full_window:true};}
  const stale=chosen.filter(x=>!x.source.retired&&now-(x.data.feed?.published_epoch||x.data.generated_epoch)>240).map(x=>x.source.name);
  const reportSnapshots=snapshots||Object.fromEntries(chosen.map(x=>[x.source.cohort,x.data.generated_epoch]));
  const activeOrder=order.filter(k=>chosen.some(x=>(x.data.order||[]).map(canonical).includes(k)));
  return {decision_timing:decisionTiming(chosen),campaign:(names[scope]||sources.find(s=>s.key===scope)?.name)+' · integrated arena',manifest_identity:'report:'+scope,labels,order:activeOrder,versions:Object.fromEntries(activeOrder.map(k=>[k,k==='4p'?'v4 policy / v3 belief':k==='4b'?'v3 policy / v4 belief':'v'+k])),generated_epoch,
   completed:common.rows.length,target:chosen.reduce((n,x)=>n+x.data.target,0),contiguous:common.observations,failures:chosen.reduce((n,x)=>n+x.data.failures,0),configured_workers:chosen.reduce((n,x)=>n+(x.data.configured_workers||0),0),rates,views,own_views:own.rows.length?own_views:null,curves,own_curves,
   report:{scope,snapshots:reportSnapshots,stale,duplicates:common.duplicates,observations:common.observations,families:new Set(common.rows.map(r=>r.family)).size,sources:chosen.map(x=>x.source.key),own_excluded:chosen.filter(x=>!x.data.own_views||x.index.supports_own_bidding===false).map(x=>x.source.name)},
   feed:{published_epoch:generated_epoch,next_update_epoch:chosen.some(x=>!x.source.retired)?Math.min(...chosen.filter(x=>!x.source.retired).map(x=>x.data.feed?.next_update_epoch||x.data.generated_epoch+60)):now+60},
   interpretation:'Completed paired boards are combined by matchup across the selected environment’s main and component runs. P/Q aliases are mapped to 4p/4b. Repeat deal families within a matchup count once, retaining the earliest completed observation regardless of outcome. Different matchups may share families. This descriptive rollup weights each counted board equally; runtime and deal mix can differ by stream. Collection rates count run observations, including repeats, over the current wall-clock window. Common auctions and native bidders are separate; runs without native-bidder games are excluded from that condition. Student-t intervals are exploratory and unadjusted for repeated looks. Self-play has no strength estimate.',
   model_note:chosen.some(x=>x.source.variant==='5R')?'Gen5R keeps Gen5 networks and changes only 10–13-trick layout selection and belief-moment weights. Pools 128/768; DDS ceilings 32/192. Original Gen5 (32) is the random-sampling control. Smaller positions are unchanged. Common and native bidding remain separate.':chosen.some(x=>x.source.generation===5)?'Gen5 and older bots both use 32 samples in historical comparisons. Gen5 uses 192 only against BEN (16) and Gen5 (32), with identical networks at both budgets. Earlier 192-vs-older games are preserved for training and excluded from statistics. Common-v5 and native bidding are separate.':'Gen 4p: Gen 4 policy + Gen 3 belief and bidder. Gen 4b: Gen 4 belief + Gen 3 policy and bidder. All common-auction results use the frozen Gen 4 bidder and 32 samples. Click any score to inspect its contributing runs and plays.'};
 }
 async function get(url){const r=await fetch(url+(url.includes('?')?'&':'?')+'v='+Math.floor(Date.now()/30000),{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error('HTTP '+r.status);return r.json();}
 function verify(data,records){
  if(!data.views?.[0]?.groups)throw Error('Invalid score snapshot');
  if(!Number.isFinite(data.generated_epoch)||records.length!==data.completed||new Set(records.map(r=>String(r.id))).size!==records.length)throw Error('Score and replay publication are not yet synchronized');
  for(const [kind,views] of [['imps',data.views],['own_imps',data.own_views]]){if(!views)continue;const groups=views['0']?.groups;if(!groups)throw Error('Invalid score snapshot');
   for(const [p,s] of Object.entries(groups)){const rows=records.filter(r=>r.pair===p),self=members(p)[0]===members(p)[1];const total=rows.reduce((n,r)=>n+(r[kind]??0),0);if(rows.length!==s.n||(s.total!==null&&Math.abs(total-s.total)>1e-8)||(!self&&rows.some(r=>!Number.isFinite(r[kind]))))throw Error('Score/replay totals do not agree');}
   if(Object.values(groups).reduce((n,s)=>n+s.n,0)!==records.length)throw Error('Incomplete score coverage');
  }
 }
 const shardCache=new Map();
 async function loadSource(source,{indexOnly=false,cutoff=null}={}){const path=base+source.branch+'/arena/',data=indexOnly?{generated_epoch:cutoff??Infinity,own_views:source.key==='recovery'?null:{}}:await get(path+'data.json');
  if(!indexOnly&&data.manifest_identity!==source.cohort)throw Error('Run identity changed');
  const indexURL=path+'replays/data/'+source.cohort+'/index.json',index=await get(indexURL);if(index.cohort!==source.cohort)throw Error('Replay run identity mismatch');
  if(index.record_shards){index.records=(await Promise.all(index.record_shards.map(async(p,i)=>{const url=new URL(p,indexURL).href;if(shardCache.has(url))return shardCache.get(url);const rows=await get(url);if(i<index.record_shards.length-1&&rows.length===100)shardCache.set(url,rows);return rows;}))).flat();}
  if(source.allowed_pairs&&index.records.some(r=>!source.allowed_pairs.includes(r.pair)))throw Error('Awaiting the corrected sample-budget publication');
  if(!indexOnly){index.records=index.records.filter(r=>r.completed_epoch<=data.generated_epoch);verify(data,index.records);}
  return {source,data,index,indexURL};
 }
 const api={sources,labels,order,names,canonical,members,pairID,normalizePair,byTime,pickSources,stats,view,rowsFor,build,decisionTiming,loadSource,verify};
 root.ArenaReporting=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);

