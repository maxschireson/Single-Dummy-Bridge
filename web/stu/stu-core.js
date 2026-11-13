/* Stu dashboard core: reads the rollout loop's published runs, sorts them into generations and roles, and computes
   paired statistics and net scores. Shared by the page (browser) and build.cjs (Node), so a snapshot and a live
   reading are reduced by the same code. */
(function (root) {
  'use strict';
  const REPO = 'maxschireson/Single-Dummy-Bridge';
  const rawURL = (branch, path) => `https://raw.githubusercontent.com/${REPO}/refs/heads/${branch}/${path}`;
  const treeURL = (branch, path = '') => `https://github.com/${REPO}/tree/${branch}${path ? '/' + path : ''}`;

  // ---- statistics ---------------------------------------------------------------------------------------------
  const T95 = [NaN, 12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160, 2.145,
    2.131, 2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042];
  function tcrit(df) {
    if (!(df >= 1)) return NaN;
    if (df <= 30) return T95[Math.floor(df)];
    const z = 1.959964;
    return z + (z ** 3 + z) / (4 * df) + (5 * z ** 5 + 16 * z ** 3 + 3 * z) / (96 * df ** 2);
  }
  function stats(values) {
    const v = values.filter(Number.isFinite), n = v.length;
    if (!n) return { n: 0, mean: null, sd: null, se: null, ci: null, won: 0, lost: 0, flat: 0 };
    const mean = v.reduce((a, b) => a + b, 0) / n;
    const sd = n > 1 ? Math.sqrt(v.reduce((s, x) => s + (x - mean) ** 2, 0) / (n - 1)) : null;
    const se = sd === null ? null : sd / Math.sqrt(n);
    const half = se === null ? null : tcrit(n - 1) * se;
    return { n, mean, sd, se, ci: half === null ? null : [mean - half, mean + half],
      won: v.filter(x => x > 0).length, lost: v.filter(x => x < 0).length, flat: v.filter(x => x === 0).length };
  }
  // Cumulative mean and 95% CI after each board, thinned to at most `points` points.
  function curve(values, points = 120) {
    const out = [], n = values.length, step = Math.max(1, Math.ceil(n / points));
    let s = 0, ss = 0;
    for (let i = 0; i < n; i++) {
      s += values[i]; ss += values[i] * values[i];
      const k = i + 1;
      if (k % step && k !== n) continue;
      const mean = s / k, variance = k > 1 ? Math.max(0, (ss - k * mean * mean) / (k - 1)) : null;
      const se = variance === null ? null : Math.sqrt(variance / k), half = se === null ? null : tcrit(k - 1) * se;
      out.push({ boards: k, mean, ci: half === null ? null : [mean - half, mean + half] });
    }
    return out;
  }

  // ---- runs.log -----------------------------------------------------------------------------------------------
  // Lines written by training/rollout-loop-20261113/run.sh:
  //   2026-11-13T09:08:18Z start g0-stu0 stu0a~8p-32-v41 seed 131 first 0 deals 2000 workers 8 --opts (source 29d2e6a)
  //   2026-11-13T09:40:00Z end g0-stu0: exit 0
  const START = /^(\S+) start (\S+) (\S+) seed (\d+) first (\d+) deals (\d+) workers (\d+)\s*(.*?)\s*\(source ([0-9a-f]+)\)\s*$/;
  const END = /^(\S+) end (\S+): exit (\d+)/;
  const epoch = t => { const x = Date.parse(t); return Number.isFinite(x) ? x / 1000 : null; };
  function parseRunsLog(text, box) {
    const runs = {}, events = [];
    for (const line of String(text || '').split('\n')) {
      let m = START.exec(line.trim());
      if (m) {
        const [, t, name, pair, seed, first, deals, workers, options, source] = m;
        const r = runs[name] ||= { name, box, pair, seed: +seed, first: +first, deals: +deals, workers: +workers,
          options: options || '', sources: [], starts: [], ends: [] };
        Object.assign(r, { pair, seed: +seed, first: +first, deals: +deals, workers: +workers, options: options || '' });
        if (!r.sources.includes(source)) r.sources.push(source);
        r.starts.push(epoch(t)); events.push({ t: epoch(t), name, kind: 'start' });
        continue;
      }
      m = END.exec(line.trim());
      if (m && runs[m[2]]) {
        runs[m[2]].ends.push({ t: epoch(m[1]), exit: +m[3] });
        events.push({ t: epoch(m[1]), name: m[2], kind: 'end', exit: +m[3] });
      }
    }
    // A box runs its jobs one after another: a run whose last event is a start is running only if no other run
    // started after it on that box; otherwise it was set aside and resumes later in the chain.
    const latestStart = events.filter(e => e.kind === 'start').reduce((a, e) => (!a || e.t >= a.t ? e : a), null);
    for (const r of Object.values(runs)) {
      const last = events.filter(e => e.name === r.name).at(-1);
      r.started = r.starts[0];
      r.last_event = last ? last.t : null;
      if (!last) r.status = 'unknown';
      else if (last.kind === 'end') r.status = last.exit === 0 ? 'complete' : 'stopped';
      else r.status = latestStart && latestStart.name === r.name ? 'running' : 'set aside';
      if (last && last.kind === 'end') r.exit = last.exit;
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

  // ---- classification -----------------------------------------------------------------------------------------
  const globToRegExp = g => new RegExp('^' + g.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\?/g, '.') + '$');
  function botIndex(registry) {
    const idx = {};
    for (const g of registry.generations || []) {
      const aliases = g.aliases || {};
      for (const [role, ids] of Object.entries(g.bots || {}))
        for (const id of ids) idx[id] = { round: g.round, role, alias: false, canonical: id };
      for (const [old, canonical] of Object.entries(aliases)) {
        const c = idx[canonical];
        if (c) idx[old] = { ...c, alias: true, canonical };
      }
    }
    return idx;
  }
  const roundOrder = (registry, r) => (registry.generations || []).findIndex(g => g.round === r);
  function classify(run, registry, idx = botIndex(registry)) {
    if ((registry.exclude_runs || []).some(g => globToRegExp(g).test(run.name))) return { kind: 'excluded' };
    const [a, b] = String(run.pair).split('~'), A = idx[a], B = idx[b];
    const opponents = (registry.validation?.opponents || []).map(o => o.id), vseed = registry.validation?.seed;
    const alias = !!(A?.alias || B?.alias);
    if (A && B && A.round === B.round && A.role === 'stu' && B.role === 'stu' && run.seed !== vseed)
      return { kind: 'selfplay', round: A.round, alias };
    if (run.seed === vseed && A && opponents.includes(b)) return { kind: 'validation', round: A.round, role: A.role, opponent: b, sign: 1, alias };
    if (run.seed === vseed && B && opponents.includes(a)) return { kind: 'validation', round: B.round, role: B.role, opponent: a, sign: -1, alias };
    if (A && B && A.role === B.role && A.round !== B.round) {
      const newerA = roundOrder(registry, A.round) > roundOrder(registry, B.round);
      return { kind: 'h2h', role: A.role, newer: newerA ? A.round : B.round, older: newerA ? B.round : A.round,
        sign: newerA ? 1 : -1, seed: run.seed, alias };
    }
    return { kind: 'other' };
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
  const X8_KEYS = ['rollout', 'blend', 'search', 'claim', 'consulted', 'moved', 'guaranteed', 'rollouts', 'net_rows', 'forks', 'seconds'];
  function reduceRun(rows, cls) {
    const sign = cls.sign || 1, keepBoards = cls.kind !== 'selfplay';
    const out = { rows: rows.length, cpu: 0, cpu_n: 0, x8: null, x8_boards: 0, boards: keepBoards ? [] : null,
      imps_sum: 0, imps_sq: 0, won: 0, lost: 0, flat: 0, classes: { p: 0, g: 0, s: 0, '0': 0 } };
    // the side whose engine is the round's bot: the candidate when sign is +1
    const side = sign > 0 ? 'candidate' : 'opponent';
    for (const r of rows) {
      const imps = sign * Number(r.common);
      if (!Number.isFinite(imps)) continue;
      out.imps_sum += imps; out.imps_sq += imps * imps;
      if (imps > 0) out.won++; else if (imps < 0) out.lost++; else out.flat++;
      if (Number.isFinite(r.cpu)) { out.cpu += r.cpu; out.cpu_n++; }
      const cc = contractClass(r.contract);
      out.classes[cc]++;
      if (keepBoards) out.boards.push([String(r.family || r.index).slice(0, 16), r.index, imps, cc]);
      const x = r.search?.[side]?.x8;
      if (x) {
        out.x8 ||= Object.fromEntries(X8_KEYS.map(k => [k, 0]));
        for (const k of X8_KEYS) out.x8[k] += Number(x[k]) || 0;
        out.x8_boards++;
      }
    }
    out.n = out.won + out.lost + out.flat;
    out.cpu = Math.round(out.cpu * 10) / 10;
    if (out.x8) for (const k of X8_KEYS) out.x8[k] = Math.round(out.x8[k] * 1000) / 1000;
    return out;
  }
  function summaryOf(red) {
    const n = red.n;
    if (!n) return stats([]);
    const mean = red.imps_sum / n, variance = n > 1 ? Math.max(0, (red.imps_sq - n * mean * mean) / (n - 1)) : null;
    const se = variance === null ? null : Math.sqrt(variance / n), half = se === null ? null : tcrit(n - 1) * se;
    return { n, mean, sd: variance === null ? null : Math.sqrt(variance), se, ci: half === null ? null : [mean - half, mean + half],
      won: red.won, lost: red.lost, flat: red.flat };
  }

  // ---- net scores from a trainer's metrics.json (scripts/train_rollout_net.py) ----------------------------------
  const pick = (g) => g ? Object.fromEntries(['n', 'nll', 'uniform_nll', 'agree', 'in_best', 'regret', 'rated_pick', 'regret_gap_head']
    .filter(k => g[k] !== undefined).map(k => [k, g[k]])) : null;
  function netMetrics(m, gen = {}) {
    if (!m || typeof m !== 'object') return null;
    const v = m.validation || {};
    const prevKey = gen.net?.previous_compare;
    const prev = prevKey && m.compared ? (m.compared[prevKey] || Object.entries(m.compared).find(([k]) => k.endsWith(prevKey))?.[1]) : null;
    const byBot = {};
    for (const [b, g] of Object.entries(v.by_bot || {})) byBot[b] = pick(g);
    return {
      width: m.width ?? null, epochs: m.epochs ?? null, selected_epoch: m.selected_epoch ?? null, parameters: m.parameters ?? null,
      train_examples: m.train_examples ?? null, train_deals: m.train_deals ?? null, init: m.init ?? null, val_data: m.val_data ?? null,
      lr: m.lr ?? null, seconds: m.seconds ?? null,
      all: pick(v.all), late: pick(v.from_trick_7), declaring: pick(v.declaring), defending: pick(v.defending),
      by_phase: Object.fromEntries(Object.entries(v.by_phase || {}).map(([k, g]) => [k, pick(g)])), by_bot: byBot,
      history: (m.history || []).map(h => ({ epoch: h.epoch, train_ce: h.train_ce ?? null, nll: h.val?.nll ?? null,
        agree: h.val?.agree ?? null, regret: h.val?.regret ?? null })),
      previous: prev ? { label: gen.net?.previous_label || prevKey, all: pick(prev.all), late: pick(prev.from_trick_7) } : null,
    };
  }

  // ---- the generation model -------------------------------------------------------------------------------------
  // runs: [{key, branch, box, name, pair, seed, deals, status, started, sources, cls, red, summary, episodes}]
  function mergeBoards(runs) {
    // One board per deal family: rows under a round's own ids before rows under an old alias, earlier runs first.
    const sorted = runs.slice().sort((a, b) => (a.cls.alias - b.cls.alias) || ((a.started || 0) - (b.started || 0)));
    const seen = new Map();
    for (const r of sorted) for (const b of r.red?.boards || []) if (!seen.has(b[0])) seen.set(b[0], b);
    return [...seen.values()].sort((a, b) => a[1] - b[1]);
  }
  function cellOf(runs) {
    const boards = mergeBoards(runs), s = stats(boards.map(b => b[2]));
    return { runs: runs.map(r => r.key), boards, stats: s,
      deals: Math.max(0, ...runs.map(r => r.deals || 0)),
      cpu: runs.reduce((a, r) => a + (r.red?.cpu || 0), 0) / Math.max(1, runs.reduce((a, r) => a + (r.red?.cpu_n || 0), 0)),
      status: runs.some(r => r.status === 'running') ? 'running' : runs.every(r => r.status === 'complete') ? 'complete' : (runs[0]?.status || 'unknown'),
      by_class: Object.fromEntries(['p', 'g', 's'].map(c => [c, stats(boards.filter(b => b[3] === c).map(b => b[2]))])),
      curve: curve(boards.map(b => b[2])) };
  }
  // A minus B on the deal families both played, each against the same opponent.
  function paired(cellA, cellB) {
    if (!cellA || !cellB) return null;
    const mb = new Map(cellB.boards.map(b => [b[0], b[2]]));
    const d = cellA.boards.filter(b => mb.has(b[0])).map(b => b[2] - mb.get(b[0]));
    return d.length ? stats(d) : null;
  }
  function buildModel(registry, runs, metricsByKey = {}) {
    const cells = {}, h2h = {}, selfplay = {}, others = [];
    const group = (obj, key, run) => (obj[key] ||= []).push(run);
    for (const r of runs) {
      const c = r.cls;
      if (c.kind === 'validation') group(cells, `${c.round}|${c.role}|${c.opponent}`, r);
      else if (c.kind === 'h2h') group(h2h, `${c.newer}|${c.older}|${c.role}`, r);
      else if (c.kind === 'selfplay') group(selfplay, c.round, r);
      else if (c.kind === 'other') others.push(r);
    }
    const cellModel = Object.fromEntries(Object.entries(cells).map(([k, rs]) => [k, cellOf(rs)]));
    const h2hModel = Object.fromEntries(Object.entries(h2h).map(([k, rs]) => [k, cellOf(rs)]));
    const opponents = registry.validation?.opponents || [], primary = (opponents.find(o => o.primary) || opponents[0])?.id;
    const roles = (registry.roles || []).map(r => r.key);
    const gens = [];
    let prevGen = null;
    for (const g of registry.generations || []) {
      const cell = (role, opp = primary) => cellModel[`${g.round}|${role}|${opp}`] || null;
      const prevCell = (role, opp = primary) => prevGen ? cellModel[`${prevGen.round}|${role}|${opp}`] || null : null;
      const sp = (selfplay[g.round] || []).slice().sort((a, b) => (a.started || 0) - (b.started || 0));
      const spRed = sp.map(r => r.red).filter(Boolean);
      const spBoards = sp.reduce((n, r) => n + Math.max(r.red?.n || 0, r.episodes || 0), 0);
      const x8 = spRed.reduce((acc, red) => {
        if (!red.x8) return acc;
        acc ||= Object.fromEntries(X8_KEYS.map(k => [k, 0]).concat([['boards', 0]]));
        for (const k of X8_KEYS) acc[k] += red.x8[k]; acc.boards += red.x8_boards;
        return acc;
      }, null);
      const spCpu = spRed.reduce((a, red) => a + red.cpu, 0), spCpuN = spRed.reduce((a, red) => a + red.cpu_n, 0);
      const valX8 = (cell('stu') ? runs.filter(r => cell('stu').runs.includes(r.key)) : []).reduce((acc, r) => {
        if (!r.red?.x8) return acc;
        acc ||= Object.fromEntries(X8_KEYS.map(k => [k, 0]).concat([['boards', 0]]));
        for (const k of X8_KEYS) acc[k] += r.red.x8[k]; acc.boards += r.red.x8_boards;
        return acc;
      }, null);
      const metricsKey = g.net?.metrics ? `${g.net.metrics.branch}:${g.net.metrics.path}` : null;
      const h = prevGen ? h2hModel[`${g.round}|${prevGen.round}|stu`] || null : null;
      const entry = {
        round: g.round, label: g.label, kind: g.kind || 'round', status: g.status || null, note: g.note || null,
        net: g.net || null, metrics: metricsKey ? metricsByKey[metricsKey] || null : null, metrics_key: metricsKey,
        bots: g.bots || {}, cells: Object.fromEntries(roles.flatMap(role => opponents.map(o => [`${role}|${o.id}`, cell(role, o.id)]))),
        amplification: {
          roll_over_net: paired(cell('roll'), cell('net')),
          stu_over_net: paired(cell('stu'), cell('net')),
          stu_over_roll: paired(cell('stu'), cell('roll')),
        },
        delta: prevGen ? Object.fromEntries(roles.map(role => [role, paired(cell(role), prevCell(role))])) : null,
        previous_round: prevGen ? prevGen.round : null,
        h2h: h,
        // queued deals: the round's own runs; a run under an old id counts only the boards it played
        selfplay: { runs: sp.map(r => r.key), boards: spBoards,
          target: sp.reduce((n, r) => n + (r.cls.alias ? Math.max(r.red?.n || 0, r.episodes || 0) : (r.deals || 0)), 0),
          stats: spRed.length ? summaryOf(spRed.reduce((a, red) => ({ n: a.n + red.n, imps_sum: a.imps_sum + red.imps_sum,
            imps_sq: a.imps_sq + red.imps_sq, won: a.won + red.won, lost: a.lost + red.lost, flat: a.flat + red.flat }),
            { n: 0, imps_sum: 0, imps_sq: 0, won: 0, lost: 0, flat: 0 })) : null,
          cpu: spCpuN ? spCpu / spCpuN : null, x8, rows_seen: spRed.reduce((a, red) => a + red.n, 0),
          status: sp.some(r => r.status === 'running') ? 'running' : sp.length ? sp.at(-1).status : null },
        validation_x8: valX8,
      };
      gens.push(entry);
      if ((g.kind || 'round') === 'round') prevGen = g;
    }
    return { generations: gens, cells: cellModel, h2h: h2hModel, others, primary, opponents, roles: registry.roles || [] };
  }

  const api = { REPO, rawURL, treeURL, tcrit, stats, curve, parseRunsLog, parseResults, botIndex, classify, contractClass,
    reduceRun, summaryOf, netMetrics, mergeBoards, cellOf, paired, buildModel, X8_KEYS };
  root.StuCore = api;
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window === 'undefined' ? globalThis : window);
