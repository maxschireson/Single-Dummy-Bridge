/* Global training history is independent of the selected arena cohort/window. */
(() => {
  const url = 'https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/research/direct-pairs-current/arena/global-stats.json';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number = value => Number.isFinite(value) ? value.toLocaleString() : 'Pending';
  const link = (label, target) => typeof target === 'string' && target.startsWith('https://github.com/maxschireson/Single-Dummy-Bridge/') ? '<a href="'+esc(target)+'" target="_blank" rel="noopener">'+esc(label)+'</a>' : esc(label);
  let stats = JSON.parse(document.getElementById('global-baseline').textContent);
  const section = document.getElementById('global-tracking');
  function card(label, metric) {
    return '<div class="card"><span class="muted">'+esc(label)+'</span><div class="big">'+number(metric?.value)+(metric?.coverage === 'lower_bound' ? '+' : '')+'</div><span class="muted">'+(metric?.coverage === 'lower_bound' ? 'Confirmed minimum' : 'Confirmed total')+'</span><details><summary>What counts</summary><p class="muted">'+esc(metric?.detail)+' '+link('Source',metric?.source_url)+'</p></details></div>';
  }
  function decisions(model) {
    const metric = model.decisions_seen;
    if (!metric || metric.value == null) return (model.training_summary ? esc(model.training_summary)+'<div class="muted">'+esc(model.training_base)+' · Decision count pending</div>' : 'Pending')+'<details><summary>What counts</summary><p class="muted">'+esc(metric?.detail || 'Training decision count has not been recorded for this checkpoint.')+'</p></details>';
    return number(metric.value)+(metric.coverage === 'lower_bound' ? '+' : '')+'<div class="muted">'+esc(metric.kind)+'</div><details><summary>What counts</summary><p class="muted">'+esc(metric.detail)+' '+link('Source',metric.source_url)+'</p></details>';
  }
  function validDecisions(metric) {
    return metric == null || (['decisions','observations','unseen-card observations'].includes(metric.kind) && metric.scope === 'latest_fit' &&
      (metric.coverage === 'pending' ? metric.value === null : ['exact','lower_bound'].includes(metric.coverage) && Number.isSafeInteger(metric.value) && metric.value >= 0));
  }
  function render() {
    section.innerHTML = '<h2>Global training &amp; models</h2><p class="muted">Across generations · independent of the match window · “+” means historical backfill is incomplete.</p><div class="cards">'+
      card('Bidding training boards',stats.training.bidding)+card('Play training boards',stats.training.play)+card('Policy audit lines tested',stats.policy_audit_lines)+'</div>'+
      '<p class="muted">Bidding supervision: '+number(stats.bidding_supervision?.dd_boards)+' DD boards · '+number(stats.bidding_supervision?.single_dummy_boards)+' single-dummy boards used in fitting. A board with both targets counts once in the total.</p>'+
      '<h3>Latest deployed component models</h3><div class="global-table"><table><thead><tr><th>Component</th><th>Model</th><th>Parameters</th><th>Training seen · latest fit</th><th>Used by</th></tr></thead><tbody>'+stats.models.map(m=>'<tr><td>'+esc(m.component)+'</td><td>'+link(m.name,m.source_url)+'</td><td>'+number(m.parameters)+'</td><td>'+decisions(m)+'</td><td>'+esc(({ 'bb46241ed4270ac171354ca9b7d5146bf532f50fc08370c5a5ee07461bbceedb':'Gen 3 · Gen 3-early', '8c62c88b0f2041ce78273e072d0b5530598255cc39b482826901ff1660e064f5':'Gen 3' })[m.sha256] || m.used_by)+'</td></tr>').join('')+'</tbody></table></div>'+
      '<p class="muted">Belief observations count each unseen-card ownership target at each recorded position. Policy counts action decisions. Counts exclude validation and repeated epochs. Bidding is fine-tuning of an inherited BEN model; earlier pretraining is additional. Pending does not mean zero.</p>'+
      '<p class="muted" id="global-status">Global summary: '+esc(stats.updated_utc)+' · '+esc(stats.coverage)+'</p>';
  }
  function valid(s) {
    const count = x => x && Number.isSafeInteger(x.value) && x.value >= 0 && ['exact','lower_bound'].includes(x.coverage);
    return s?.schema === 'bridge-global-tracking-v1' && Number.isFinite(Date.parse(s.updated_utc)) && count(s.training?.bidding) && count(s.training?.play) && count(s.policy_audit_lines) && Array.isArray(s.models) && s.models.length && s.models.every(m=>Number.isSafeInteger(m.parameters)&&m.parameters>=0&&validDecisions(m.decisions_seen)) && Array.isArray(s.generations);
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
