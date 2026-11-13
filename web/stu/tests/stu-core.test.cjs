// node --test web/stu/tests/  (fixtures: rows, run logs and net scores cut from the loop's branches on 13 November)
'use strict';
const test = require('node:test'), assert = require('node:assert/strict'), path = require('path');
const C = require('../stu-core.js');
const FX = require('./fixtures.json');
const REG = require('../registry.json');
const close = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);

test('stats: mean, standard error and a t interval', () => {
  const s = C.stats([1, -1, 3, 0, 2]);
  assert.equal(s.n, 5); close(s.mean, 1);
  close(s.sd, Math.sqrt(2.5)); close(s.se, Math.sqrt(2.5 / 5));
  close(s.ci[1] - s.mean, 2.776 * Math.sqrt(0.5), 1e-9);
  assert.deepEqual([s.won, s.flat, s.lost], [3, 1, 1]);
  assert.equal(C.stats([]).mean, null);
});

test('curve ends at the full-sample statistics', () => {
  const v = [3, -2, 0, 5, 1, -1, 0, 2];
  const c = C.curve(v), s = C.stats(v);
  assert.equal(c.at(-1).boards, v.length); close(c.at(-1).mean, s.mean); close(c.at(-1).ci[0], s.ci[0], 1e-9);
  assert.ok(C.curve(Array(1000).fill(1)).length <= 121);
});

test('runs.log: a run that another job overtook on the same box is not running', () => {
  const r = C.parseRunsLog(FX.runs_log_azure3, 'azure3');
  assert.deepEqual(Object.keys(r).sort(), ['g0-stu0', 'g0-v2', 's0b']);
  assert.equal(r.s0b.status, 'running');
  assert.equal(r['g0-stu0'].status, 'set aside');
  assert.equal(r['g0-stu0'].seed, 131); assert.equal(r['g0-stu0'].deals, 2000); assert.deepEqual(r['g0-stu0'].sources, ['29d2e6a']);
  assert.equal(r.s0b.options, '--episodes'); assert.equal(r.s0b.first, 20000);
  const ended = C.parseRunsLog('2026-11-13T09:00:00Z start a x~y seed 131 first 0 deals 10 workers 8  (source abc1234)\n2026-11-13T09:30:00Z end a: exit 0\n', 'b');
  assert.equal(ended.a.status, 'complete');
  const stopped = C.parseRunsLog('2026-11-13T09:00:00Z start a x~y seed 131 first 0 deals 10 workers 8  (source abc1234)\n2026-11-13T09:30:00Z end a: exit 143\n', 'b');
  assert.equal(stopped.a.status, 'stopped'); assert.equal(stopped.a.exit, 143);
});

test('parseResults skips a line cut off by the publisher', () => {
  const text = JSON.stringify(FX.g0_stu0_rows[0]) + '\n' + JSON.stringify(FX.g0_stu0_rows[1]).slice(0, 40);
  const p = C.parseResults(text);
  assert.equal(p.rows.length, 1); assert.equal(p.bad, 1);
});

test('classify: self-play, validation (either order), aliases, controls, preflights', () => {
  const idx = C.botIndex(REG), run = (name, pair, seed) => C.classify({ name, pair, seed }, REG, idx);
  assert.deepEqual(run('s0', 'stu0a~stu0b', 9001), { kind: 'selfplay', round: 0, alias: false });
  assert.deepEqual(run('r0', 'z0a-v2~z0b-v2', 9001), { kind: 'selfplay', round: 0, alias: true });
  assert.deepEqual(run('g0-stu0', 'stu0a~8p-32-v41', 131), { kind: 'validation', round: 0, role: 'stu', opponent: '8p-32-v41', sign: 1, alias: false });
  assert.deepEqual(run('x', '8p-32-v41~n-stu0', 131), { kind: 'validation', round: 0, role: 'net', opponent: '8p-32-v41', sign: -1, alias: false });
  assert.equal(run('g', 'stu0a~8p-32-v41', 9001).kind, 'other');           // not the validation seed
  assert.equal(run('c-r7-n41', 'r7-v41~n-v41', 131).kind, 'other');        // the reference row's own control
  assert.equal(run('pf-gate', 'stu0a~8p-32-v41', 131).kind, 'excluded');
  const reg = { ...REG, generations: [...REG.generations, { round: 1, label: 'Stu 1', bots: { stu: ['stu1a', 'stu1b'] } }] };
  const h = C.classify({ name: 'h', pair: 'stu0a~stu1a', seed: 131 }, reg);
  assert.deepEqual(h, { kind: 'h2h', role: 'stu', newer: 1, older: 0, sign: -1, seed: 131, alias: false });
});

test('reduceRun orients IMPs to the round\'s bot and keeps deal families', () => {
  const rows = FX.g0_stu0_rows, red = C.reduceRun(rows, { kind: 'validation', sign: 1 });
  assert.equal(red.n, rows.length);
  close(red.imps_sum, rows.reduce((a, r) => a + r.common, 0));
  assert.equal(red.boards[0][0], rows[0].family.slice(0, 16)); assert.equal(red.boards[0][1], rows[0].index);
  assert.equal(red.x8_boards, rows.length);
  assert.equal(red.x8.rollout, rows.reduce((a, r) => a + r.search.candidate.x8.rollout, 0));
  const flipped = C.reduceRun(rows, { kind: 'validation', sign: -1 });
  close(flipped.imps_sum, -red.imps_sum);
  const sp = C.reduceRun(FX.s0_rows, { kind: 'selfplay' });
  assert.equal(sp.boards, null); assert.equal(sp.n, FX.s0_rows.length);
  const s = C.summaryOf(red), direct = C.stats(rows.map(r => r.common));
  close(s.mean, direct.mean); close(s.se, direct.se, 1e-9);
});

test('contract classes', () => {
  assert.deepEqual(['2S', '3NT', '4H', '4D', '5C', '6NT', '7SX', 'P', null, '3N'].map(C.contractClass), ['p', 'g', 'g', 'p', 'g', 's', 's', '0', '0', 'g']);
});

test('cells merge an old id\'s run with the new one, one board per family, the new id first', () => {
  const cls = { kind: 'validation', round: 0, role: 'stu', opponent: '8p-32-v41', sign: 1 };
  const old = { key: 'azure3/g0-v2', started: 1, cls: { ...cls, alias: true }, red: C.reduceRun(FX.g0_v2_rows, cls), status: 'set aside', deals: 2000 };
  const neu = { key: 'azure3/g0-stu0', started: 2, cls: { ...cls, alias: false }, red: C.reduceRun(FX.g0_stu0_rows, cls), status: 'set aside', deals: 2000 };
  const cell = C.cellOf([old, neu]);
  const fams = new Set([...FX.g0_v2_rows, ...FX.g0_stu0_rows].map(r => r.family.slice(0, 16)));
  assert.equal(cell.boards.length, fams.size);
  const firstNew = FX.g0_stu0_rows[0];
  assert.equal(cell.boards.find(b => b[0] === firstNew.family.slice(0, 16))[2], firstNew.common);
  assert.ok(cell.boards.every((b, i) => !i || cell.boards[i - 1][1] <= b[1]));
});

test('paired differences use shared deal families only', () => {
  const a = { boards: [['f1', 0, 3], ['f2', 1, -1], ['f3', 2, 0]] }, b = { boards: [['f2', 1, 1], ['f3', 2, 2], ['f4', 3, 9]] };
  const d = C.paired(a, b);
  assert.equal(d.n, 2); close(d.mean, -2);
  assert.equal(C.paired(a, null), null);
});

test('net metrics: this net and the previous one on the same rows', () => {
  const g = REG.generations.find(x => x.round === 0);
  const m = C.netMetrics(FX.metrics_v2, g);
  assert.equal(m.all.n, FX.metrics_v2.validation.all.n); close(m.all.nll, FX.metrics_v2.validation.all.nll);
  assert.equal(m.history.length, FX.metrics_v2.history.length);
  assert.ok(m.previous && m.previous.all.n === m.all.n, 'v4.1 scored on the same rows');
  close(m.previous.all.nll, FX.metrics_v2.compared[g.net.previous_compare].all.nll);
  assert.ok(m.late.n > 0 && m.by_bot['8s-32'].n > 0);
});

test('buildModel: round 0 from the fixtures', () => {
  const idx = C.botIndex(REG), runs = [];
  const add = (box, name, pair, seed, rows, status, started) => {
    const cls = C.classify({ name, pair, seed }, REG, idx);
    runs.push({ key: `${box}/${name}`, branch: 'b', box, name, pair, seed, deals: 2000, started, status, cls, red: C.reduceRun(rows, cls) });
  };
  add('azure3', 'g0-v2', 'z0a-v2~8p-32-v41', 131, FX.g0_v2_rows, 'set aside', 1);
  add('azure3', 'g0-stu0', 'stu0a~8p-32-v41', 131, FX.g0_stu0_rows, 'set aside', 2);
  add('azure5', 's0', 'stu0a~stu0b', 9001, FX.s0_rows, 'running', 3);
  add('sandbox', 'r7', 'r7-v41~n-v41', 131, FX.r7_rows, 'complete', 0);
  const g = REG.generations.find(x => x.round === 0), key = `${g.net.metrics.branch}:${g.net.metrics.path}`;
  const M = C.buildModel(REG, runs, { [key]: C.netMetrics(FX.metrics_v2, g) });
  const r0 = M.generations.find(x => x.round === 0);
  assert.equal(M.primary, '8p-32-v41');
  assert.ok(r0.cells['stu|8p-32-v41'].stats.n >= FX.g0_v2_rows.length);
  assert.equal(r0.cells['net|8p-32-v41'], null);
  assert.equal(r0.amplification.stu_over_net, null);
  assert.equal(r0.selfplay.boards, FX.s0_rows.length); assert.equal(r0.selfplay.status, 'running');
  assert.ok(r0.selfplay.x8.consulted > 0);
  assert.ok(r0.metrics && r0.metrics.all.nll > 0);
  assert.equal(M.others.length, 1);
  assert.equal(r0.previous_round, null, 'the reference row is not a previous round');
});

test('the page and the registry agree on roles and the primary opponent', () => {
  const fs = require('fs'), html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
  for (const r of REG.roles) assert.ok(/^[a-z]+$/.test(r.key) && html.includes(`${r.key}: 'var(--s`), r.key);
  assert.equal(REG.validation.opponents.filter(o => o.primary).length, 1);
  const ids = new Set();
  for (const g of REG.generations) for (const v of Object.values(g.bots)) for (const id of v) { assert.ok(!ids.has(id), 'bot in two rows: ' + id); ids.add(id); }
});
