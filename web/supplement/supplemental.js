/* Independent writers publish separate immutable cohorts. Never pool IMPs by label. */
(()=>{'use strict';
 const FEED='https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/arena-local-feed/arena/data.json';
 let supplemental=null,lastError='';window.arenaSupplementSelected=false;
 const section=document.createElement('section');section.id='arena-sources';
 section.innerHTML='<h2>Collection across environments</h2><p id="source-totals" aria-live="polite">Loading additional completed boards…</p><table><thead><tr><th>Environment</th><th>Completed boards</th><th>Recent boards/hour</th><th>Last publication</th></tr></thead><tbody id="source-rows"></tbody></table><p><label>Results and replays from <select id="arena-source"><option value="primary">Original arena</option><option value="supplement" disabled>ChatGPT environment</option></select></label></p><p class="muted">Counts below refer to the selected cohort. Fresh deal cohorts stay separate for IMP statistics; self-play counts toward collection but has no strength score.</p>';
 document.getElementById('cards').before(section);
 const selector=document.getElementById('arena-source');
 window.renderArenaSources=()=>{
   const sources=[['Original arena',PrimaryD],['ChatGPT environment',supplemental]];
   document.getElementById('source-rows').replaceChildren();
   for(const [name,data]of sources){const tr=document.createElement('tr');
     const age=data?.feed?.published_epoch?Date.now()/1000-data.feed.published_epoch:Infinity;
     const stale=age>(data?.feed?.interval_seconds||60)+180;
     const values=[name,data?data.completed.toLocaleString():'Pending first publication',data?(stale?'Snapshot: ':'')+Math.round(data.rates['5'].per_hour).toLocaleString()+(data.rates['5'].full_window?'':' (short window)'):'—',data?new Date((data.feed?.published_epoch||data.generated_epoch)*1000).toLocaleTimeString()+(stale?' · stale':''):'—'];
     for(const value of values){const td=document.createElement('td');td.textContent=value;tr.append(td);}document.getElementById('source-rows').append(tr);
   }
   const total=PrimaryD.completed+(supplemental?.completed||0);
   document.getElementById('source-totals').textContent=total.toLocaleString()+' completed boards across '+(supplemental?'both environments.':'the available feed.')+(lastError?' '+lastError:'');
   selector.options[1].disabled=!supplemental;
 };
 selector.addEventListener('change',()=>{window.arenaSupplementSelected=selector.value==='supplement';D=window.arenaSupplementSelected?supplemental:PrimaryD;renderAll();window.renderArenaSources();});
 async function refresh(){try{
   const response=await fetch(FEED+'?v='+Math.floor(Date.now()/30000),{cache:'no-store'});if(!response.ok)throw Error('HTTP '+response.status);
   const incoming=await response.json();
   if(!incoming.manifest_identity||!incoming.views?.['0']?.groups||!incoming.own_views||!Number.isFinite(incoming.completed))throw Error('Invalid supplemental snapshot');
   if(supplemental&&incoming.manifest_identity!==supplemental.manifest_identity)throw Error('Supplement cohort changed; reload');
   if(!supplemental||incoming.generated_epoch>=supplemental.generated_epoch){supplemental=incoming;if(window.arenaSupplementSelected){D=supplemental;renderAll();}}
   lastError='';
 }catch(error){lastError='Additional feed unavailable; retained the last published snapshot.';}window.renderArenaSources();}
 window.renderArenaSources();refresh();setInterval(refresh,30000);
})();
