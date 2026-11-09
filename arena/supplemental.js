/* Independent immutable cohorts. Never pool strength evidence by display label. */
(()=>{'use strict';
 const base='https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/';
 const feeds={recovery:{name:'Codex recovered six-bot mix',branch:'arena-recovery-feed',data:null},supplement:{name:'ChatGPT environment',branch:'arena-local-feed',data:null},components:{name:'Gen 4p / 4b component arena',branch:'arena-components-feed',data:null}};
 const desired=new URLSearchParams(location.search).get('source');let selected='primary',chosen=false;
 window.arenaSupplementSelected=false;
 const section=document.createElement('section');section.id='arena-sources';
 section.innerHTML='<h2>Collection across environments</h2><p id="source-totals" aria-live="polite">Loading completed boards…</p><table><thead><tr><th>Run</th><th>Completed boards</th><th>Recent boards/hour</th><th>Last publication</th></tr></thead><tbody id="source-rows"></tbody></table><p><label>Results and replays from <select id="arena-source"><option value="primary">Original arena</option><option value="supplement" disabled>ChatGPT environment</option><option value="recovery" disabled>Codex recovered six-bot mix</option><option value="components" disabled>Gen 4p / 4b component arena</option></select></label></p><p class="muted">Gen 4p uses the Gen 4 policy with Gen 3 belief and bidder. Gen 4b uses the Gen 4 belief with Gen 3 policy and bidder. Each upgrades one component. Common-auction and native-bidder results stay separate.</p>';
 document.getElementById('cards').before(section);const selector=document.getElementById('arena-source');
 function choose(key){selected=key;selector.value=key;window.arenaSupplementSelected=key!=='primary';D=key==='primary'?PrimaryD:feeds[key].data;renderAll();window.renderArenaSources();}
 window.renderArenaSources=()=>{
  const sources=[['Original arena',PrimaryD],...Object.values(feeds).map(f=>[f.name,f.data])];
  const tbody=document.getElementById('source-rows');tbody.replaceChildren();let total=0;
  for(const [name,data] of sources){const tr=document.createElement('tr');total+=data?.completed||0;
   const epoch=data?.feed?.published_epoch||data?.generated_epoch;
   const stale=!epoch||Date.now()/1000-epoch>(data?.feed?.interval_seconds||60)+180;
   const values=[name,data?data.completed.toLocaleString():'Pending first publication',data?(stale?'Snapshot: ':'')+Math.round(data.rates['5'].per_hour).toLocaleString():'—',data?new Date(epoch*1000).toLocaleTimeString()+(stale?' · stale':''):'—'];
   for(const value of values){const td=document.createElement('td');td.textContent=value;tr.append(td);}tbody.append(tr);
  }
  document.getElementById('source-totals').textContent=total.toLocaleString()+' completed run observations. Recovered-run deals overlap the original cohort; these are not distinct families across sources. Strength results remain separate by cohort.';
  for(const [key,f]of Object.entries(feeds))selector.querySelector('[value="'+key+'"]').disabled=!f.data;
 };
 selector.addEventListener('change',()=>{chosen=true;choose(selector.value);const u=new URL(location.href);u.searchParams.set('source',selector.value);history.replaceState(null,'',u);});
 async function refresh(){await Promise.allSettled(Object.entries(feeds).map(async([key,f])=>{
  const r=await fetch(base+f.branch+'/arena/data.json?v='+Math.floor(Date.now()/30000),{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);
  const incoming=await r.json();if(!incoming.manifest_identity||!incoming.views?.['0']?.groups||!Number.isFinite(incoming.completed))throw Error('Invalid feed');
  if(f.data&&incoming.manifest_identity!==f.data.manifest_identity)throw Error('Cohort changed; reload');
  if(!f.data||incoming.generated_epoch>=f.data.generated_epoch){f.data=incoming;if(selected===key){D=incoming;renderAll();}}
 }));window.renderArenaSources();if(!chosen&&desired&&feeds[desired]?.data){chosen=true;choose(desired);}}
 window.renderArenaSources();refresh();setInterval(refresh,30000);
})();
