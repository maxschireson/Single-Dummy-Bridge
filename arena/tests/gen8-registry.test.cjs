const assert=require('node:assert');
// Generation 8 sources (12 November 2026: the arena goes to Gen 8, Max 15:32 and 16:11 UTC). They are registered like
// Gen 7's; once one is live the default view follows it, and the Gen 7 rollup stays selectable.
const R=require('../reporting.js');const registry=require('../gen6-sources.json');
assert.equal(R.latestScope,'gen7');
const gen8={key:'gen8test',group:'gen8',generation:8,variant:'8',environment:'azure',name:'Gen 8 · test feed',branch:'arena-gen8-test-feed',cohort:'a'.repeat(64)};
R.applyRegistry({...registry,sources:[...registry.sources,gen8]});
assert.equal(R.latestScope,'gen8','the default view follows the newest generation with a live source');
assert.equal(R.latestSource.key,'gen8test');assert.equal(R.names.latest,'Gen 8 · all collectors');
assert.ok(R.pickSources('latest').some(s=>s.key==='gen8test'));assert.ok(!R.pickSources('latest').some(s=>s.group==='gen7'),'the Gen 8 rollup holds Gen 8 sources only');
assert.ok(R.pickSources('gen7').length>0&&R.pickSources('gen7').every(s=>s.group==='gen7'),'the Gen 7 rollup stays selectable');
assert.deepEqual(R.resolveSelection('?source=gen7&older=1'),{selected:'gen7',older:true});
assert.throws(()=>R.applyRegistry({...registry,sources:[...registry.sources,{...gen8,key:'bad',cohort:'b'.repeat(64),branch:'arena-gen7-bad-feed'}]}),/Invalid/,'a Gen 8 source must have a Gen 8 branch name');
