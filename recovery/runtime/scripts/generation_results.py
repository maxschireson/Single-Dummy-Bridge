#!/usr/bin/env python3
"""Pool one generation's published arena results across every registered feed.

Used at a generation cleanup (docs/generation-cleanup.md) to write the closing
results table. It reads the dashboard's source registry (gh-pages
arena/gen6-sources.json, which lists Gen 6 and Gen 7 feeds), loads each feed's
score snapshot and replay index at the registered revision (retired sources) or
the branch head (live sources), and applies the dashboard's counting rules:

* records completed after the snapshot's generated_epoch are ignored;
* hidden actors (ben32) and the accidental fast-vs-BEN cohorts are excluded;
* pairs are normalized to the dashboard's actor order (IMPs are from the
  first-named actor's side);
* within a matchup a deal family counts once, earliest completion wins.

Common = common (shared-bidder) auction IMPs; native = each partnership's own
bidder; bidding = native - common on boards that have both. Intervals are
normal-approximation 95% and unadjusted for repeated looks, as on the dashboard.

Usage:
  python scripts/generation_results.py --generation 6 --out results.json [--markdown table.md]
  python scripts/generation_results.py --generation 6 --fetch gh   # use the gh CLI instead of HTTPS
"""
from __future__ import annotations

import argparse
import json
import math
import posixpath
import subprocess
import time
import urllib.request

REPO = 'maxschireson/Single-Dummy-Bridge'
REGISTRY = ('gh-pages', 'arena/gen6-sources.json')
ORDER = ['7s-32', '7f-32', '6-32', '6-256', '5RZ32', '5RZ192', '5R32', '5R192', '5', '5-32',
         '4', '4p', '4b', '3', '2', '1', 'ben', 'ben32', 'ben64']
HIDDEN = {'ben32'}
ACCIDENTAL = {'497d7f2c2e90d37c271ee7d700371c94f93d0f6717f530082742e80d24b2eb63',
              'e891c0a5c780c509a81df08c15397b6c7c6a24a8a266da499c6223d73bd24177'}


def fetch(path: str, ref: str, how: str):
    if how == 'gh':
        out = subprocess.run(['gh', 'api', '-H', 'Accept: application/vnd.github.raw',
                              f'repos/{REPO}/contents/{path}?ref={ref}'],
                             capture_output=True, check=True).stdout
        return json.loads(out)
    url = f'https://raw.githubusercontent.com/{REPO}/{ref}/{path}'
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())


def head(branch: str, how: str) -> str:
    if how == 'gh':
        return subprocess.run(['gh', 'api', f'repos/{REPO}/git/ref/heads/{branch}', '--jq', '.object.sha'],
                              capture_output=True, text=True, check=True).stdout.strip()
    with urllib.request.urlopen(f'https://api.github.com/repos/{REPO}/git/ref/heads/{branch}', timeout=60) as r:
        return json.loads(r.read())['object']['sha']


def members(p: str):
    return p.split('~') if '~' in p else [p[0], p[1]]


def pair_id(a: str, b: str) -> str:
    return a + b if len(a) == 1 and len(b) == 1 else f'{a}~{b}'


def normalize(p: str):
    a, b = members(p)
    flip = ORDER.index(a) > ORDER.index(b)
    return (pair_id(b, a) if flip else pair_id(a, b)), flip


def stats(values):
    n = len(values)
    if n < 2:
        return {'n': n}
    mean = sum(values) / n
    var = sum((x - mean) ** 2 for x in values) / (n - 1)
    se = math.sqrt(var / n)
    return {'n': n, 'mean': mean, 'se': se, 'ci95': [mean - 1.96 * se, mean + 1.96 * se],
            'wins': sum(x > 0 for x in values), 'ties': sum(x == 0 for x in values),
            'losses': sum(x < 0 for x in values)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--generation', type=int, required=True)
    ap.add_argument('--registry', help='Local registry JSON (default: gh-pages arena/gen6-sources.json)')
    ap.add_argument('--fetch', choices=['http', 'gh'], default='http')
    ap.add_argument('--out', required=True)
    ap.add_argument('--markdown')
    args = ap.parse_args()

    registry = (json.load(open(args.registry)) if args.registry
                else fetch(REGISTRY[1], REGISTRY[0], args.fetch))
    rows, sources = [], []
    for s in registry['sources']:
        if s.get('generation') != args.generation:
            continue
        ref = s.get('revision') or head(s['branch'], args.fetch)
        data = fetch('arena/data.json', ref, args.fetch)
        if data['manifest_identity'] != s['cohort']:
            raise SystemExit(f"{s['key']}: run identity at {ref} is not the registered cohort")
        ipath = f"arena/replays/data/{s['cohort']}/index.json"
        index = fetch(ipath, ref, args.fetch)
        records = list(index.get('records') or [])
        for shard in index.get('record_shards') or []:
            records += fetch(posixpath.normpath(posixpath.join(posixpath.dirname(ipath), shard)), ref, args.fetch)
        records = [r for r in records if r['completed_epoch'] <= data['generated_epoch']]
        own_ok = bool(data.get('own_views')) and index.get('supports_own_bidding') is not False
        sources.append({'key': s['key'], 'name': s.get('name'), 'branch': s['branch'], 'revision': ref,
                        'retired': bool(s.get('retired')), 'records': len(records),
                        'snapshot_utc': time.strftime('%Y-%m-%d %H:%M', time.gmtime(data['generated_epoch']))})
        for r in records:
            p, flip = normalize(r['pair'])
            if any(m in HIDDEN for m in members(p)) or (p == '6-32~ben' and s['cohort'] in ACCIDENTAL):
                continue
            if s.get('allowed_pairs') and r['pair'] not in s['allowed_pairs']:
                continue
            sign = -1 if flip else 1
            rows.append({'pair': p, 'family': r['family'], 't': r['completed_epoch'], 'source': s['key'],
                         'common': None if r.get('imps') is None else sign * r['imps'],
                         'native': sign * r['own_imps'] if own_ok and r.get('own_imps') is not None else None})

    rows.sort(key=lambda r: r['t'])
    seen, counted = set(), []
    for r in rows:
        key = (r['family'], r['pair'])
        if key not in seen:
            seen.add(key)
            counted.append(r)

    pairs = {}
    for p in sorted({r['pair'] for r in counted}, key=lambda p: [ORDER.index(m) for m in members(p)]):
        a, b = members(p)
        pr = [r for r in counted if r['pair'] == p]
        if a == b:
            pairs[p] = {'boards': len(pr), 'self_play': True}
            continue
        both = [r for r in pr if r['native'] is not None and r['common'] is not None]
        pairs[p] = {'boards': len(pr),
                    'common': stats([r['common'] for r in pr if r['common'] is not None]),
                    'native': stats([r['native'] for r in both]),
                    'bidding': stats([r['native'] - r['common'] for r in both])}

    out = {'generation': args.generation, 'computed_utc': time.strftime('%Y-%m-%d %H:%M', time.gmtime()),
           'rules': 'dashboard counting rules; see module docstring', 'observations': len(rows),
           'counted_boards': len(counted), 'pairs': pairs, 'sources': sources}
    json.dump(out, open(args.out, 'w'), indent=1)

    def cell(s):
        if not s or s.get('mean') is None:
            return '—'
        return f"{s['mean']:+.2f} ({s['ci95'][0]:+.2f} to {s['ci95'][1]:+.2f})"

    lines = ['| Pair | Boards | Common auction (play) | Native auction (total) | Bidding (native − common) |',
             '| --- | ---: | --- | --- | --- |']
    for p, v in pairs.items():
        if v.get('self_play'):
            lines.append(f"| `{p}` self-play | {v['boards']:,} | no strength estimate | | |")
        else:
            lines.append(f"| `{p}` | {v['boards']:,} | {cell(v['common'])} | {cell(v['native'])} | {cell(v['bidding'])} |")
    table = '\n'.join(lines)
    if args.markdown:
        open(args.markdown, 'w').write(table + '\n')
    print(table)
    print(f"\n{len(counted):,} counted boards from {len(rows):,} observations across {len(sources)} sources")


if __name__ == '__main__':
    main()
