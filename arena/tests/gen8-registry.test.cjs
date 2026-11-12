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
// The bidding, play and total differences (supplemental.js) are computed for Gen 8 records as for Gen 7's and shown for a Gen 8 view.
const row8=(index,pair,family,imps,own,epoch=1)=>({index,id:String(index),pair,family,imps,own_imps:own,scores:[0,0],contracts:[],completed_epoch:epoch,differences:{play:imps,bidding:own-imps,total:own},different_bidding:own!==imps});
const input8=(source,records)=>({source,revision:'a'.repeat(40),data:{manifest_identity:source.cohort,generated_epoch:10,completed:records.length,target:2000,failures:0,order:['8s-32','8c-32','71s-32','5RZ32','1'],own_views:{}},index:{records}});
const built8=R.build([input8(R.latestSource,[row8(0,'8s-32~5RZ32','m',2,5),row8(1,'8c-32~8s-32','n',0,-4)])],'latest');
assert.equal(built8.difference_views[0].groups['8s-32~5RZ32'].bidding.total,3,'Gen 8 bidding difference: own-system auctions minus common auctions');
assert.equal(built8.difference_views[0].groups['8s-32~8c-32'].bidding.total,4,'the Precision pair, from the standard Gen 8 side');
assert.match(require('node:fs').readFileSync(__dirname+'/../supplemental.js','utf8'),/\[6,7,8\]\.includes\(s\.generation\)/,'the differences section is shown for Gen 8');
// Max, 18:03 UTC: compare play only in the same contract; different contracts are the bidding's. Same contract = same level,
// strain, doubling and declarer at the two own-system tables; the two parts are averaged over all boards and add to the total.
const c=(x,d)=>({contract:x,declarer:d});
const rowc=(index,pair,common,own,contracts)=>({...row8(index,pair,'c'+index,common,own),own_contracts:contracts});
const split=R.build([input8(R.latestSource,[rowc(20,'8c-32~8s-32',0,-3,[c('4S','N'),c('4S','N')]),rowc(21,'8c-32~8s-32',0,-6,[c('3NT','S'),c('4S','N')]),rowc(22,'8c-32~8s-32',0,2,[c('4S','N'),c('4S','S')])])],'latest').difference_views[0].groups['8s-32~8c-32'];
assert.equal(split.contracts_known,3);assert.equal(split.same_contract,1,'4S by N at both tables; 4S by N against 4S by S is not the same contract');
assert.equal(split.contract_play.total,3,'same contract: play, from the standard Gen 8 side');assert.equal(split.contract_bidding.total,4,'different contracts: bidding (6 - 2)');
assert.equal(split.contract_play.total+split.contract_bidding.total,split.contract_total.total);assert.equal(split.contract_play.n,3,'each part is averaged over all boards');
const none=R.build([input8(R.latestSource,[row8(30,'8s-32~1','z',1,2)])],'latest').difference_views[0].groups['8s-32~1'];
assert.equal(none.contracts_known,0,'a record without the own tables\' contracts is not classified');
console.log('PASS Gen 8 sources: default view, rollups, and bidding/play/total differences, split by contract');

