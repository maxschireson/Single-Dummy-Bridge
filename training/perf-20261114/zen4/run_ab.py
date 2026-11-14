#!/usr/bin/env python3
"""P02 (PR #35): the perf patches measured on Zen 4, each alone and together, on fixed deals, two runs a configuration.

    run_ab.py [--boards N] [--lanes 8] [--heavy-lanes 4] [--only NAMES] [--push] [--report-only]

Every job is one `scripts/x8_match.py` run with one worker (one table a board, full records) on seed 777, deals 0 to
N-1, so configurations are compared deal by deal. Jobs run in parallel lanes, as eight collection workers share a box.
For each job: CPU-s a board (x8_match's own count), boards an hour of one worker (wall clock), and the worker's peak
resident memory (sampled every 2 s). Then cards are compared board by board: each configuration against both
baseline runs, and the two baseline runs against each other (the run-to-run floor).

Outputs under ~/perf/ab/<job>/ and ~/perf/ab/report.json, report.txt, cards.json.gz. --push publishes the report
and the cards (not the episodes) to branch transfer/perf-zen4-ab-20261114 with the box's boxctl deploy key.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

P = Path.home() / 'perf'
S = P / 'src'
OUT = P / 'ab'
PY = str(P / 'venv' / 'bin' / 'python')
OFF = dict(BRIDGE_NET_BUCKETS='0', BRIDGE_FORK_BATCH='0', BRIDGE_FAST_FEATURES='0', BRIDGE_POLICY_SUITS='0')
ON = dict(BRIDGE_NET_BUCKETS='1', BRIDGE_FORK_BATCH='1', BRIDGE_FAST_FEATURES='1', BRIDGE_POLICY_SUITS='1')
STU, G8 = 'stu4c-psta~stu4c-pstb', 'g8-greedy0~g8-passive0'


def configs():
    """(name, pair, env, heavy). heavy: bf16 without the padding, whose workers grow to several GB."""
    bf = dict(BRIDGE_NET_BF16='1')
    one = lambda **k: {**OFF, **k}
    return [
        ('stu-base', STU, {**bf, **OFF}, True),                       # bf16 as the loop collects now
        ('stu-buckets', STU, {**bf, **one(BRIDGE_NET_BUCKETS='1')}, False),
        ('stu-forks', STU, {**bf, **one(BRIDGE_FORK_BATCH='1')}, True),
        ('stu-forks2', STU, {**bf, **one(BRIDGE_FORK_BATCH='2')}, True),   # the old path on the fork stream: forks' reference
        ('stu-features', STU, {**bf, **one(BRIDGE_FAST_FEATURES='1')}, True),
        ('stu-policy', STU, {**bf, **one(BRIDGE_POLICY_SUITS='1')}, True),
        ('stu-all', STU, {**bf, **ON}, False),
        ('stu-all2', STU, {**bf, **ON, 'BRIDGE_FORK_BATCH': '2'}, False),  # all, forks by the old path on their stream: stu-all's reference
        ('g8-base', G8, dict(OFF), False),                            # fp32, as Gen 8's self-play is collected
        ('g8-features', G8, one(BRIDGE_FAST_FEATURES='1'), False),
        ('g8-policy', G8, one(BRIDGE_POLICY_SUITS='1'), False),
        ('g8-all', G8, dict(ON), False),
        ('g8-bf16-all', G8, {**bf, **ON}, False),                     # a proposal, not an equivalence: bf16 changes cards
    ]


SHORT = {'stu-forks', 'stu-forks2', 'stu-features', 'stu-policy'}     # single patches on unpadded bf16: 60% of the boards


def jobs(boards, only):
    out = []
    for name, pair, env, heavy in configs():
        if only and name not in only:
            continue
        n = max(1, round(0.6 * boards)) if name in SHORT else boards
        for rep in (1, 2):
            out.append(dict(job=f'{name}-{rep}', config=name, pair=pair, env=env, heavy=heavy, boards=n))
    return out


def child_rss_kb(pid):
    """Largest resident set among the run's processes (the pool worker is the big one)."""
    best = 0
    for d in Path('/proc').iterdir():
        if not d.name.isdigit():
            continue
        try:
            stat = (d / 'stat').read_text()
            ppid = int(stat.rsplit(')', 1)[1].split()[1])
            if int(d.name) != pid and ppid != pid:
                continue
            for line in (d / 'status').read_text().splitlines():
                if line.startswith('VmRSS:'):
                    best = max(best, int(line.split()[1]))
        except (OSError, ValueError, IndexError):
            continue
    return best


def run_job(j):
    d = OUT / j['job']
    if (d / 'summary.json').exists() and (d / 'perf.json').exists():
        return json.loads((d / 'perf.json').read_text())
    d.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, SURE_BIN=str(P / 'bin' / 'sure_cpp'), OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
               MKL_NUM_THREADS='1', BRIDGE_DDS_CACHE='', **j['env'])
    cmd = [PY, 'scripts/x8_match.py', '--source', str(P / 'capsule' / 'recovery'), '--bots', 'configs/loop-bots.json',
           '--pair', j['pair'], '--deals', str(j['boards']), '--first', '0', '--seed', '777', '--workers', '1',
           '--out', str(d / 'run'), '--episodes', '--one-room']
    t0 = time.time()
    with open(d / 'log.txt', 'w') as log:
        proc = subprocess.Popen(cmd, cwd=S, env=env, stdout=log, stderr=subprocess.STDOUT)
        peak, samples = 0, []
        while proc.poll() is None:
            r = child_rss_kb(proc.pid)
            peak = max(peak, r)
            samples.append((round(time.time() - t0), r))
            time.sleep(2)
    wall = time.time() - t0
    summary = json.loads((d / 'run' / 'summary.json').read_text()) if (d / 'run' / 'summary.json').exists() else {}
    lines = (d / 'log.txt').read_text().strip().splitlines()
    last = json.loads(lines[-1]) if lines and lines[-1].startswith('{') else {}
    done = sum(1 for _ in open(d / 'run' / 'results.jsonl')) if (d / 'run' / 'results.jsonl').exists() else 0
    out = dict(job=j['job'], config=j['config'], pair=j['pair'], env=j['env'], exit=proc.returncode, boards=done,
               cpu_per_board=last.get('cpu_per_board'), wall_s=round(wall, 1),
               boards_per_hour=round(3600 * done / wall, 1) if wall and done else None,
               peak_rss_mb=round(peak / 1024), rss_trace=samples[::15])
    (d / 'perf.json').write_text(json.dumps(out, indent=1))
    (d / 'summary.json').write_text(json.dumps(summary, indent=1))
    return out


def cards(job):
    """{board index: [card, ...]} from a job's episodes."""
    out = {}
    for f in sorted((OUT / job / 'run' / 'episodes').glob('*.json.gz')):
        try:
            e = json.load(gzip.open(f))
            t = e['unique_tables']['table-0']['tables'][0]
            out[int(e['index'])] = [a['card'] for a in t['actions'] if a.get('card') is not None]
        except (OSError, ValueError, KeyError, IndexError):
            continue
    return out


def agreement(a, b):
    common = sorted(set(a) & set(b))
    same = [i for i in common if a[i] == b[i]]
    first = [next((k for k, (x, y) in enumerate(zip(a[i], b[i])) if x != y), min(len(a[i]), len(b[i])))
             for i in common if a[i] != b[i]]
    return dict(boards=len(common), identical=len(same),
                median_first_difference=sorted(first)[len(first) // 2] if first else None)


def lanes_run(todo, lanes, n_heavy):
    """Heavy jobs (unpadded bf16, several GB a worker) on at most `n_heavy` lanes, which take light jobs once the heavy
    ones are done; the other lanes take light jobs only, so no more than `n_heavy` heavy workers ever share the box."""
    heavy = [j for j in todo if j['heavy']]
    light = [j for j in todo if not j['heavy']]
    results, lock = [], threading.Lock()
    n_heavy = max(1, min(n_heavy, lanes))

    def worker(queue, fallback):
        while True:
            with lock:
                j = queue.pop(0) if queue else (fallback.pop(0) if fallback else None)
            if j is None:
                return
            r = run_job(j)
            with lock:
                results.append(r)
                print(json.dumps({k: r[k] for k in ('job', 'exit', 'boards', 'cpu_per_board', 'boards_per_hour', 'peak_rss_mb')}), flush=True)

    threads = [threading.Thread(target=worker, args=(heavy, light)) for _ in range(n_heavy)]
    threads += [threading.Thread(target=worker, args=(light, [])) for _ in range(lanes - n_heavy)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def report(results):
    by = {}
    for r in results:
        by.setdefault(r['config'], []).append(r)
    cardsets = {r['job']: cards(r['job']) for r in results}
    rows = []
    for name, *_ in configs():
        rs = sorted(by.get(name, []), key=lambda r: r['job'])
        if not rs:
            continue
        base = 'stu-base' if name.startswith('stu') else 'g8-base'
        ref = {'stu-forks': 'stu-forks2', 'stu-all': 'stu-all2'}.get(name, base)
        agree = {}
        for r in rs:
            for b in (f'{ref}-1', f'{ref}-2'):
                if b != r['job'] and b in cardsets:
                    agree[f"{r['job']} vs {b}"] = agreement(cardsets[r['job']], cardsets[b])
        rows.append(dict(config=name, runs=[{k: r[k] for k in ('job', 'exit', 'boards', 'cpu_per_board', 'boards_per_hour',
                                                                'peak_rss_mb', 'wall_s')} for r in rs],
                         cpu_per_board=[r['cpu_per_board'] for r in rs], agreement=agree))
    meta = dict(time=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                source=subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=S, capture_output=True, text=True).stdout.strip(),
                cpu=next((l.split(':', 1)[1].strip() for l in open('/proc/cpuinfo') if l.startswith('model name')), ''),
                cores=os.cpu_count(), host=os.uname().nodename)
    rep = dict(meta=meta, configs=rows)
    (OUT / 'report.json').write_text(json.dumps(rep, indent=1))
    with gzip.open(OUT / 'cards.json.gz', 'wt') as f:
        json.dump(cardsets, f)
    lines = [f"P02 on {meta['cpu']} ({meta['cores']} cores, {meta['host']}), source {meta['source'][:10]}, {meta['time']}",
             f"{'config':14s} {'CPU-s/board':>16s} {'boards/h':>14s} {'peak MB':>12s}  cards identical (vs reference runs)"]
    for row in rows:
        cpu = ' '.join(f'{c:.2f}' if c else '-' for c in row['cpu_per_board'])
        bph = ' '.join(f"{r['boards_per_hour']:.0f}" if r['boards_per_hour'] else '-' for r in row['runs'])
        mb = ' '.join(str(r['peak_rss_mb']) for r in row['runs'])
        ag = '; '.join(f"{v['identical']}/{v['boards']}" for v in row['agreement'].values())
        lines.append(f"{row['config']:14s} {cpu:>16s} {bph:>14s} {mb:>12s}  {ag}")
    (OUT / 'report.txt').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


def push():
    """report.txt, report.json, cards.json.gz and each job's perf.json to transfer/perf-zen4-ab-20261114."""
    key = Path.home() / '.ssh' / 'boxctl_github'
    url = 'git@github.com:maxschireson/Single-Dummy-Bridge.git'
    cfg = Path.home() / '.boxctl' / 'config.json'
    if cfg.exists():
        url = json.loads(cfg.read_text()).get('repo', url)
    env = dict(os.environ, GIT_SSH_COMMAND=f'ssh -i {key} -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new')
    g = P / 'pub'
    subprocess.run(['rm', '-rf', str(g)], check=True)
    g.mkdir()
    run = lambda *a: subprocess.run(['git', *a], cwd=g, env=env, check=True, capture_output=True)
    run('init', '-q', '-b', 'transfer/perf-zen4-ab-20261114')
    run('config', 'user.name', f'perf ({os.uname().nodename})')
    run('config', 'user.email', 'perf@invalid')
    run('config', 'commit.gpgsign', 'false')
    for name in ('report.txt', 'report.json', 'cards.json.gz'):
        if (OUT / name).exists():
            (g / name).write_bytes((OUT / name).read_bytes())
    (g / 'jobs').mkdir()
    for d in OUT.iterdir():
        if (d / 'perf.json').exists():
            (g / 'jobs' / f'{d.name}.json').write_bytes((d / 'perf.json').read_bytes())
    run('add', '-A')
    run('commit', '-q', '-m', 'P02 Zen 4 measurement: report, cards and per-job timings (perf session)')
    run('remote', 'add', 'origin', url)
    run('push', '-q', '-f', 'origin', 'HEAD:refs/heads/transfer/perf-zen4-ab-20261114')
    print('pushed transfer/perf-zen4-ab-20261114')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--boards', type=int, default=100)
    ap.add_argument('--lanes', type=int, default=os.cpu_count() or 8)
    ap.add_argument('--heavy-lanes', type=int, default=4, help='most unpadded-bf16 jobs at once (memory)')
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--push', action='store_true')
    ap.add_argument('--report-only', action='store_true')
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    todo = jobs(a.boards, set(a.only or []))
    if a.report_only:
        results = [json.loads((OUT / j['job'] / 'perf.json').read_text()) for j in todo if (OUT / j['job'] / 'perf.json').exists()]
    else:
        print(f'{len(todo)} jobs, {a.boards} boards each, {a.lanes} lanes', flush=True)
        results = lanes_run(todo, a.lanes, a.heavy_lanes)
    report(results)
    if a.push:
        push()


if __name__ == '__main__':
    sys.exit(main())
