const assert=require('node:assert/strict');
const R=require('../reporting.js');
function input(name,bot,n,seconds){return {source:{name},data:{decision_timing:{by_bot:{[bot]:{decisions:n,total_seconds:seconds,forced_decisions:1,opening_lead:{decisions:1,total_seconds:seconds/2},play:{decisions:n-1,total_seconds:seconds/2}}}}}};}
const timing=R.decisionTiming([input('run A','Q',2,10),input('run B','4b',8,80),{source:{name:'missing'},data:{}}]);
assert.equal(timing.by_bot['4b'].decisions,10);
assert.equal(timing.by_bot['4b'].mean_seconds,9);
assert.equal(timing.by_bot['4b'].opening_lead.mean_seconds,22.5);
assert.equal(timing.by_bot['4b'].play.mean_seconds,45/8);
assert.deepEqual(timing.missing_sources,['missing']);
assert.deepEqual(R.decisionTiming([]).by_bot,{});
assert.equal(R.decisionTiming([input('BEN','ben',2,10)]).by_bot.ben.mean_seconds,5);
console.log('PASS decision-weighted averages, canonical bot names, phase counts and missing data');
