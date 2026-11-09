/* Global training history is independent of the selected arena cohort/window. */
(() => {
  const url = 'https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/research/direct-pairs-current/arena/global-stats.json';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number = value => Number.isFinite(value) ? value.toLocaleString() : 'Pending';
  const scientific = value => Number.isFinite(value) ? value.toExponential(3) : 'Pending';
  const link = (label, target) => typeof target === 'string' && target.startsWith('https://github.com/maxschireson/Single-Dummy-Bridge/') ? '<a href="'+esc(target)+'" target="_blank" rel="noopener">'+esc(label)+'</a>' : esc(label);
  let stats = JSON.parse(document.getElementById('global-baseline').textContent);
  const section = document.getElementById('global-tracking');
  function card(label, metric) {
    return '<div class="card"><span class="muted">'+esc(label)+'</span><div class="big">'+number(metric?.value)+(metric?.coverage === 'lower_bound' ? '+' : '')+'</div><span class="muted">'+(metric?.coverage === 'lower_bound' ? 'Confirmed minimum' : 'Confirmed total')+'</span><details><summary>What counts</summary><p class="muted">'+esc(metric?.detail)+' '+link('Source',metric?.source_url)+'</p></details></div>';
  }
  function render() {
    section.innerHTML = '<h2>Global training &amp; models</h2><p class="muted">Across generations · independent of the match window · “+” means historical backfill is incomplete.</p><div class="cards">'+
      card('Bidding training boards',stats.training.bidding)+card('Play training boards',stats.training.play)+card('Policy audit lines tested',stats.policy_audit_lines)+'</div>'+
      '<p class="muted">Bidding supervision: '+number(stats.bidding_supervision?.dd_boards)+' DD boards · '+number(stats.bidding_supervision?.single_dummy_boards)+' single-dummy boards used in fitting. A board with both targets counts once in the total.</p>'+
      '<h3>Latest deployed component models</h3><div class="global-table"><table><thead><tr><th>Component</th><th>Model</th><th>Parameters</th><th>Used by</th></tr></thead><tbody>'+stats.models.map(m=>'<tr><td>'+esc(m.component)+'</td><td>'+link(m.name,m.source_url)+'</td><td>'+number(m.parameters)+'</td><td>'+esc(m.used_by)+'</td></tr>').join('')+'</tbody></table></div>'+
      '<h3>Learning by generation</h3><p class="muted">Gain in IMPs per evaluation board, divided by new training work in 32-sample-equivalent paired boards. Evaluate both components at 32 samples, changing one component at a time. Partial audit continuations add fractional work.</p><div class="global-table"><table><thead><tr><th>Generation</th><th>Bidding IMP gain / normalized board</th><th>Play IMP gain / normalized board</th></tr></thead><tbody>'+stats.generations.map(g=>'<tr><td>'+esc(g.name)+'</td>'+['bidding','play'].map(k=>'<td>'+scientific(g.learning_efficiency?.[k]?.value)+(g.learning_efficiency?.[k]?.ci95 ? '<span class="ci">95% CI ['+g.learning_efficiency[k].ci95.map(scientific).join(', ')+']</span>' : '')+'</td>').join('')+'</tr>').join('')+'</tbody></table></div><p class="muted">Pending values need matched parent comparisons and recorded training work. Bidding needs a measured DDS-to-cardplay cost conversion.</p>'+
      '<p class="muted" id="global-status">Global summary: '+esc(stats.updated_utc)+' · '+esc(stats.coverage)+'</p>';
  }
  function valid(s) {
    const count = x => x && Number.isSafeInteger(x.value) && x.value >= 0 && ['exact','lower_bound'].includes(x.coverage);
    return s?.schema === 'bridge-global-tracking-v1' && Number.isFinite(Date.parse(s.updated_utc)) && count(s.training?.bidding) && count(s.training?.play) && count(s.policy_audit_lines) && Array.isArray(s.models) && s.models.length && s.models.every(m=>Number.isSafeInteger(m.parameters)&&m.parameters>=0) && Array.isArray(s.generations);
  }
  async function refresh() {
    try {
      const response = await fetch(url+'?v='+Math.floor(Date.now()/30000),{cache:'no-store'});
      if(!response.ok) throw Error('Unavailable');
      const incoming = await response.json();
      if(!valid(incoming)) throw Error('Invalid summary');
      if(Date.parse(incoming.updated_utc)>=Date.parse(stats.updated_utc)){stats=incoming;render();}
    } catch (_) {
      document.getElementById('global-status').textContent='Global summary: '+stats.updated_utc+' · Last verified snapshot; refresh unavailable. '+stats.coverage;
    }
  }
  render();
  if(location.protocol==='http:' || location.protocol==='https:'){refresh();setInterval(refresh,30000);}
})();
