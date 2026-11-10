/* Real elapsed decision latencies, weighted by the number of played decisions. */
(()=>{'use strict';
 const section=document.createElement('section');section.id='decision-timing';
 section.innerHTML='<p class="muted">Gen 5 round: 40% vs 4b, 20% vs Gen 3, 15% vs Gen 2, 5% vs Gen 1, 5% vs BEN, and 15% Gen 5 at 32 vs 192 samples. Gen 5 and older opponents both use 32. Gen 5 uses 192 only vs BEN (16) and Gen 5 (32).</p><h2>Average time per decision</h2><p class="muted">Wall-clock seconds for actual card decisions in root games, including forced moves. Opening leads and later play are shown separately. Training forks and replayed moves are excluded. Times depend on the host and include interface overhead.</p><table><thead><tr><th>Bot</th><th>Decisions</th><th>Average seconds</th><th>Opening lead</th><th>Later play</th></tr></thead><tbody id="decision-timing-rows"></tbody></table><p id="decision-timing-coverage" class="muted"></p>';
 document.getElementById('cards').after(section);
 const number=n=>n==null?'—':n.toLocaleString(undefined,{minimumFractionDigits:3,maximumFractionDigits:3});
 window.renderDecisionTiming=data=>{
  const timing=data.decision_timing||{by_bot:{},sources:[],missing_sources:[]},body=document.getElementById('decision-timing-rows');body.replaceChildren();
  const keys=[...new Set([...(data.order||[]),...Object.keys(timing.by_bot||{})])];
  for(const key of keys){const row=timing.by_bot?.[key],tr=document.createElement('tr');
   for(const value of [data.labels[key]||({'ben':'BEN','5':'Gen 5'})[key]||key,row?row.decisions.toLocaleString():'Not published',number(row?.mean_seconds),number(row?.opening_lead?.mean_seconds),number(row?.play?.mean_seconds)]){const td=document.createElement('td');td.textContent=value;tr.append(td);}body.append(tr);
  }
  document.getElementById('decision-timing-coverage').textContent=timing.sources?.length?'Measured in '+timing.sources.join(', ')+'.'+(timing.missing_sources?.length?' Timing is not yet published for '+timing.missing_sources.join(', ')+'.':''):'Decision timing will appear when a selected run publishes it.';
 };
 window.renderDecisionTiming(D);
})();
