const assert=require('node:assert/strict');
const path=require('node:path');
const R=require(path.resolve(process.argv[2],'arena/reporting.js'));
const row=(id,pair,imps)=>({id,index:Number(id),family:'family-'+id,pair,imps,own_imps:imps,
  scores:[0,0],contracts:[],completed_epoch:10});
const input=(key,records)=>({source:R.sources.find(s=>s.key===key),
  data:{generated_epoch:100,target:records.length,failures:0,order:['5R32','5R192','5-32','4b','ben'],own_views:{}},index:{records}});
const current=input('gen5r',[row('1','5R32~5R192',3),row('2','5R32~5-32',-4),row('3','5R192~ben',5)]);
const old=input('gen5',[row('4','5~5-32',100)]);
const all=[old,current];
assert.deepEqual(R.pickSources('gen5r').map(x=>x.key),['gen5r']);
assert.ok(!R.pickSources('gen5').some(x=>x.key==='gen5r'));
assert.ok(old.source.retired);
const report=R.build(all,'gen5r',null,100);
assert.equal(report.completed,3);
assert.equal(report.views[0].groups['5R32~5R192'].total,3);
assert.equal(report.views[0].groups['5R32~5-32'].total,-4);
assert.equal(report.views[0].groups['5R192~ben'].total,5);
assert.equal(report.views[0].groups['5~5-32'],undefined);
assert.equal(R.rowsFor(all,'gen5r','common',report.report.snapshots).rows.length,3);
assert.equal(R.build(all,'gen5',null,100).completed,1);
assert.equal(R.build(all,'all',null,100).completed,4);
console.log('PASS Gen5R isolation, matchup orientation, original Gen5 archive and exact replay rows');
