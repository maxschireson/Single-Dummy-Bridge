#!/usr/bin/env node
/* Builds the Stu dashboard's snapshot (data.json) from the loop's published branches.
 *
 *   node web/stu/build.cjs --repo <git checkout whose origin is the GitHub repo> [--registry web/stu/registry.json]
 *                          [--out data.json] [--no-fetch]
 *
 * Fetches (depth 1) the loop's run list, every box's transfer and status branch and every net's metrics branch; reads
 * runs.log, each run's results.jsonl, <run>.log, summary.json and EPISODES.txt, and the boxes' heartbeats; reduces them
 * with stu-core.js, the same code the page runs on live data. The page shows the snapshot and re-reads what is moving. */
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
const ref = br => `refs/remotes/origin/${br}`;

// What the page shows of a box's heartbeat (the ops/boxctl agent's heartbeat.json).
function heartbeat(h) {
  return { time: Date.parse(h.time) / 1000 || null, load: h.load || null, cpus: h.cpus ?? null,
    mem_available_mb: h.memory_mb?.MemAvailable ?? null, mem_total_mb: h.memory_mb?.MemTotal ?? null,
    disk_free_gb: h.disk?.home?.free_gb ?? null, last_push: h.previous_push || null, running: h.running || null };
}

function main() {
  const a = args(process.argv);
  const registry = JSON.parse(fs.readFileSync(a.registry, 'utf8'));
  const full = [...new Set(registry.boxes.map(b => b.branch))];          // rows: every blob is read
  const sparse = [...new Set([registry.runs_list?.branch, ...registry.boxes.map(b => b.status), ...registry.nets.map(n => n.metrics?.branch),
    ...registry.nets.flatMap(n => Object.values(n.before || {}).map(b => b.branch))]
    .filter(b => b && !full.includes(b)))];                               // a file or two each: blobs fetched on demand
  if (a.fetch) {
    for (const br of full) tryGit(a.repo, 'fetch', '-q', '--depth', '1', 'origin', `+refs/heads/${br}:${ref(br)}`);
    for (const br of sparse) tryGit(a.repo, 'fetch', '-q', '--depth', '1', '--filter=blob:none', 'origin', `+refs/heads/${br}:${ref(br)}`);
  }
  const heads = {};
  for (const br of [...full, ...sparse]) {
    const head = tryGit(a.repo, 'rev-parse', ref(br));
    heads[br] = head ? { sha: head.trim(), committed_epoch: +git(a.repo, 'log', '-1', '--format=%ct', ref(br)).trim() } : null;
  }
  const show = (br, p) => heads[br] ? tryGit(a.repo, 'show', `${ref(br)}:${p}`) : null;

  const listText = registry.runs_list ? show(registry.runs_list.branch, registry.runs_list.path) : null;
  const runsList = listText ? JSON.parse(listText) : { runs: [] };
  const entries = new Map(runsList.runs.map(r => [`${r.box}/${r.name}`, r]));
  const ids = core.botIds(runsList);
  const runs = [];
  for (const b of registry.boxes) {
    if (!heads[b.branch]) continue;
    const files = new Set(git(a.repo, 'ls-tree', '-r', '--name-only', ref(b.branch)).split('\n').filter(Boolean));
    const meta = core.parseRunsLog(files.has('runs.log') ? show(b.branch, 'runs.log') : '', b.box);
    // Folders with rows but no runs.log line (the sandbox): the manifest names the pair and seed.
    for (const f of files) {
      const m = /^([^/]+)\/results\.jsonl$/.exec(f);
      if (!m || meta[m[1]]) continue;
      const man = files.has(`${m[1]}/manifest.json`) ? JSON.parse(show(b.branch, `${m[1]}/manifest.json`)) : {};
      const pair = man.pair || (Array.isArray(man.pair_schedule) && man.pair_schedule.length === 1 ? man.pair_schedule[0] : null);
      if (!pair) continue;
      meta[m[1]] = { name: m[1], box: b.box, pair, seed: man.seed ?? null, first: man.first ?? 0, deals: man.deals ?? null,
        sources: man.source_commit ? [man.source_commit.slice(0, 7)] : [], status: b.frozen ? 'complete' : 'unknown', started: null };
    }
    // Runs the list names with no runs.log line: sharded runs (their folders hold the rows), and runs not started yet,
    // shown as queued unless shelved (they will not be played).
    for (const e of runsList.runs.filter(e => e.box === b.box && !meta[e.name])) {
      const sharded = Array.isArray(e.folders) && e.folders.length;
      if (e.shelved && !sharded && !files.has(e.name + '/results.jsonl')) continue;
      meta[e.name] = { name: e.name, box: b.box, pair: e.pair, seed: e.seed, first: e.first, deals: e.deals, sources: [],
        status: sharded ? 'complete' : 'queued', started: null, folders: sharded ? e.folders : null };
    }
    for (const r of Object.values(meta)) {
      const entry = entries.get(`${b.box}/${r.name}`) || null;
      const cls = core.classify(r, entry, registry, ids);
      if (cls.role === 'excluded') continue;
      const dir = r.name + '/';
      let red = null, bad = 0;
      const sources = r.folders ? r.folders.map(f => f + '/results.jsonl') : [dir + 'results.jsonl'];
      const texts = sources.filter(f => files.has(f)).map(f => show(b.branch, f));
      if (texts.length) {
        const parsed = core.parseResults(texts.join('\n'));
        bad = parsed.bad; red = core.reduceRun(parsed.rows, { sign: cls.sign || 1, keepBoards: cls.role !== 'collection' });
        if (r.folders && Number.isFinite(r.deals) && red.rows < r.deals) r.status = 'partial';
      }
      const summary = files.has(dir + 'summary.json') ? JSON.parse(show(b.branch, dir + 'summary.json')) : null;
      const episodes = files.has(dir + 'EPISODES.txt') ? parseInt(show(b.branch, dir + 'EPISODES.txt'), 10) || null : null;
      const progress = files.has(r.name + '.log') ? core.parseMatchLog(show(b.branch, r.name + '.log')) : null;
      const plan = core.planRun(r, entry);
      runs.push({ key: `${b.box}/${r.name}`, branch: b.branch, box: b.box, name: r.name, pair: r.pair, seed: r.seed,
        first: r.first, deals: plan.deals, pass_deals: plan.pass_deals, passes: plan.passes, options: r.options || '', sources: r.sources || [],
        started: r.started ?? null, last_event: r.last_event ?? null, status: plan.status, exit: r.exit ?? null, cls, red, bad_lines: bad, progress, episodes,
        queue_order: entry?.queue_order ?? null, note: entry?.note || null,
        summary: summary ? { boards_per_hour: summary.boards_per_hour ?? null, cpu_per_board: summary.cpu_per_board ?? null, failures: summary.failures ?? null } : null });
    }
  }
  const health = {};
  for (const b of registry.boxes.filter(b => b.status)) {
    const hb = show(b.status, 'heartbeat.json');
    if (hb) health[b.box] = heartbeat(JSON.parse(hb));
  }
  const metrics = {};
  for (const n of registry.nets) {
    const m = n.metrics;
    if (!m) continue;
    const text = show(m.branch, m.path);
    const before = {};
    for (const [k, f] of Object.entries(n.before || {})) { const t = show(f.branch, f.path); if (t) try { before[k] = JSON.parse(t); } catch (e) { console.warn(`${n.key} before ${k}: ${e.message}`); } }
    if (text) try { metrics[`${m.branch}:${m.path}`] = core.netMetrics(JSON.parse(text), n.compare, before, n.focus_bot || null); } catch (e) { console.warn(`${n.key}: ${e.message}`); }
  }
  let ledger = null;
  if (registry.ledger) { const t = show(registry.ledger.branch, registry.ledger.path); if (t) try { ledger = JSON.parse(t); } catch (e) { console.warn('ledger: ' + e.message); } }
  const snapshot = { schema: 'stu-snapshot-v2', built_epoch: Date.now() / 1000, registry_updated: registry.updated || null,
    heads, runs_list: runsList, runs, health, metrics, ledger };
  fs.writeFileSync(a.out, JSON.stringify(snapshot));
  const model = core.buildModel(registry, runs, metrics, runsList, ledger);
  for (const r of model.rounds) {
    const cells = Object.entries(r.cells).map(([k, c]) => `${k} ${c?.stats.n ? c.stats.n + ': ' + c.stats.mean.toFixed(3) + ' +- ' + c.stats.se.toFixed(3) : '-'}`).join('; ');
    console.log(`${r.label}: collection ${r.collection.boards} boards (${JSON.stringify(r.collection.by_rung)}, ${r.collection.rate ?? '-'} an hour); ${cells}`);
  }
  console.log(`ladder cells: ${Object.entries(model.ladder).map(([k, c]) => k + ' ' + c.stats.n).join(', ') || 'none'}`);
  console.log(`${runs.length} runs, ${Object.keys(metrics).length} nets scored, ${(fs.statSync(a.out).size / 1024).toFixed(0)} KB -> ${a.out}`);
}
module.exports = { heartbeat };
if (require.main === module) main();
