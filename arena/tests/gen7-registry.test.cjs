const assert=require('node:assert/strict');
const R=require('../reporting.js'),registry=require('../gen6-sources.json');
R.applyRegistry(registry);
// Since 12 November 2026 the default view is Gen 8 (the arena switched, Max 16:11 UTC); the Gen 7 rollup is selected as gen7.
assert.equal(R.latestScope,'gen9');
assert.ok(R.pickSources('gen7').every(s=>s.generation===7));
assert.equal(R.sources.find(s=>s.key==='gen6newselfplay').revision,'6c7e9f612cd6f634ab6789f45def351edb4acba0');
assert.equal(R.sources.find(s=>s.key==='gen6newselfplay').retired,true);
const row=(index,pair,family,imps,epoch=1)=>({index,id:String(index),pair,family,imps,own_imps:imps+1,scores:[0,0],contracts:[],completed_epoch:epoch});
const input=(source,records)=>({source,revision:'a'.repeat(40),data:{manifest_identity:source.cohort,generated_epoch:10,completed:records.length,target:2000,failures:0,order:['7s-32','6-32','5RZ32','1'],own_views:{}},index:{records}});
const current=R.sources.find(s=>s.group==='gen7'&&!s.retired),original=input(current,[row(0,'7s-32~6-32','same',2),row(1,'7s-32~1','other',3)]);
const other={...current,key:'gen7second',branch:'arena-gen7-second-feed',cohort:'f'.repeat(64)};
R.applyRegistry({...registry,sources:[other,...registry.sources]});
const duplicate=input(other,[row(0,'6-32~7s-32','same',-999,2)]),old=input(R.sources.find(s=>s.key==='gen6newselfplay'),[row(2,'6-32~6-32','old',null)]);
const result=R.build([original,duplicate,old],'gen7');
assert.equal(result.completed,2);assert.equal(result.report.duplicates,1);
assert.equal(result.views[0].groups['7s-32~6-32'].total,2);
assert.equal(result.difference_views[0].groups['7s-32~6-32'].bidding.total,1);
assert.equal(result.views[0].groups['6-32~6-32'],undefined);
assert.equal(R.rowsFor([old],'gen6').rows.length,1,'Historical Gen6 remains available explicitly');
assert.deepEqual(R.resolveSelection('?source=gen6&older=1'),{selected:'gen6',older:true});
assert.throws(()=>R.applyRegistry({...registry,sources:[{...other,generation:6}]}),/Invalid/);
assert.equal(original.index.records[0].imps,2,'Raw observations stay untouched');
// A point release may publish under arena-gen71-...; the registry and the branch-head refresh accept one minor digit.
R.applyRegistry({...registry,sources:[{...other,key:'gen71point',branch:'arena-gen71-independent-feed',cohort:'e'.repeat(64)},...registry.sources]});
assert.throws(()=>R.applyRegistry({...registry,sources:[{...other,key:'gen71bad',branch:'arena-gen8-other-feed',cohort:'d'.repeat(64)}]}),/Invalid/);
R.applyRegistry(registry);
// Gen 7.1 (71s-32: Gen 7 standard with policy net v4.1) is listed ahead of Gen 7 and scored for 7.1 against 7.0, Gen 6 and BEN.
assert.equal(R.labels['71s-32'],'Gen 7.1 standard (32)');assert.equal(R.order[R.order.indexOf('8p-32')+1],'71s-32','Gen 7.1 right after the Gen 8 bots (8p-32, the Gen 9 control, is the last of them)');
const seven1=R.build([input(current,[row(0,'71s-32~7s-32','a',3),row(1,'7s-32~71s-32','b',-2,2),row(2,'71s-32~6-32','c',1),row(3,'71s-32~ben64','d',-1),row(4,'71s-32~71s-32','e',null)])],'gen7');
assert.equal(seven1.views[0].groups['71s-32~7s-32'].total,5,'A mirrored 7.0-led pair is flipped to 7.1');
assert.equal(seven1.views[0].groups['71s-32~6-32'].n,1);assert.equal(seven1.views[0].groups['71s-32~ben64'].total,-1);
assert.equal(seven1.views[0].groups['71s-32~71s-32'].total,null,'7.1 self-play has no score');
console.log('PASS Gen7 rollup excludes Gen6, deduplicates mirrored families, separates bidding, and preserves pinned archives');
assert.equal(R.labels['8s-32'],'Gen 8 candidate (32)');assert.equal(R.labels['8c-32'],'Gen 8 candidate, Precision rule bidder (32)');assert.ok(R.order.indexOf('9a-32')===0&&R.order.indexOf('stu4c-put')===1&&R.order.indexOf('stu3-ps')===2&&R.order.indexOf('8x3-32')===3&&R.order.indexOf('8s-32')===5&&R.order.indexOf('8c-32')===6,'the Gen 9 candidate, Gen X Stu (newest round first), then 8X and the Gen 8 bots, first');
const eight=R.build([input(current,[row(10,'8s-32~71s-32','f',4),row(11,'71s-32~8s-32','g',-1,2),row(12,'8c-32~8s-32','h',2),row(13,'8s-32~5RZ32','i',3),row(14,'8s-32~1','j',1),row(15,'8s-32~ben64','k',-2)])],'gen7');
assert.equal(eight.views[0].groups['8s-32~71s-32'].total,5,'A mirrored 7.1-led pair is flipped to Gen 8');assert.equal(eight.views[0].groups['8s-32~8c-32'].total,-2,'The Precision pair is shown from the standard Gen 8 side');assert.equal(eight.views[0].groups['8s-32~ben64'].total,-2);
