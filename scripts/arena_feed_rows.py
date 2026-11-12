#!/usr/bin/env python3
"""Every per-board result the arena has published, one row per record, with no pooling rule applied.

Gen 9 work in progress (dave, task G9-D2/G9-D3). Not an arena tool: it only reads.

Reads the dashboard's source registry (gh-pages arena/gen6-sources.json), and for each source
the score snapshot (arena/data.json) and the replay index and its shards at the registered
revision (retired sources) or the branch head (live sources), the same files and the same
revision rule as scripts/generation_results.py. Unlike that script it keeps every record and
writes the facts needed to apply any counting rule later:

  source, generation, cohort, ref, retired, allowed_pairs, snapshot_epoch,
  pair (as recorded, from the candidate's side), index, family, completed_epoch,
  common (IMPs, common auction), native (IMPs, each side's own bidder), native_ok

`native_ok` is false where the dashboard does not trust the feed's native column (no own views,
or the index says it does not support own bidding).

  python scripts/arena_feed_rows.py --out rows.jsonl.gz [--registry local.json] [--cache DIR]

Files are fetched from raw.githubusercontent.com at a commit sha and cached under --cache, so a
second run costs nothing for retired sources.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
import posixpath
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = 'maxschireson/Single-Dummy-Bridge'
RAW = 'https://raw.githubusercontent.com/' + REPO


def heads():
    """Branch name -> commit sha for every branch, in one call."""
    out = subprocess.run(['git', 'ls-remote', '--heads', 'https://github.com/' + REPO],
                         capture_output=True, text=True, check=True).stdout
    return {line.split('\t')[1].removeprefix('refs/heads/'): line.split('\t')[0]
            for line in out.splitlines() if '\t' in line}


def fetch(cache: Path, ref: str, path: str, tries=3):
    key = cache / ref / path
    if key.exists():
        return json.loads(key.read_text())
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(f'{RAW}/{ref}/{path}', timeout=120) as r:
                body = r.read()
            break
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(2 + 3 * attempt)
    key.parent.mkdir(parents=True, exist_ok=True)
    key.write_bytes(body)
    return json.loads(body)


def source_rows(s, ref, cache):
    data = fetch(cache, ref, 'arena/data.json')
    if data['manifest_identity'] != s['cohort']:
        raise ValueError(f"{s['key']}: run identity at {ref} is not the registered cohort")
    ipath = f"arena/replays/data/{s['cohort']}/index.json"
    index = fetch(cache, ref, ipath)
    records = list(index.get('records') or [])
    for shard in index.get('record_shards') or []:
        records += fetch(cache, ref, posixpath.normpath(posixpath.join(posixpath.dirname(ipath), shard)))
    native_ok = bool(data.get('own_views')) and index.get('supports_own_bidding') is not False
    rows = []
    for r in records:
        rows.append(dict(source=s['key'], generation=s.get('generation'), cohort=s['cohort'], ref=ref,
                         retired=bool(s.get('retired')), allowed_pairs=s.get('allowed_pairs'),
                         snapshot_epoch=data['generated_epoch'], pair=r['pair'], index=r.get('index'),
                         family=r['family'], completed_epoch=r['completed_epoch'], common=r.get('imps'),
                         native=r.get('own_imps'), native_ok=native_ok))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--registry', type=Path)
    ap.add_argument('--cache', type=Path, default=Path.home() / '.cache' / 'arena-feeds')
    ap.add_argument('--workers', type=int, default=6)
    args = ap.parse_args()
    if args.registry:
        registry = json.loads(args.registry.read_text())
    else:
        registry = json.loads(urllib.request.urlopen(f'{RAW}/gh-pages/arena/gen6-sources.json', timeout=60).read())
    branch_heads = heads()
    jobs = []
    for s in registry['sources']:
        ref = s.get('revision') or branch_heads.get(s['branch'])
        if ref is None:
            print(f"{s['key']}: branch {s['branch']} not found; skipped", file=sys.stderr)
            continue
        jobs.append((s, ref))
    rows, report = [], []
    with ThreadPoolExecutor(args.workers) as pool:
        futures = [(s, ref, pool.submit(source_rows, s, ref, args.cache)) for s, ref in jobs]
        for s, ref, f in futures:
            try:
                got = f.result()
            except Exception as e:
                print(f"{s['key']}: {type(e).__name__}: {e}"[:300], file=sys.stderr)
                report.append(dict(source=s['key'], ref=ref, error=repr(e)[:300]))
                continue
            rows += got
            report.append(dict(source=s['key'], ref=ref, generation=s.get('generation'), records=len(got)))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.out, 'wt') as f:
        for r in rows:
            f.write(json.dumps(r, separators=(',', ':')) + '\n')
    registry_sha = hashlib.sha256(json.dumps(registry, sort_keys=True).encode()).hexdigest()
    meta = dict(computed_utc=time.strftime('%Y-%m-%d %H:%M', time.gmtime()), registry_sha256=registry_sha,
                rows=len(rows), sources=report)
    args.out.with_suffix('').with_suffix('.meta.json').write_text(json.dumps(meta, indent=1))
    print(f'{len(rows):,} rows from {sum("records" in r for r in report)} sources '
          f'({sum("error" in r for r in report)} failed) -> {args.out}')


if __name__ == '__main__':
    main()
