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
  const one = C.parseMatchLog('stu0-pra v stu0-prb: 20000 boards to play (0 done), 8 workers\n50 boards: None +- None IMPs/board for stu0-pra; 454 boards/hour; 0 failed\n');
  assert.deepEqual([one.boards, one.mean, one.se, one.per_hour], [50, null, null, 454]);
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
  for (const e of [...FX.runs_json.runs, ...FX.runs_json_1255.runs]) {
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
  const metrics = { [`${v2.metrics.branch}:${v2.metrics.path}`]: C.netMetrics(FX.metrics_v2, v2.compare) };
  const M = C.buildModel(REG, runs, metrics, { rounds: { 0: { collection_cut_boards: null, note: 'no count' } } });
  const r0 = M.rounds[0];
  assert.equal(r0.collection.boards, 200 + 150); assert.equal(r0.collection.rate, 1074); assert.equal(r0.collection.failed, 1);
  assert.equal(r0.collection.cut, null); assert.equal(r0.collection.eta_hours, null); assert.equal(r0.note, 'no count');
  const withCut = C.buildModel({ ...REG, rounds: [{ ...REG.rounds[0], cut: 6000 }] }, runs, metrics).rounds[0];
  close(withCut.collection.eta_hours, (6000 - 350) / 1074);
  assert.equal(C.buildModel(REG, runs, metrics, { rounds: { 0: { collection_cut_boards: 4000 } } }).rounds[0].collection.cut, 4000);
  assert.ok(r0.collection.mix.rollout > 0);
  assert.equal(r0.gate.stats.n, new Set([...FX.g0_v2_rows, ...FX.g0_stu0_rows].map(r => r.family)).size);
  assert.equal(r0.cells.stu, r0.gate); assert.equal(r0.cells.net, null);
  assert.equal(r0.gate.superseded_boards, r0.gate.stats.n, 'every gate board so far is from a superseded run');
  assert.equal(r0.change, null);
  assert.ok(M.ladder['v2|stu'] && M.ladder['v2|stu'].boards.every(b => b[1] < 500), 'l0-stu0 plans deals 0 to 499');
  assert.equal(M.ladder['v2|stu'].deals, 500);
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

test('passes: a job that ends short of the planned deals is a pass, not complete', () => {
  const e = entries.get('l0-stu0');
  assert.deepEqual(e.deals, 500);
  const done = C.planRun({ status: 'complete', deals: 200 }, { ...e, passes: [200, 500] });
  assert.deepEqual([done.status, done.deals, done.pass_deals], ['pass done', 500, 200]);
  assert.equal(C.planRun({ status: 'complete', deals: 500 }, e).status, 'complete');
  assert.equal(C.planRun({ status: 'running', deals: 200 }, e).status, 'running');
  assert.equal(C.planRun({ status: 'complete', deals: 300 }, null).status, 'complete');
  const mk = (st, n) => ({ key: 'k' + n, started: n, status: st, cls: { superseded: false }, red: C.reduceRun(FX.g0_stu0_rows.slice(0, 5)) });
  assert.equal(C.cellOf([mk('pass done', 1)], { deals: 500 }).status, 'pass done');
});

test('round 1 net: earlier nets from a before-file, and the round\'s own bot\'s rows', () => {
  const stu1 = REG.nets.find(n => n.key === 'stu1');
  assert.ok(stu1.before?.v2 && stu1.focus_bot === 'stu0');
  // a stand-in for train-r1/metrics.json: v2's file with a stu0 row added, and a before-file scored by v2
  const m = JSON.parse(JSON.stringify(FX.metrics_v2));
  m.validation.by_bot = { ...(m.validation.by_bot || {}), stu0: { n: 9000, nll: 0.85, agree: 0.66, regret: 0.03 } };
  const before = { validation: { all: { n: m.validation.all.n, nll: 0.6 }, by_bot: { stu0: { n: 9000, nll: 1.2, agree: 0.5, regret: 0.05 } } } };
  const out = C.netMetrics(m, stu1.compare, { v2: before }, 'stu0');
  assert.equal(out.focus.nll, 0.85); assert.equal(out.focus_bot, 'stu0');
  assert.equal(out.same_rows.v2.before, true); assert.equal(out.same_rows.v2.focus.nll, 1.2); assert.equal(out.same_rows.v2.all.nll, 0.6);
  assert.equal(C.netMetrics(m, stu1.compare, {}, 'stu0').same_rows.v2, undefined, 'v2 is not read from compared for round 1');
});

test('one table a board: rows count, CPU and decisions too, no IMPs', () => {
  const rows = FX.g0_stu0_rows.slice(0, 6).map(r => ({ ...r, common: null, tables: 1 }));
  const red = C.reduceRun(rows, { keepBoards: false });
  assert.equal(red.rows, 6); assert.equal(red.n, 0); assert.equal(red.tables, 6);
  assert.ok(red.cpu_n === 6 && red.x8_boards === 6);
  assert.equal(C.summaryOf(red).mean, null);
});

test('a run the list dropped is read by its bots (s0b, Stu-as-is self-play, after 12:05)', () => {
  const ids = C.botIds(FX.runs_json_1255);
  assert.ok(!FX.runs_json_1255.runs.some(e => e.name === 's0b'));
  assert.deepEqual([ids.stu0a.rung, ids.stu0b.rung, ids['stu0-pra'].rung, ids.stu1a.net], ['stu', 'stu', 'pure-rl', 'stu1']);
  const c = C.classify({ name: 's0b', pair: 'stu0a~stu0b', seed: 9001 }, null, REG, ids);
  assert.deepEqual([c.role, c.round, c.rung, c.superseded, c.listed], ['collection', 0, 'stu', true, false]);
  assert.equal(C.classify({ name: 'x', pair: 'stu0-p~8p-32-v41', seed: 131 }, null, REG, ids).role, 'ladder');
  assert.equal(C.classify({ name: 'y', pair: 'stu0a~ben', seed: 131 }, null, REG, ids).role, 'other');
});

test('the ladder takes its deals from its runs; the two lead rungs are compared with pure Stu', () => {
  const E = new Map(FX.runs_json_1255.runs.map(e => [e.name, e])), runs = [];
  const add = (name, rows) => { const e = E.get(name), cls = C.classify({ name }, e, REG);
    runs.push({ key: e.box + '/' + name, box: e.box, name, pair: e.pair, seed: e.seed, first: e.first, deals: e.deals, started: 1, status: 'running', cls, red: C.reduceRun(rows) }); };
  const base = FX.g0_stu0_rows, shift = (rows, k) => rows.map(r => ({ ...r, index: r.index + k, family: 'f' + (r.index + k) }));
  add('l0-stu0', shift(base, 0)); add('l0b-stu0', shift(base, 500)); add('l0-p', shift(base, 0).map(r => ({ ...r, common: r.common - 1 })));
  add('l0-pr', shift(base, 0).map(r => ({ ...r, common: r.common - 3 })));
  const M = C.buildModel(REG, runs, {}, FX.runs_json_1255);
  assert.equal(M.ladder['v2|stu'].deals, 1000); assert.equal(M.ladder['v2|stu'].stats.n, 2 * base.length);
  assert.equal(M.ladder['v2|pure'].deals, 500);
  assert.equal(M.ref_of['pure-rl'], 'pure'); assert.equal(M.ref_of.pure, 'stu');
  close(M.vs_ref['v2|pure-rl'].mean, -2); close(M.vs_ref['v2|pure'].mean, -1);
  const r0 = M.rounds[0];
  assert.equal(r0.cells.stu.stats.n, 2 * base.length); assert.equal(r0.cells.pure.stats.n, base.length);
  assert.equal(r0.main_rung, 'pure');
});

test('round over round: the change at each rung is paired by deal', () => {
  const reg = { ...REG, rounds: REG.rounds };
  const E = new Map(FX.runs_json_1255.runs.map(e => [e.name, e])), runs = [];
  const add = (name, d) => { const e = E.get(name), cls = C.classify({ name }, e, reg);
    runs.push({ key: name, box: e.box, name, pair: e.pair, seed: 131, first: e.first, deals: e.deals, started: 1, status: 'running', cls, red: C.reduceRun(FX.g0_stu0_rows.map(r => ({ ...r, common: r.common + d }))) }); };
  add('l0-n', 0); add('l1-n', 0.5); add('l0-p', 0); add('l1-p', 1);
  const M = C.buildModel(reg, runs, {}, FX.runs_json_1255), r1 = M.rounds.find(r => r.round === 1);
  close(r1.change.net.mean, 0.5); close(r1.change.pure.mean, 1); assert.equal(r1.change.stu, null);
  assert.ok(M.vs_net['stu1|v2|pure'] && Math.abs(M.vs_net['stu1|v2|pure'].mean - 1) < 1e-9);
});

test('fusion ledger: pooled by net and rung, the opponent pooled across runs', () => {
  const E = new Map(FX.runs_json_1255.runs.map(e => [e.name, e]));
  const runs = ['l0-stu0', 'l0-p', 'l0-n'].map(name => ({ name, cls: C.classify({ name }, E.get(name), REG) }));
  const L = C.ledgerModel(FX.ledger, runs, '8p-32-v41');
  const opp = L.rows.find(r => r.key === 'opp'), pure = L.rows.find(r => r.key === 'v2|pure');
  const want = ['l0-stu0', 'l0-p', 'l0-n'].reduce((a, k) => a + FX.ledger.runs[k].bots['8p-32-v41'].all.gave_up, 0);
  assert.equal(opp.classes.all.gave_up, want); assert.equal(opp.runs, 3);
  assert.equal(pure.classes.all.held, FX.ledger.runs['l0-p'].bots['stu0-p'].all.held);
  assert.equal(C.ledgerModel(null, runs, 'x'), null);
});
