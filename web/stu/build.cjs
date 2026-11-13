#!/usr/bin/env node
/* Builds the Stu dashboard's snapshot (data.json) from the loop's published branches.
 *
 *   node web/stu/build.cjs --repo <git checkout with origin = the GitHub repo> [--registry web/stu/registry.json]
 *                          [--out data.json] [--no-fetch]
 *
 * For every branch in the registry (and every net's metrics branch) it fetches the branch tip (depth 1), reads
 * runs.log and each run folder's results.jsonl, summary.json and EPISODES.txt, and reduces them with stu-core.js, the
 * same code the page runs on live data. The page shows the snapshot and re-reads runs that are still going. */
'use strict';
const fs = require('fs'), path = require('path'), { execFileSync } = require('child_process');
const core = require('./stu-core.js');

function args(argv) {
  const a = { registry: path.join(__dirname, 'registry.json'), out: 'data.json', fetch: true };
  for (let i = 2; i < argv.length; i++) {
    const k = argv[i];
    if (k === '--repo') a.repo = argv[++i];
    else if (k === '--registry') a.registry = argv[++i];
    else if (k === '--out') a.out = argv[++i];
    else if (k === '--no-fetch') a.fetch = false;
    else throw Error('unknown argument ' + k);
  }
  if (!a.repo) throw Error('--repo is required');
  return a;
}
const git = (repo, ...xs) => execFileSync('git', ['-C', repo, ...xs], { encoding: 'utf8', maxBuffer: 1 << 30, stdio: ['ignore', 'pipe', 'pipe'] });
const tryGit = (repo, ...xs) => { try { return git(repo, ...xs); } catch (e) { return null; } };

function main() {
  const a = args(process.argv);
  const registry = JSON.parse(fs.readFileSync(a.registry, 'utf8'));
  const branchList = registry.branches.map(b => b.branch);
  const metricBranches = [...new Set(registry.generations.map(g => g.net?.metrics?.branch).filter(Boolean))];
  const heads = {};
  for (const br of [...branchList, ...metricBranches]) {
    const ref = `refs/remotes/origin/${br}`;
    if (a.fetch) tryGit(a.repo, 'fetch', '-q', '--depth', '1', 'origin', `+refs/heads/${br}:${ref}`);
    const head = tryGit(a.repo, 'rev-parse', ref);
    heads[br] = head ? { sha: head.trim(), committed_epoch: +git(a.repo, 'log', '-1', '--format=%ct', ref).trim() } : null;
  }
  const idx = core.botIndex(registry), runs = [];
  for (const b of registry.branches) {
    if (!heads[b.branch]) continue;
    const ref = `refs/remotes/origin/${b.branch}`;
    const files = new Set(git(a.repo, 'ls-tree', '-r', '--name-only', ref).split('\n').filter(Boolean));
    const log = files.has('runs.log') ? git(a.repo, 'show', `${ref}:runs.log`) : '';
    const meta = core.parseRunsLog(log, b.box);
    // Runs on a frozen branch with no runs.log (the sandbox): folders with a manifest name their pair and seed.
    for (const f of files) {
      const m = /^([^/]+)\/results\.jsonl$/.exec(f);
      if (!m || meta[m[1]]) continue;
      const man = files.has(`${m[1]}/manifest.json`) ? JSON.parse(git(a.repo, 'show', `${ref}:${m[1]}/manifest.json`)) : {};
      const pair = man.pair || (Array.isArray(man.pair_schedule) && man.pair_schedule.length === 1 ? man.pair_schedule[0] : null);
      if (!pair) continue;
      meta[m[1]] = { name: m[1], box: b.box, pair, seed: man.seed ?? null, first: man.first ?? 0, deals: man.deals ?? null,
        sources: man.source_commit ? [man.source_commit.slice(0, 7)] : [], starts: [], ends: [],
        status: b.frozen ? 'complete' : 'unknown', started: null, common_bidder: man.common_bidder || null };
    }
    for (const r of Object.values(meta)) {
      const cls = core.classify(r, registry, idx);
      if (cls.kind === 'excluded') continue;
      const folder = r.name + '/';
      let red = null, bad = 0, summary = null, episodes = null;
      if (files.has(folder + 'results.jsonl')) {
        const parsed = core.parseResults(git(a.repo, 'show', `${ref}:${folder}results.jsonl`));
        bad = parsed.bad; red = core.reduceRun(parsed.rows, cls);
      }
      if (files.has(folder + 'summary.json')) summary = JSON.parse(git(a.repo, 'show', `${ref}:${folder}summary.json`));
      if (files.has(folder + 'EPISODES.txt')) episodes = parseInt(git(a.repo, 'show', `${ref}:${folder}EPISODES.txt`), 10) || null;
      if (b.frozen && r.status === 'unknown') r.status = 'complete';
      runs.push({ key: `${b.box}/${r.name}`, branch: b.branch, box: b.box, name: r.name, pair: r.pair, seed: r.seed,
        first: r.first, deals: r.deals, options: r.options || '', sources: r.sources, started: r.started,
        last_event: r.last_event ?? null, status: r.status, exit: r.exit ?? null, cls, red, bad_lines: bad,
        summary: summary ? { boards_per_hour: summary.boards_per_hour ?? null, cpu_per_board: summary.cpu_per_board ?? null,
          failures: summary.failures ?? null } : null, episodes });
    }
  }
  const metrics = {};
  for (const g of registry.generations) {
    const m = g.net?.metrics;
    if (!m || !heads[m.branch]) continue;
    const text = tryGit(a.repo, 'show', `refs/remotes/origin/${m.branch}:${m.path}`);
    if (text) metrics[`${m.branch}:${m.path}`] = core.netMetrics(JSON.parse(text), g);
  }
  const snapshot = { schema: 'stu-snapshot-v1', built_epoch: Date.now() / 1000, registry_updated: registry.updated || null,
    heads, runs, metrics };
  fs.writeFileSync(a.out, JSON.stringify(snapshot));
  const model = core.buildModel(registry, runs, metrics);
  for (const g of model.generations) {
    const c = g.cells[`stu|${model.primary}`];
    console.log(`${g.label}: self-play ${g.selfplay.boards} boards; Stu v ${model.primary}: ${c ? c.stats.n + ' boards, ' +
      (c.stats.mean ?? NaN).toFixed(3) + ' +- ' + (c.stats.se ?? NaN).toFixed(3) : 'not run'}; net metrics ${g.metrics ? 'yes' : 'no'}`);
  }
  console.log(`${runs.length} runs, ${(fs.statSync(a.out).size / 1024).toFixed(0)} KB -> ${a.out}`);
}
main();
