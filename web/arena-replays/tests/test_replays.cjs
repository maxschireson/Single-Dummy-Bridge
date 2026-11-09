const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../site/arena/replays');
const B = require(path.join(root, 'core.js'));
const catalog = JSON.parse(fs.readFileSync(path.join(root,'catalog.json')));
let boards=0,tables=0;const totals={AB:0,AC:0,BC:0};
for(const cohort of catalog.cohorts){
  const index=JSON.parse(fs.readFileSync(path.join(root,cohort.index_url)));
  assert.equal(index.records.length,cohort.count);
  for(const row of index.records){
    const records=JSON.parse(fs.readFileSync(path.join(root,path.dirname(cohort.index_url),row.shard)));
    const record=records[row.id];assert.equal(record.imps,row.imps);assert.equal(record.episode_sha256,row.episode_sha256);
    totals[row.pair]+=row.imps;boards++;
    for(const table of record.tables){
      const end=B.replay(record.board,table,52);
      assert(end.hands.every(h=>h.length===0));assert.equal(end.tricks[0]+end.tricks[1],13);
      assert.equal(end.tricks[B.seats.indexOf(B.tableBoard(record.board,table).declarer)%2],table.declarer_tricks);
      for(const ply of [0,1,4,5,26,51]){const s=B.replay(record.board,table,ply);assert.equal(s.hands.reduce((v,h)=>v+h.length,0),52-ply);assert.equal(s.history.length,Math.floor(ply/4));}
      tables++;
    }
    assert.equal(record.tables[0].ns_score,row.scores[0]);assert.equal(record.tables[1].ns_score,row.scores[1]);
  }
}
assert.equal(boards,465);assert.equal(tables,930);assert.deepEqual(totals,{AB:-122,AC:22,BC:-4});
assert.equal(B.firstDifference(['NSA'],['NSA']),null);
assert.equal(B.firstDifference(['NSA','ESK'],['NSA','ESH']),1);
console.log(JSON.stringify({boards,tables,totals,checks:'Legal play, ownership, follow suit, trick winners, final scores, partial states and identities verified'}));

// Different table contracts must affect trump and opening leader, not just labels.
const deal={hands:['A...2','K...3','.2..4','Q...5'],contract:'1N',declarer:'W',auction:['1N','P','P','P']};
const plays=['NSA','ESK','SC4','WSQ'];
assert.equal(B.replay(deal,{plays},4).history[0].winner,'N');
assert.equal(B.replay(deal,{plays,contract:'1C'},4).history[0].winner,'S');
assert.equal(B.replay(deal,{declarer:'N',plays:['ESK','SC4','WSQ','NSA']},4).history[0].winner,'N');
assert.deepEqual(B.tableBoard(deal,{auction:['1C','P','P','P']}).auction,['1C','P','P','P']);
console.log('Per-table contract, declarer, auction and legacy fallback verified');
