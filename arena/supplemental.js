/* Main and component runs share reporting; collectors retain their own manifests. */
(()=>{'use strict';
 const R=ArenaReporting,inputs=new Map(),errors=new Map();let busy=false,selected=new URLSearchParams(location.search).get('source')||'all';
 if(!['all','chatgpt','codex',...R.sources.map(s=>s.key)].includes(selected))selected='all';
 window.arenaSupplementSelected=true;
 const section=document.createElement('section');section.id='arena-sources';
 section.innerHTML='<h2>Collection across all four streams</h2><p id="source-totals" aria-live="polite">Loading main and component results…</p><table><thead><tr><th>Environment</th><th>Paired boards</th><th>Collected observations</th><th>Recent observations/hour</th></tr></thead><tbody id="source-rows"></tbody></table><p><label>Report <select id="arena-source"><option value="all">All streams (rollup)</option><option value="chatgpt">ChatGPT · main + 4p / 4b</option><option value="codex">Codex · main + 4p / 4b</option><optgroup label="Individual runs"><option value="primary">Codex main only</option><option value="recovery">Codex six-bot mix only</option><option value="supplement">ChatGPT main only</option><option value="components">ChatGPT 4p / 4b only</option></optgroup></select></label></p><p id="source-status" class="muted" aria-live="polite"></p><details><summary>Run publications and provenance</summary><p id="run-publications" class="muted"></p></details>';
 document.getElementById('cards').before(section);const selector=document.getElementById('arena-source');selector.value=selected;
 const windows=document.getElementById('window');for(const option of windows.options){if(option.value!=='0')option.textContent='Last '+Number(option.value).toLocaleString()+' completed per matchup';}
 function report(){const available=[...inputs.values()],wanted=R.pickSources(selected),missing=wanted.filter(s=>!inputs.has(s.key));
  D=R.build(available,selected);renderAll();
  const tbody=document.getElementById('source-rows');tbody.replaceChildren();
  for(const scope of ['chatgpt','codex']){const has=available.some(x=>x.source.environment===scope),data=has?R.build(available,scope):null,tr=document.createElement('tr');
   const values=[R.names[scope],data?data.completed.toLocaleString():'Loading…',data?data.report.observations.toLocaleString():'—',data?Math.round(data.rates['5'].per_hour).toLocaleString():'—'];for(const value of values){const td=document.createElement('td');td.textContent=value;tr.append(td);}tbody.append(tr);}
  if(available.length){const all=R.build(available);document.getElementById('source-totals').textContent=all.report.sources.length+' of 4 streams · '+all.report.observations.toLocaleString()+' collected observations · '+all.completed.toLocaleString()+' paired boards after deduplication · '+all.report.families.toLocaleString()+' distinct deal families · '+all.report.duplicates.toLocaleString()+' repeated family/matchup observations counted once.';}
  const issues=wanted.filter(s=>errors.has(s.key)).map(s=>s.name+': '+errors.get(s.key));
  document.getElementById('source-status').textContent=(missing.length?'Partial report — awaiting '+missing.map(s=>s.name).join(', ')+'. ':'')+(issues.length?'Refresh delayed; retaining the last verified snapshots. '+issues.join(' · '):'Main and component results are integrated. Live scores refresh every 30 seconds; every score links to its contributing play records.');
  document.getElementById('run-publications').textContent=R.sources.map(s=>{const x=inputs.get(s.key);if(!x)return s.name+': pending';const epoch=x.data.feed?.published_epoch||x.data.generated_epoch;return s.name+': '+x.data.completed.toLocaleString()+' observations · '+new Date(epoch*1000).toLocaleTimeString()+(Date.now()/1000-epoch>240?' · stale':'');}).join(' | ');
 }
 selector.addEventListener('change',()=>{selected=selector.value;const u=new URL(location.href);u.searchParams.set('source',selected);history.replaceState(null,'',u);report();});
 async function refresh(){if(busy)return;busy=true;try{await Promise.allSettled(R.sources.map(async source=>{try{const incoming=await R.loadSource(source);const previous=inputs.get(source.key);if(!previous||incoming.data.generated_epoch>=previous.data.generated_epoch)inputs.set(source.key,incoming);errors.delete(source.key);}catch(e){errors.set(source.key,e.message);}}));report();}finally{busy=false;}}
 window.renderArenaSources=()=>{};report();refresh();setInterval(refresh,30000);
})();

