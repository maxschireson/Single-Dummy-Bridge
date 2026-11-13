#!/usr/bin/env python3
"""Fetch the episodes a recorded fetch saw: every episode at the branch tips named in a fetch manifest.

  python fetch_tips.py --tips v2-fetch.json --out DIR --work DIR --manifest FILE [--jobs 8] [--limit N]

--tips is a manifest written by training/rollout-net-v2-20261113/fetch_feeds.py (`branches`: name -> tip). The
commits are fetched by id, so the result is the set of episodes those feeds held then, whatever they hold now: one
file per distinct blob, DIR/<blob id>.json.gz, as fetch_feeds.py writes them. The new manifest records the tips used
and the counts. Rollout net v2's training set is the episodes at the tips of `v2-fetch.json` (its last fetch,
02:17 UTC on 13 November 2026, `fetch.json` on transfer/rollout-net-v2-20261113).
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rollout-net-v2-20261113'))
from fetch_feeds import EPISODE, REPO, fetch_chunk, git, store          # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--tips', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--limit', type=int, default=0)
    p.add_argument('--jobs', type=int, default=8)
    p.add_argument('--chunk', type=int, default=400)
    a = p.parse_args()
    started = time.time()
    a.out.mkdir(parents=True, exist_ok=True)
    a.work.mkdir(parents=True, exist_ok=True)
    source = json.loads(a.tips.read_text())
    tips = {name: b['tip'] for name, b in source['branches'].items()}
    base = store(a.work / 'base.git')
    names = sorted(tips)
    for i in range(0, len(names), 12):
        git(base, 'fetch', '-q', '--no-tags', '--depth=1', '--filter=blob:none', 'origin',
            *[f'+{tips[n]}:refs/tips/{n}' for n in names[i:i + 12]])
    have = {f.name.split('.')[0] for f in a.out.iterdir() if f.name.endswith('.json.gz')}
    branches, new, first, every = {}, [], {}, set()
    for name in names:
        got = git(base, 'rev-parse', f'refs/tips/{name}').stdout.decode().strip()
        if got != tips[name]:
            raise SystemExit(f'{name}: fetched {got}, wanted {tips[name]}')
        total = fresh = 0
        for line in git(base, 'ls-tree', '-r', got).stdout.decode().splitlines():
            meta, path = line.split('\t', 1)
            if not EPISODE.search(path):
                continue
            oid = meta.split()[2]
            total += 1
            every.add(oid)
            if oid in have or oid in first:
                continue
            first[oid] = name
            new.append(oid)
            fresh += 1
        if total != source['branches'][name]['episodes']:
            raise SystemExit(f"{name}: {total} episodes at the tip, the manifest says {source['branches'][name]['episodes']}")
        branches[name] = dict(tip=got, episodes=total, new=fresh)
    if a.limit:
        new = new[:a.limit]
    print(f'{len(names)} tips, {sum(b["episodes"] for b in branches.values())} episode paths, {len(every)} distinct blobs, '
          f'{len(new)} to fetch', flush=True)
    chunks = [new[i:i + a.chunk] for i in range(0, len(new), a.chunk)]
    repos = [store(a.work / f'w{j}.git') for j in range(a.jobs)]
    done = size = 0

    def worker(j):
        nonlocal done, size
        for index in range(j, len(chunks), a.jobs):
            n, s = fetch_chunk((index, repos[j], chunks[index], a.out))
            done += n
            size += s
            print(f'{done} of {len(new)} blobs, {size / 2**30:.2f} GB, {round(time.time() - started)} s', flush=True)

    with ThreadPoolExecutor(a.jobs) as pool:
        for f in [pool.submit(worker, j) for j in range(a.jobs)]:
            f.result()
    summary = dict(repo=REPO, tips_from=a.tips.name, tips_finished_utc=source.get('finished_utc'),
                   finished_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), seconds=round(time.time() - started),
                   distinct_blobs=len(every), new_blobs=len(new), new_bytes=size, branches=branches)
    a.manifest.parent.mkdir(parents=True, exist_ok=True)
    a.manifest.write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: summary[k] for k in ('finished_utc', 'seconds', 'distinct_blobs', 'new_blobs', 'new_bytes')}))


if __name__ == '__main__':
    main()
