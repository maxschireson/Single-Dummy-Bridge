// node --test web/stu/tests/stu-core.test.cjs
// Fixtures: rows, run logs, the loop's runs.json and net scores cut from the loop's branches on 13 November 2026.
'use strict';
const test = require('node:test'), assert = require('node:assert/strict'), fs = require('fs'), path = require('path');
const C = require('../stu-core.js');
const { heartbeat } = require('../build.cjs');
const FX = require('./fixtures.json');
const REG = require('../registry.json');
const close = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);
const entries = new Map(FX.runs_json.runs.map(r => [r.name, r]));

test('stats: mean, standard error and a t interval', () => {
  const s = C.stats([1, -1, 3, 0, 2]);
  assert.equal(s.n, 5); close(s.mean, 1); close(s.sd, Math.sqrt(2.5)); close(s.se, Math.sqrt(0.5));
  close(s.ci[1] - s.mean, 2.776 * Math.sqrt(0.5));
  assert.deepEqual([s.won, s.flat, s.lost], [3, 1, 1]);
  assert.equal(C.stats([]).mean, null);
  const f = C.fromSums(5, 5, 15, 3, 1, 1); close(f.se, s.se);
});

test('curve ends at the full-sample statistics', () => {
  const v = [3, -2, 0, 5, 1, -1, 0, 2], c = C.curve(v), s = C.stats(v);
  assert.equal(c.at(-1).boards, v.length); close(c.at(-1).mean, s.mean); close(c.at(-1).ci[0], s.ci[0]);
  assert.ok(C.curve(Array(1000).fill(1)).length <= 121);
});

test('runs.log: a run another job overtook on its box is not running', () => {
  const r = C.parseRunsLog(FX.runs_log_azure3, 'azure3');
  assert.equal(r.s0b.status, 'running');
  assert.equal(r['g0-stu0'].status, 'not running');
  assert.equal(r['g0-stu0'].seed, 131); assert.equal(r['g0-stu0'].deals, 2000); assert.deepEqual(r['g0-stu0'].sources, ['29d2e6a']);
  assert.equal(r.s0b.options, '--episodes'); assert.equal(r.s0b.first, 20000);
  const line = '2026-11-13T09:00:00Z start a x~y seed 131 first 0 deals 10 workers 8  (source abc1234)\n';
  assert.equal(C.parseRunsLog(line + '2026-11-13T09:30:00Z end a: exit 0\n', 'b').a.status, 'complete');
  const st = C.parseRunsLog(line + '2026-11-13T09:30:00Z end a: exit 143\n', 'b').a;
  assert.equal(st.status, 'stopped'); assert.equal(st.exit, 143);
});

test('match log: the last progress line', () => {
  const p = C.parseMatchLog(FX.s0_log);
  assert.ok(p.boards >= 50 && p.per_hour > 0 && p.failed === 0 && p.bot === 'stu0a');
  assert.equal(C.parseMatchLog('stu0a v stu0b: 19000 boards to play (0 done), 8 workers\n'), null);
});

test('parseResults skips a line cut off by the publisher', () => {
  const p = C.parseResults(JSON.stringify(FX.g0_stu0_rows[0]) + '\n' + JSON.stringify(FX.g0_stu0_rows[1]).slice(0, 40));
  assert.equal(p.rows.length, 1); assert.equal(p.bad, 1);
});

test('classify from the loop\'s runs.json', () => {
  const cl = name => C.classify({ name }, entries.get(name) || null, REG);
  assert.deepEqual(cl('s0'), { role: 'collection', round: 0, net: 'v2', rung: 'stu', superseded: false, listed: true });
  assert.equal(cl('r0').superseded, true);
  const g = cl('g0-stu0');
  assert.equal(g.role, 'gate'); assert.equal(g.opponent, '8p-32-v41'); assert.equal(g.sign, 1); assert.equal(g.superseded, true);
  const l = cl('l0-v1-p');
  assert.deepEqual([l.role, l.net, l.rung, l.opponent, l.superseded], ['ladder', 'v1', 'pure', '8p-32-v41', false]);
  const d = cl('d0-p'); assert.deepEqual([d.role, d.rung, d.opponent], ['data', 'pure', 'stu0a']);
  assert.equal(cl('c-r7-n41').role, 'control');
  assert.equal(C.classify({ name: 'pf-gate' }, null, REG).role, 'excluded');
  assert.equal(C.classify({ name: 'r7', pair: 'r7-v41~n-v41' }, null, REG).role, 'other');
  // a Stu bot named second is measured from its own side
  const flipped = C.classify({ name: 'x' }, { role: 'ladder', pair: '8p-32-v41~stu0a', first_bot: { family: 'other' }, second_bot: { family: 'stu', round: 0, net: 'v2', rung: 'stu' }, queue_order: 1 }, REG);
  assert.deepEqual([flipped.sign, flipped.opponent, flipped.net], [-1, '8p-32-v41', 'v2']);
});

test('every run the loop lists is understood', () => {
  const roles = new Set(['collection', 'gate', 'ladder', 'data', 'control', 'excluded']);
  for (const e of FX.runs_json.runs) {
    const c = C.classify({ name: e.name }, e, REG);
    assert.ok(roles.has(c.role), e.name + ' ' + c.role);
    if (['gate', 'ladder', 'data'].includes(c.role)) assert.ok(REG.rungs.some(r => r.key === c.rung), 'rung ' + c.rung + ' in the registry');
    if (c.net) assert.ok(REG.nets.some(n => n.key === c.net), 'net ' + c.net + ' in the registry');
  }
});

test('reduceRun orients IMPs to the measured bot and keeps deal families', () => {
  const rows = FX.g0_stu0_rows, red = C.reduceRun(rows);
  assert.equal(red.n, rows.length); close(red.sum, rows.reduce((a, r) => a + r.common, 0));
  assert.deepEqual(red.boards[0].slice(0, 2), [rows[0].family.slice(0, 16), rows[0].index]);
  assert.equal(red.x8.rollout, rows.reduce((a, r) => a + r.search.candidate.x8.rollout, 0));
  close(C.reduceRun(rows, { sign: -1 }).sum, -red.sum);
  const sp = C.reduceRun(FX.s0_rows, { keepBoards: false });
  assert.equal(sp.boards, null); assert.equal(sp.n, FX.s0_rows.length);
  const s = C.summaryOf(red), direct = C.stats(rows.map(r => r.common));
  close(s.mean, direct.mean); close(s.se, direct.se);
  const mix = C.decisionMix({ ...red.x8, boards: red.x8_boards });
  close(mix.moved, red.x8.moved / red.x8.rollout); close(mix.rollout, red.x8.rollout / rows.length);
});

test('contract classes', () => {
  assert.deepEqual(['2S', '3NT', '4H', '4D', '5C', '6NT', '7SX', 'P', null, '3N'].map(C.contractClass), ['p', 'g', 'g', 'p', 'g', 's', 's', '0', '0', 'g']);
});

test('a cell counts a superseded run only where a current run has not played the deal', () => {
  const mk = (name, rows, status, started) => ({ key: 'azure3/' + name, started, status, cls: C.classify({ name }, entries.get(name), REG), red: C.reduceRun(rows) });
  const old = mk('g0-v2', FX.g0_v2_rows, 'not running', 1), neu = { ...mk('g0-stu0', FX.g0_stu0_rows, 'not running', 2), cls: { ...C.classify({ name: 'g0-stu0' }, entries.get('g0-stu0'), REG), superseded: false } };
  const cell = C.cellOf([old, neu], { deals: 2000 });
  const fams = new Set([...FX.g0_v2_rows, ...FX.g0_stu0_rows].map(r => r.family.slice(0, 16)));
  assert.equal(cell.boards.length, fams.size);
  const first = FX.g0_stu0_rows[0];
  assert.equal(cell.boards.find(b => b[0] === first.family.slice(0, 16))[2], first.common);
  const newFams = new Set(FX.g0_stu0_rows.map(r => r.family.slice(0, 16)));
  assert.equal(cell.superseded_boards, [...fams].filter(f => !newFams.has(f)).length);
  assert.ok(cell.boards.every((b, i) => !i || cell.boards[i - 1][1] <= b[1]));
  assert.equal(cell.deals, 2000);
});

test('paired differences use shared deal families only', () => {
  const d = C.paired({ boards: [['f1', 0, 3], ['f2', 1, -1], ['f3', 2, 0]] }, { boards: [['f2', 1, 1], ['f3', 2, 2], ['f4', 3, 9]] });
  assert.equal(d.n, 2); close(d.mean, -2);
  assert.equal(C.paired({ boards: [] }, null), null);
});

test('net metrics: own rows and the earlier nets on the same rows', () => {
  const v2 = REG.nets.find(n => n.key === 'v2'), m = C.netMetrics(FX.metrics_v2, v2.compare);
  close(m.all.nll, FX.metrics_v2.validation.all.nll); assert.equal(m.history.length, FX.metrics_v2.history.length);
  assert.deepEqual(Object.keys(m.same_rows).sort(), ['v1', 'v4.1']);
  assert.equal(m.same_rows.v1.all.n, m.all.n);
  close(m.same_rows['v4.1'].all.nll, FX.metrics_v2.compared[v2.compare['v4.1']].all.nll);
  assert.equal(C.netMetrics(null), null);
});

test('buildModel: round 0, the ladder and the control from the fixtures', () => {
  const runs = [];
  const add = (box, name, rows, status, started, extra = {}) => {
    const e = entries.get(name) || null, cls = C.classify({ name, pair: extra.pair }, e, REG);
    runs.push({ key: `${box}/${name}`, branch: 'b', box, name, pair: e?.pair || extra.pair, seed: e?.seed ?? 131, first: e?.first ?? 0,
      deals: e?.deals ?? 300, started, status, cls, red: rows ? C.reduceRun(rows, { sign: cls.sign || 1, keepBoards: cls.role !== 'collection' }) : null, ...extra });
  };
  add('azure3', 'g0-v2', FX.g0_v2_rows, 'not running', 1);
  add('azure3', 'g0-stu0', FX.g0_stu0_rows, 'not running', 2);
  add('azure3', 'l0-stu0', null, 'queued', null);
  add('azure5', 's0', FX.s0_rows, 'running', 3, { progress: { boards: 200, per_hour: 574, failed: 0 } });
  add('azure3', 's0b', FX.s0_rows.slice(0, 4), 'running', 4, { progress: { boards: 150, per_hour: 500, failed: 1 } });
  for (const [n, pair] of [['r7', 'r7-v41~n-v41'], ['r7x_v4', 'r7x-v4~n-v41'], ['c_r7_n4', 'r7-v41~n-v4'], ['c_r7x4_n4', 'r7x-v4~n-v4'], ['c_n41_n4', 'n-v41~n-v4']])
    add('sandbox', n, FX['sb_' + n], 'complete', 0, { pair });
  const v2 = REG.nets.find(n => n.key === 'v2');
  const M = C.buildModel(REG, runs, { [`${v2.metrics.branch}:${v2.metrics.path}`]: C.netMetrics(FX.metrics_v2, v2.compare) });
  const r0 = M.rounds[0];
  assert.equal(r0.collection.boards, 200 + 150); assert.equal(r0.collection.rate, 1074); assert.equal(r0.collection.failed, 1);
  close(r0.collection.eta_hours, (6000 - 350) / 1074);
  assert.ok(r0.collection.mix.rollout > 0);
  assert.equal(r0.gate.stats.n, new Set([...FX.g0_v2_rows, ...FX.g0_stu0_rows].map(r => r.family)).size);
  assert.equal(r0.gate.superseded_boards, r0.gate.stats.n, 'every gate board so far is from a superseded run');
  assert.equal(r0.gate_change, null);
  assert.ok(M.ladder['v2|stu'] && M.ladder['v2|stu'].boards.every(b => b[1] < 500));
  assert.deepEqual(M.ladder_nets, ['v2']);
  assert.ok(M.nets.find(n => n.key === 'v2').metrics);
  // control: the derived split agrees with direct pairing
  const K = M.control.cells, sp = M.control.split;
  assert.ok(K.R41_N41.source === 'sandbox' && sp);
  close(sp.matched.mean, C.paired(K.R41_N41, K.R4_N41).mean, 1e-9);
  close(sp.quality.mean, (sp.matched.mean + sp.mismatched.mean) / 2, 1e-9);
  assert.equal(M.others.length, 0);
});

test('heartbeat summary', () => {
  const h = heartbeat({ time: '2026-11-13T09:37:02Z', load: [8, 8, 8], cpus: 8, memory_mb: { MemAvailable: 100, MemTotal: 200 }, disk: { home: { free_gb: 5 } }, previous_push: { outcome: 'ok' } });
  assert.equal(h.time, Date.parse('2026-11-13T09:37:02Z') / 1000); assert.equal(h.mem_available_mb, 100); assert.equal(h.disk_free_gb, 5);
});

test('the registry: unique keys, one opponent, nets and rungs the page can colour', () => {
  assert.equal(new Set(REG.nets.map(n => n.key)).size, REG.nets.length);
  assert.equal(new Set(REG.rungs.map(r => r.key)).size, REG.rungs.length);
  assert.ok(REG.rungs.some(r => r.key === 'stu'));
  for (const r of REG.rounds) assert.ok(REG.nets.some(n => n.key === r.net), r.label);
  assert.ok(REG.nets.length <= 3, 'the page colours three nets (validated palette); fold older nets out or extend the palette check');
  const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
  assert.ok(html.includes("src=\"stu-core.js"));
});
