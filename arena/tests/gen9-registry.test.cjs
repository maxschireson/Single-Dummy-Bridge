const assert=require('node:assert');
// Generation 9 sources (13 November 2026: the Gen 9 cohort on azure4, run by Gen 9; registered by the operator). They are
// shown and selectable as ?source=gen9, but the default view stays Gen 8 until Max says otherwise.
const R=require('../reporting.js');const registry=require('../gen6-sources.json');
const gen9={key:'gen9test',group:'gen9',generation:9,variant:'9',environment:'azure',name:'Gen 9 · test feed',branch:'arena-gen9-test-feed',cohort:'b'.repeat(64)};
R.applyRegistry({...registry,sources:[...registry.sources,gen9]});
assert.equal(R.latestScope,'gen8','a Gen 9 source does not move the default view');
assert.equal(R.latestSource.group,'gen8');
assert.deepEqual(R.pickSources('gen9').map(s=>s.key).sort(),[...registry.sources.filter(s=>s.group==='gen9').map(s=>s.key),'gen9test'].sort(),'the Gen 9 rollup holds the Gen 9 sources');
assert.ok(registry.sources.some(s=>s.key==='gen9azure4'&&s.branch==='arena-gen9-azure4-feed'),'the azure4 Gen 9 cohort is registered');
assert.ok(!R.pickSources('latest').some(s=>s.group==='gen9'),'the default (Gen 8) rollup holds no Gen 9 source');
assert.equal(R.names.gen9,'Gen 9 · all collectors');
assert.deepEqual(R.resolveSelection('?source=gen9&older=1'),{selected:'gen9',older:true},'selectable like the other non-default rollups');
for(const bot of ['9a-32','8p-32'])assert.ok(R.labels[bot]&&R.order.includes(bot),bot+' has a label and a place in the order');
assert.deepEqual(R.members('9a-32~8s-32'),['9a-32','8s-32']);
// A Gen 9 record builds like a Gen 8 one, with the bidding/play split by contract.
const c=(x,d)=>({contract:x,declarer:d});
const row=(index,pair,common,own,contracts)=>({index,id:String(index),pair,family:'f'+index,imps:common,own_imps:own,scores:[0,0],contracts:[],own_contracts:contracts,completed_epoch:1,differences:{play:common,bidding:own-common,total:own},different_bidding:own!==common});
const input={source:R.sources.find(s=>s.key==='gen9test'),revision:'c'.repeat(40),data:{manifest_identity:'b'.repeat(64),generated_epoch:10,completed:3,target:10000,failures:0,order:R.order,own_views:{}},
  index:{records:[row(0,'9a-32~8s-32',1,2,[c('4S','N'),c('4S','N')]),row(1,'9a-32~8p-32',0,3,[c('3NT','S'),c('4S','N')]),row(2,'71s-32~9a-32',-2,-2,[c('2H','E'),c('2H','E')])]}};
const built=R.build([input],'gen9');const g=built.difference_views[0].groups;
assert.equal(g['9a-32~8s-32'].contract_play.total,2);assert.equal(g['9a-32~8p-32'].contract_bidding.total,3);
assert.ok(g['9a-32~71s-32'],'a pair is shown from the Gen 9 side');assert.equal(g['9a-32~71s-32'].contract_play.total,2);
assert.ok(/^Gen 9 candidate/.test(built.model_note||''),'Gen 9 model note');
console.log('PASS Gen 9 sources: registered and selectable, default view stays Gen 8, labels, contract split');
