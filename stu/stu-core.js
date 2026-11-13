/* Stu dashboard core: reads the rollout loop's published runs and reduces them to what the page shows, round by
   round. Shared by the page (browser) and build.cjs (Node), so a snapshot and a live reading go through the same code.
   What each run is comes from the loop's own run list (training/rollout-loop-20261113/runs.json on
   research/rollout-loop-20261113, see DASHBOARD.md there); the rows come from the boxes' transfer branches. */
(function (root) {
  'use strict';
  const REPO = 'maxschireson/Single-Dummy-Bridge';
  const rawURL = (branch, path) => `https://raw.githubusercontent.com/${REPO}/refs/heads/${branch}/${path}`;
  const treeURL = (branch, path = '') => `https://github.com/${REPO}/tree/${branch}${path ? '/' + path : ''}`;
  const commitsURL = branch => `https://api.github.com/repos/${REPO}/commits?sha=${encodeURIComponent(branch)}&per_page=1`;

  // ---- statistics ---------------------------------------------------------------------------------------------
  const T95 = [NaN, 12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160, 2.145,
    2.131, 2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042];
  function tcrit(df) {
    if (!(df >= 1)) return NaN;
    if (df <= 30) return T95[Math.floor(df)];
    const z = 1.959964;
    return z + (z ** 3 + z) / (4 * df) + (5 * z ** 5 + 16 * z ** 3 + 3 * z) / (96 * df ** 2);
  }
  function fromSums(n, sum, sq, won = 0, lost = 0, flat = 0) {
    if (!n) return { n: 0, mean: null, sd: null, se: null, ci: null, won, lost, flat };
    const mean = sum / n, variance = n > 1 ? Math.max(0, (sq - n * mean * mean) / (n - 1)) : null;
    const sd = variance === null ? null : Math.sqrt(variance), se = sd === null ? null : sd / Math.sqrt(n);
    const half = se === null ? null : tcrit(n - 1) * se;
    return { n, mean, sd, se, ci: half === null ? null : [mean - half, mean + half], won, lost, flat };
  }
  function stats(values) {
    const v = values.filter(Number.isFinite);
    return fromSums(v.length, v.reduce((a, b) => a + b, 0), v.reduce((a, b) => a + b * b, 0),
      v.filter(x => x > 0).length, v.filter(x => x < 0).length, v.filter(x => x === 0).length);
  }
  // Cumulative mean and 95% CI after each board, thinned to at most `points` points.
  function curve(values, points = 120) {
    const out = [], n = values.length, step = Math.max(1, Math.ceil(n / points));
    let s = 0, ss = 0;
    for (let i = 0; i < n; i++) {
      s += values[i]; ss += values[i] * values[i];
      const k = i + 1;
      if (k % step && k !== n) continue;
      const st = fromSums(k, s, ss);
      out.push({ boards: k, mean: st.mean, ci: st.ci });
    }
    return out;
  }

  // ---- what the boxes publish ---------------------------------------------------------------------------------
  // runs.log (training/rollout-loop-20261113/run.sh):
  //   2026-11-13T09:08:18Z start g0-stu0 stu0a~8p-32-v41 seed 131 first 0 deals 2000 workers 8 --opts (source 29d2e6a)
  //   2026-11-13T09:40:00Z end g0-stu0: exit 0
  const START = /^(\S+) start (\S+) (\S+) seed (\d+) first (\d+) deals (\d+) workers (\d+)\s*(.*?)\s*\(source ([0-9a-f]+)\)\s*$/;
  const END = /^(\S+) end (\S+): exit (\d+)/;
  const PAUSE = /^(\S+) the collection is paused/;
  const epoch = t => { const x = Date.parse(t); return Number.isFinite(x) ? x / 1000 : null; };
  function parseRunsLog(text, box) {
    const runs = {}, events = [];
    for (const line of String(text || '').split('\n')) {
      let m = START.exec(line.trim());
      if (m) {
        const [, t, name, pair, seed, first, deals, workers, options, source] = m;
        const r = runs[name] ||= { name, box, sources: [], starts: [], ends: [] };
        Object.assign(r, { pair, seed: +seed, first: +first, deals: +deals, workers: +workers, options: options || '' });
        if (!r.sources.includes(source)) r.sources.push(source);
        r.starts.push(epoch(t)); events.push({ t: epoch(t), name, kind: 'start', i: events.length });
        continue;
      }
      m = END.exec(line.trim());
      if (m && runs[m[2]]) {
        runs[m[2]].ends.push({ t: epoch(m[1]), exit: +m[3] });
        events.push({ t: epoch(m[1]), name: m[2], kind: 'end', exit: +m[3], i: events.length });
        continue;
      }
      m = PAUSE.exec(line.trim());
      if (m) events.push({ t: epoch(m[1]), kind: 'pause', i: events.length });
    }
    // A box runs one job at a time, or a few side by side started together (the collection's two runs). A run whose
    // last event is a start is running if it started within 90 s of the box's latest start and no pause came after it;
    // otherwise it was set aside (stopped by hand, paused for another job, or the chain moved on).
    const latestStart = events.filter(e => e.kind === 'start').reduce((a, e) => (!a || e.t >= a.t ? e : a), null);
    for (const r of Object.values(runs)) {
      const last = events.filter(e => e.name === r.name).at(-1);
      r.started = r.starts[0] ?? null;
      r.last_event = last ? last.t : null;
      const paused = last && events.some(e => e.kind === 'pause' && e.i > last.i);   // a pause logged after the run's start
      if (!last) r.status = 'unknown';
      else if (last.kind === 'end') { r.status = last.exit === 0 ? 'complete' : 'stopped'; r.exit = last.exit; }
      else r.status = latestStart && !paused && latestStart.t - last.t <= 90 ? 'running' : 'not running';
    }
    return runs;
  }
  function parseResults(text) {
    const rows = [];
    let bad = 0;
    for (const line of String(text || '').split('\n')) {
      if (!line.trim()) continue;
      try { rows.push(JSON.parse(line)); } catch (e) { bad++; }   // a line being written when the publisher copied it
    }
    return { rows, bad };
  }
  // <run>.log: "150 boards: 0.0467 +- 0.0869 IMPs/board for stu0a; 572 boards/hour; 0 failed" every 50 boards.
  // One table a board writes "None +- None" for the IMPs.
  const PROGRESS = /^(\d+) boards: (-?[\d.]+|None) \+- ([\d.]+|None) IMPs\/board for (\S+); ([\d.]+) boards\/hour; (\d+) failed/;
  function parseMatchLog(text) {
    let last = null, lines = 0;
    for (const line of String(text || '').split('\n')) {
      const m = PROGRESS.exec(line.trim());
      if (m) { lines++; last = { boards: +m[1], mean: m[2] === 'None' ? null : +m[2], se: m[3] === 'None' ? null : +m[3], bot: m[4], per_hour: +m[5], failed: +m[6] }; }
    }
    return last ? { ...last, lines } : null;
  }

  // ---- classification ----------------------------------------------------------------------------------------
  // From the loop's runs.json entry; a run it does not list is shown under other matches.
  const globToRegExp = g => new RegExp('^' + g.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\?/g, '.') + '$');
  // Bot ids the run list names, with what each is (family, round, net, rung).
  function botIds(runsList) {
    const ids = {};
    for (const e of runsList?.runs || []) {
      const [a, b] = String(e.pair || '').split('~');
      if (e.first_bot?.family === 'stu' && a) ids[a] ||= e.first_bot;
      if (b && e.second_bot?.family === 'stu') ids[b] ||= (e.second_bot.round != null ? e.second_bot : (e.role === 'collection' ? e.first_bot : null));
    }
    for (const k of Object.keys(ids)) if (!ids[k]) delete ids[k];
    return ids;
  }
  function classify(run, entry, registry, ids = null) {
    if ((registry.exclude_runs || []).some(g => globToRegExp(g).test(run.name))) return { role: 'excluded' };
    if (!entry) {
      // A run the list dropped (its job file moved on): read it by its bots, as superseded.
      const [a, b] = String(run.pair || '').split('~'), A = ids?.[a], B = ids?.[b];
      const train = registry.training_seeds || [], same = A && B && A.round === B.round && A.net === B.net && A.rung === B.rung;
      if (same && train.includes(run.seed)) return { role: 'collection', round: A.round, net: A.net, rung: A.rung, superseded: true, listed: false };
      if (A && run.seed === (registry.gate_seed ?? 131) && b === registry.opponent?.id)
        return { role: 'ladder', round: A.round, net: A.net, rung: A.rung, opponent: b, sign: 1, superseded: true, listed: false };
      return { role: 'other', listed: false };
    }
    const [a, b] = String(entry.pair || run.pair || '').split('~');
    const role = entry.role, fb = entry.first_bot || {}, sb = entry.second_bot || {};
    if (role === 'preflight') return { role: 'excluded' };
    const superseded = entry.queue_order == null, shelved = !!entry.shelved;
    if (role === 'ben') {
      const stu = fb.family === 'stu' ? fb : sb.family === 'stu' ? sb : null, first = fb.family === 'stu' || !stu;
      return { role, round: stu?.round ?? null, net: stu?.net ?? null, rung: stu?.rung ?? null, gen8: !stu,
        opponent: first ? b : a, sign: first ? 1 : -1, superseded, shelved, listed: true };
    }
    if (role === 'collection') return { role, round: fb.round, net: fb.net, rung: fb.rung, superseded, shelved, listed: true };
    if (role === 'gate' || role === 'ladder' || role === 'data') {
      const stuFirst = fb.family === 'stu';
      const bot = stuFirst ? fb : sb;
      return { role, round: bot.round, net: bot.net, rung: bot.rung, opponent: stuFirst ? b : a, sign: stuFirst ? 1 : -1,
        superseded, shelved, listed: true };
    }
    return { role: role || 'other', superseded, shelved, listed: true };
  }

  // ---- one run's rows, reduced ----------------------------------------------------------------------------------
  function contractClass(c) {
    const m = /^([1-7])(NT|N|S|H|D|C)/.exec(String(c || ''));
    if (!m) return '0';                                      // passed out
    const level = +m[1], strain = m[2];
    if (level >= 6) return 's';
    if ((strain[0] === 'N' && level >= 3) || ('SH'.includes(strain) && level >= 4) || ('DC'.includes(strain) && level >= 5)) return 'g';
    return 'p';
  }
  const X8_KEYS = ['rollout', 'blend', 'search', 'claim', 'consulted', 'moved', 'guaranteed', 'mixed', 'rollouts', 'net_rows', 'forks', 'seconds',
    'lead', 'lead_moved', 'lead_seconds'];
  // sign: +1 when the first-named bot is the one the run measures. Boards are kept (family, index, IMPs, contract
  // class) except for collections, whose IMPs are only a check and whose size would make the snapshot large.
  function reduceRun(rows, { sign = 1, keepBoards = true } = {}) {
    // rows: every board; n: boards with IMPs (a collection with one table a board has `common: null`).
    const out = { rows: 0, tables: 0, cpu: 0, cpu_n: 0, x8: null, x8_boards: 0, boards: keepBoards ? [] : null,
      sum: 0, sq: 0, won: 0, lost: 0, flat: 0, n: 0, max_index: null, classes: { p: 0, g: 0, s: 0, '0': 0 } };
    const side = sign > 0 ? 'candidate' : 'opponent';
    for (const r of rows) {
      out.rows++; out.tables += Number(r.tables) || 0;
      if (Number.isFinite(r.cpu)) { out.cpu += r.cpu; out.cpu_n++; }
      const x = r.search?.[side]?.x8;
      if (x) {
        out.x8 ||= Object.fromEntries(X8_KEYS.map(k => [k, 0]));
        for (const k of X8_KEYS) out.x8[k] += Number(x[k]) || 0;
        out.x8_boards++;
      }
      const imps = r.common == null ? NaN : sign * Number(r.common);
      if (!Number.isFinite(imps)) continue;
      out.n++; out.sum += imps; out.sq += imps * imps;
      if (imps > 0) out.won++; else if (imps < 0) out.lost++; else out.flat++;
      if (Number.isFinite(r.index)) out.max_index = Math.max(out.max_index ?? r.index, r.index);
      const cc = contractClass(r.contract);
      out.classes[cc]++;
      if (keepBoards) out.boards.push([String(r.family || r.index).slice(0, 16), r.index, imps, cc]);
    }
    out.cpu = Math.round(out.cpu * 10) / 10;
    if (out.x8) for (const k of X8_KEYS) out.x8[k] = Math.round(out.x8[k] * 1000) / 1000;
    return out;
  }
  const summaryOf = red => red ? fromSums(red.n, red.sum, red.sq, red.won, red.lost, red.flat) : fromSums(0, 0, 0);
  function addX8(acc, red) {
    if (!red?.x8) return acc;
    acc ||= Object.fromEntries(X8_KEYS.map(k => [k, 0]).concat([['boards', 0]]));
    for (const k of X8_KEYS) acc[k] += red.x8[k];
    acc.boards += red.x8_boards;
    return acc;
  }
  // The decision mix DASHBOARD.md asks for: per board, and moved over rollout decisions.
  function decisionMix(x8) {
    if (!x8 || !x8.boards) return null;
    return { boards: x8.boards, rollout: x8.rollout / x8.boards, blend: x8.blend / x8.boards, claim: x8.claim / x8.boards,
      moved: x8.rollout ? x8.moved / x8.rollout : null, rollouts: x8.consulted ? x8.rollouts / x8.consulted : null,
      net_rows: x8.consulted ? x8.net_rows / x8.consulted : null,
      lead: x8.lead ? x8.lead / x8.boards : null, lead_moved: x8.lead ? x8.lead_moved / x8.lead : null };
  }

  // ---- net scores from a trainer's metrics.json (scripts/train_rollout_net.py) ----------------------------------
  const pick = g => g ? Object.fromEntries(['n', 'nll', 'uniform_nll', 'agree', 'in_best', 'regret', 'rated_pick', 'regret_gap_head']
    .filter(k => g[k] !== undefined && g[k] !== null).map(k => [k, g[k]])) : null;
  const phases = g => g ? Object.fromEntries(Object.entries(g).map(([k, x]) => [k, pick(x)])) : null;
  // compare: {netKey: key under metrics.compared}, the other nets the trainer scored on this net's held-out rows.
  // before: {netKey: a metrics.json of the same rows scored by that net}, for an earlier net that `compared` reads
  // wrongly (round 1's v2 under `compared` reads Stu as an unknown bot; metrics_before.json tells it Stu is 8s-32).
  // focus: the bot whose rows matter most (round 1 on: the round's own Stu), scored from `by_bot`.
  function netMetrics(m, compare = {}, before = {}, focus = null) {
    if (!m || typeof m !== 'object') return null;
    const v = m.validation || {};
    const byBot = {};
    for (const [b, g] of Object.entries(v.by_bot || {})) byBot[b] = pick(g);
    const same = {};
    for (const [net, key] of Object.entries(compare || {})) {
      const c = m.compared?.[key];
      if (c) same[net] = { all: pick(c.all), late: pick(c.from_trick_7), focus: focus ? pick(c.by_bot?.[focus]) : null,
        focus_phase: focus ? phases(c.by_bot_phase?.[focus]) : null };
    }
    for (const [net, b] of Object.entries(before || {})) {
      const bv = b?.validation;
      if (bv) same[net] = { all: pick(bv.all), late: pick(bv.from_trick_7), focus: focus ? pick(bv.by_bot?.[focus]) : null,
        focus_phase: focus ? phases(bv.by_bot_phase?.[focus]) : null, before: true };
    }
    return {
      width: m.width ?? null, epochs: m.epochs ?? null, selected_epoch: m.selected_epoch ?? null, parameters: m.parameters ?? null,
      train_examples: m.train_examples ?? null, train_deals: m.train_deals ?? null, init: m.init ?? null, val_data: m.val_data ?? null,
      lr: m.lr ?? null, seconds: m.seconds ?? null,
      all: pick(v.all), late: pick(v.from_trick_7), declaring: pick(v.declaring), defending: pick(v.defending), by_bot: byBot,
      focus_bot: focus, focus: focus ? byBot[focus] || null : null, focus_phase: focus ? phases(v.by_bot_phase?.[focus]) : null,
      history: (m.history || []).map(h => ({ epoch: h.epoch, train_ce: h.train_ce ?? null, nll: h.val?.nll ?? null,
        agree: h.val?.agree ?? null, regret: h.val?.regret ?? null })),
      same_rows: same,
    };
  }

  // ---- the model the page draws ---------------------------------------------------------------------------------
  // runs: [{key, branch, box, name, pair, seed, first, deals, status, started, sources, cls, red, progress, episodes, note}]
  function mergeBoards(runs, keep = () => true) {
    // One board per deal family: runs still in a job file before superseded ones, earlier runs first.
    const sorted = runs.slice().sort((a, b) => (!!a.cls.superseded - !!b.cls.superseded) || ((a.started || 0) - (b.started || 0)));
    const seen = new Map();
    for (const r of sorted) for (const b of r.red?.boards || []) if (keep(b) && !seen.has(b[0])) seen.set(b[0], { b, sup: !!r.cls.superseded });
    const all = [...seen.values()].sort((x, y) => x.b[1] - y.b[1]);
    return { boards: all.map(x => x.b), superseded: all.filter(x => x.sup).length };
  }
  function cellOf(runs, { keep, deals } = {}) {
    const merged = mergeBoards(runs, keep), boards = merged.boards, s = stats(boards.map(b => b[2]));
    const live = runs.filter(r => !r.cls.superseded);
    const status = runs.some(r => r.status === 'running') ? 'running'
      : live.length && live.every(r => r.status === 'complete') ? 'complete'
      : live.some(r => r.status === 'pass done') ? 'pass done'
      : boards.length ? 'paused' : 'queued';
    return { runs: runs.map(r => r.key), boards, stats: s, deals: deals ?? (live.reduce((n, r) => n + (r.deals || 0), 0) || boards.length),
      status, superseded_boards: merged.superseded,
      x8: runs.reduce((acc, r) => addX8(acc, r.red), null),
      cpu: runs.reduce((a, r) => a + (r.red?.cpu || 0), 0) / Math.max(1, runs.reduce((a, r) => a + (r.red?.cpu_n || 0), 0)),
      by_class: Object.fromEntries(['p', 'g', 's'].map(c => [c, stats(boards.filter(b => b[3] === c).map(b => b[2]))])),
      curve: curve(boards.map(b => b[2])) };
  }
  // A minus B on the deal families both played (each against the same opponent, on the same seed).
  function paired(cellA, cellB) {
    if (!cellA || !cellB) return null;
    const mb = new Map(cellB.boards.map(b => [b[0], b[2]]));
    const d = cellA.boards.filter(b => mb.has(b[0])).map(b => b[2] - mb.get(b[0]));
    return d.length ? stats(d) : null;
  }

  // The fusion ledger (training/rollout-loop-20261113/fusion_ledger.py): per run, per bot, per contract class, how often
  // a declaring card gives up a contract the side held guaranteed (gave_up of held) and how often a defending card leaves
  // declarer a guarantee another card would not have (handed of choice).
  function ledgerModel(ledger, runs, primary) {
    if (!ledger?.runs) return null;
    const byName = new Map(runs.map(r => [r.name, r]));
    const rows = {}, add = (key, label, c) => {
      const row = rows[key] ||= { key, label, runs: 0, classes: {} };
      for (const [cls, v] of Object.entries(c || {})) {
        const t = row.classes[cls] ||= { tables: 0, held: 0, gave_up: 0, choice: 0, handed: 0, decl_unknown: 0, def_unknown: 0 };
        for (const k of Object.keys(t)) t[k] += Number(v[k]) || 0;
      }
    };
    for (const [name, r] of Object.entries(ledger.runs)) {
      const cls = byName.get(name)?.cls;
      for (const [bot, c] of Object.entries(r.bots || {})) {
        const key = bot === primary ? 'opp' : cls?.net && cls?.rung ? `${cls.net}|${cls.rung}` : 'bot:' + bot;
        add(key, bot, c);
        rows[key].runs++;
        if (key !== 'opp' && key !== rows[key].label) rows[key].net = cls?.net, rows[key].rung = cls?.rung;
      }
    }
    return { as_of: ledger.as_of || null, rows: Object.values(rows) };
  }

  function buildModel(registry, runs, metrics = {}, runsList = null, ledger = null) {
    const vseed = registry.gate_seed ?? 131, primary = registry.opponent?.id || '8p-32-v41';
    const gateDeals = registry.gate_deals ?? 2000;
    const rungOrder = (registry.rungs || []).map(r => r.key), netOrder = (registry.nets || []).map(n => n.key);
    const refOf = g => (registry.rungs || []).find(r => r.key === g)?.ref || 'stu';
    const byRole = role => runs.filter(r => r.cls.role === role);
    const stuVsOpp = runs.filter(r => ['gate', 'ladder'].includes(r.cls.role) && r.seed === vseed && r.cls.opponent === primary);
    const groups = {};
    for (const r of stuVsOpp) (groups[`${r.cls.net}|${r.cls.rung}`] ||= []).push(r);

    // The ladder: each net and rung on the deals its ladder runs plan (the union of their [first, first + deals));
    // boards of a gate run or a superseded run with the same bot count inside that range.
    const ladder = {};
    for (const [k, rs] of Object.entries(groups)) {
      const ranges = rs.filter(r => r.cls.role === 'ladder' && !r.cls.superseded && !r.cls.shelved && Number.isFinite(r.first) && Number.isFinite(r.deals)).map(r => [r.first, r.first + r.deals]);
      if (!ranges.length) continue;
      const inside = i => ranges.some(([a, b]) => i >= a && i < b);
      const size = new Set(ranges.flatMap(([a, b]) => Array.from({ length: b - a }, (_, x) => a + x))).size;
      ladder[k] = cellOf(rs, { keep: b => inside(b[1]), deals: size });
    }
    const seenNets = Object.keys(ladder).map(k => k.split('|')[0]), seenRungs = Object.keys(ladder).map(k => k.split('|')[1]);
    const nets = [...netOrder.filter(n => seenNets.includes(n)), ...[...new Set(seenNets)].filter(n => !netOrder.includes(n))];
    const rungs = [...rungOrder, ...[...new Set(seenRungs)].filter(g => !rungOrder.includes(g))];
    // Leverage: each loop net (variants left out) against the latest earlier net with at least 20 shared deals at a rung.
    const loopNets = (registry.nets || []).filter(n => !n.variant).map(n => n.key);
    const leverage = loopNets.slice(1).map((k, i) => {
      const prevNets = loopNets.slice(0, i + 1).reverse(), byRung = {};
      for (const g of [...rungOrder, ...[...new Set(seenRungs)].filter(x => !rungOrder.includes(x))]) {
        for (const e of prevNets) { const d = paired(ladder[`${k}|${g}`], ladder[`${e}|${g}`]); if (d && d.n >= 20) { byRung[g] = { d, vs: e }; break; } }
      }
      return { net: k, previous: loopNets[i], rungs: byRung };
    });
    const vsRef = {}, vsNet = {};
    for (const n of nets) for (const g of rungs) if (g !== refOf(g)) vsRef[`${n}|${g}`] = paired(ladder[`${n}|${g}`], ladder[`${n}|${refOf(g)}`]);
    for (let i = 1; i < nets.length; i++) for (const g of rungs)
      vsNet[`${nets[i]}|${nets[i - 1]}|${g}`] = paired(ladder[`${nets[i]}|${g}`], ladder[`${nets[i - 1]}|${g}`]);

    // Rounds: the round's collection, and its own net at each of the registry's round rungs on every gate deal played
    // (0 to gate_deals - 1), with the change from the previous round paired by deal.
    const roundRungs = registry.round_rungs || ['net', 'stu', 'pure'];
    const rounds = [];
    for (const g of registry.rounds || []) {
      const coll = byRole('collection').filter(r => r.cls.round === g.round).sort((a, b) => (a.started || 0) - (b.started || 0));
      const done = r => Math.max(r.red?.rows || 0, r.episodes || 0, r.progress?.boards || 0);
      const boards = coll.reduce((n, r) => n + done(r), 0);
      const running = coll.filter(r => r.status === 'running');
      const rate = running.reduce((a, r) => a + (r.progress?.per_hour || 0), 0);
      const listed = runsList?.rounds?.[String(g.round)];
      const cut = listed && 'collection_cut_boards' in listed ? listed.collection_cut_boards : (g.cut ?? null);
      const cells = {};
      for (const rung of roundRungs) {
        const rs = groups[`${g.net}|${rung}`];
        cells[rung] = rs ? cellOf(rs, { keep: b => b[1] < gateDeals, deals: gateDeals }) : null;
      }
      const prev = rounds.at(-1);
      // The change at each rung: against the latest earlier round with at least 20 deals in common at that rung (round 2's
      // rungs play deals 500 to 699, which round 1's did not, so its change is against Stu 0).
      const change = prev ? {} : null, changeVs = {};
      if (prev) for (const rung of roundRungs) {
        change[rung] = null;
        for (const e of rounds.slice().reverse()) {
          const d = paired(cells[rung], e.cells[rung]);
          if (d && d.n >= 20) { change[rung] = d; changeVs[rung] = e.label; break; }
        }
      }
      const x8 = coll.reduce((acc, r) => addX8(acc, r.red), null);
      const cpuN = coll.reduce((a, r) => a + (r.red?.cpu_n || 0), 0);
      const byRung = {};
      for (const r of coll) { const k = r.cls.rung || '?'; byRung[k] = (byRung[k] || 0) + done(r); }
      rounds.push({
        round: g.round, label: g.label, net: g.net, note: listed?.note || g.note || null, started: g.started || null, main_rung: g.main_rung || null,
        trained_on: g.trained_on || null, change_vs: changeVs,
        collection: { runs: coll.map(r => r.key), boards, by_rung: byRung, cut, rate: running.length ? rate : null,
          eta_hours: cut && rate > 0 && boards < cut ? (cut - boards) / rate : null,
          failed: coll.reduce((n, r) => n + (r.progress?.failed || 0), 0),
          status: running.length ? 'running' : coll.length ? 'not running' : 'not started',
          cpu: cpuN ? coll.reduce((a, r) => a + (r.red?.cpu || 0), 0) / cpuN : null, mix: decisionMix(x8) },
        cells, change, previous: prev ? prev.label : null,
        gate: cells.stu || null, gate_change: change?.stu || null,
        mix: Object.fromEntries(roundRungs.map(rung => [rung, cells[rung] ? decisionMix(cells[rung].x8) : null])),
      });
    }

    const netRows = (registry.nets || []).map(n => {
      const key = n.metrics ? `${n.metrics.branch}:${n.metrics.path}` : null;
      return { ...n, metrics_key: key, metrics: key ? metrics[key] || null : null };
    });

    // The leverage control (round README, "Measured before round 0"): a 2 by 2 from the box's 3,000-deal runs once they
    // have boards, else the sandbox's 300 deals.
    const C2 = registry.control || {};
    const controlCell = pair => {
      const box = runs.filter(r => r.pair === pair && r.box !== 'sandbox' && r.red?.n);
      const sand = runs.filter(r => r.pair === pair && r.box === 'sandbox' && r.red?.n);
      const use = box.length ? box : sand;
      return use.length ? { ...cellOf(use, { deals: Math.max(...use.map(r => r.deals || 0)) }), source: box.length ? use[0].box : 'sandbox' } : null;
    };
    const cells = Object.fromEntries(Object.entries(C2.cells || {}).map(([k, pair]) => [k, controlCell(pair)]));
    let split = null;
    if (['R41_N41', 'R4_N41', 'R41_N4', 'R4_N4'].every(k => cells[k])) {
      const maps = ['R41_N41', 'R4_N41', 'R41_N4', 'R4_N4'].map(k => new Map(cells[k].boards.map(b => [b[0], b[2]])));
      const fams = [...maps[0].keys()].filter(f => maps.every(m => m.has(f)));
      const d1 = fams.map(f => maps[0].get(f) - maps[1].get(f)), d2 = fams.map(f => maps[2].get(f) - maps[3].get(f));
      split = { matched: stats(d1), mismatched: stats(d2), quality: stats(d1.map((x, i) => (x + d2[i]) / 2)), exact: stats(d1.map((x, i) => (x - d2[i]) / 2)) };
    }
    const controlPairs = new Set(Object.values(C2.cells || {}));

    // Against BEN: each bot's result against BEN, minus Gen 8 card play's against BEN on the same deals, beside the bot's
    // own result against Gen 8 on those deals (the ladder's rows).
    const benRuns = byRole('ben').filter(r => r.red?.n);
    const benG8 = benRuns.filter(r => r.cls.gen8), g8cell = benG8.length ? cellOf(benG8) : null;
    const benRows = [];
    if (g8cell) benRows.push({ key: 'gen8', label: null, net: null, rung: null, cell: g8cell, minus_gen8: null, h2h: null });
    const benBots = {};
    for (const r of benRuns.filter(r => !r.cls.gen8)) (benBots[`${r.cls.net}|${r.cls.rung}`] ||= []).push(r);
    for (const [k, rs] of Object.entries(benBots)) {
      const c = cellOf(rs), [net, rung] = k.split('|'), deals = new Set(c.boards.map(b => b[0]));
      const h = groups[k] ? stats(mergeBoards(groups[k], b => deals.has(b[0])).boards.map(b => b[2])) : null;
      benRows.push({ key: k, net, rung, cell: c, minus_gen8: paired(c, g8cell), h2h: h && h.n ? h : null });
    }

    // What each box is doing now, and the collection's totals by box.
    const boxes = {};
    for (const r of runs.filter(r => r.box !== 'sandbox')) {
      const b = boxes[r.box] ||= { box: r.box, running: [], coll_rows: 0, coll_rate: 0, coll_running: 0 };
      const done = Math.max(r.red?.rows || 0, r.episodes || 0, r.progress?.boards || 0);
      if (r.cls.role === 'collection') { b.coll_rows += done; if (r.status === 'running') { b.coll_rate += r.progress?.per_hour || 0; b.coll_running++; } }
      if (r.status === 'running') {
        const rate = r.progress?.per_hour || null, left = Number.isFinite(r.deals) ? Math.max(0, r.deals - done) : null;
        b.running.push({ key: r.key, name: r.name, role: r.cls.role, net: r.cls.net, rung: r.cls.rung, pair: r.pair, done, deals: r.deals,
          rate, eta_hours: r.cls.role !== 'collection' && rate && left != null ? left / rate : null, failed: r.progress?.failed ?? null });
      }
    }
    const boxList = Object.values(boxes).sort((a, b) => a.box.localeCompare(b.box));
    const now = { boxes: boxList, coll_rows: boxList.reduce((a, b) => a + b.coll_rows, 0), coll_rate: boxList.reduce((a, b) => a + b.coll_rate, 0) };

    return {
      now, ben: benRows,
      rounds, round_rungs: roundRungs, nets: netRows, leverage, ladder_nets: nets, rungs, ladder, vs_ref: vsRef, ref_of: Object.fromEntries(rungs.map(g => [g, refOf(g)])), vs_net: vsNet,
      control: { cells, split, generation: paired(cells.F41_F4, cells.N41_N4) },
      data: byRole('data'), ledger: ledgerModel(ledger, runs, primary),
      others: runs.filter(r => (r.cls.role === 'other' || r.cls.role === 'control') && !controlPairs.has(r.pair) && r.red?.n),
      primary, vseed, gate_deals: gateDeals,
    };
  }

  // The run's planned deals are the run list's; a box may play them in passes (runs.json `passes`, e.g. 200 then 500),
  // so a job that ended at the end of a pass short of the plan is "pass done", not complete.
  function planRun(m, entry) {
    const planned = entry?.deals ?? m.deals, pass = m.deals;
    let status = m.status;
    if (status === 'complete' && entry && Number.isFinite(planned) && Number.isFinite(pass) && pass < planned) status = 'pass done';
    return { deals: planned, pass_deals: pass, passes: entry?.passes || null, status };
  }

  const api = { REPO, planRun, botIds, rawURL, treeURL, commitsURL, tcrit, stats, fromSums, curve, parseRunsLog, parseResults, parseMatchLog,
    classify, contractClass, reduceRun, summaryOf, decisionMix, netMetrics, mergeBoards, cellOf, paired, buildModel, ledgerModel, X8_KEYS };
  root.StuCore = api;
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window === 'undefined' ? globalThis : window);
