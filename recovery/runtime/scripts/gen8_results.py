#!/usr/bin/env python3
"""Pool the Gen 8 matches published by the boxes (results of scripts/gen8_match.py on the branches
transfer/gen8-proto-<box>-20261112, one folder a match with its results.jsonl).

  python scripts/gen8_results.py                      every match, pooled over boxes by name (a '-azureN' suffix is dropped)
  python scripts/gen8_results.py --pair NAME1 NAME2   also: NAME1 minus NAME2 on the deals both played (same seed and index)
  python scripts/gen8_results.py --regime native      the rooms where each bot bids its own system, in place of the common auctions

A match played from an auction book is also given by what the two sides of the table declared (NS~EW).
The branches are fetched into ~/.cache/g8results. IMPs a board are for the first-named bot of the match.
"""
import argparse, json, math, subprocess, sys
from pathlib import Path

REPO = 'https://github.com/maxschireson/single-dummy-bridge'
CACHE = Path.home() / '.cache' / 'g8results'


def fetch(boxes):
    CACHE.mkdir(parents=True, exist_ok=True)
    if not (CACHE / '.git').exists():
        subprocess.run(['git', 'init', '-q', str(CACHE)], check=True)
        subprocess.run(['git', '-C', str(CACHE), 'remote', 'add', 'origin', REPO], check=True)
    out = {}
    for box in boxes:
        br = f'transfer/gen8-proto-{box}-20261112'
        r = subprocess.run(['git', '-C', str(CACHE), 'fetch', '-q', '--depth', '1', 'origin', f'+refs/heads/{br}:refs/remotes/origin/{br}'], capture_output=True, text=True)
        if r.returncode:
            continue
        names = subprocess.run(['git', '-C', str(CACHE), 'ls-tree', '-r', '--name-only', f'origin/{br}'], capture_output=True, text=True).stdout.split('\n')
        when = subprocess.run(['git', '-C', str(CACHE), 'log', '-1', '--format=%cI', f'origin/{br}'], capture_output=True, text=True).stdout.strip()
        out[box] = (br, [n for n in names if n.endswith('/results.jsonl')], when)
    return out


def rows_of(br, path):
    text = subprocess.run(['git', '-C', str(CACHE), 'show', f'origin/{br}:{path}'], capture_output=True, text=True).stdout
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def stat(x):
    n = len(x)
    if n < 2:
        return None
    mean = sum(x) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in x) / (n - 1))
    return mean, sd / math.sqrt(n), n, sd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--boxes', default='azure1,azure2,azure3,azure4,azure6')
    ap.add_argument('--pair', nargs=2, action='append', default=[])
    ap.add_argument('--regime', default='common')
    args = ap.parse_args()
    matches = {}
    for box, (br, paths, when) in fetch(args.boxes.split(',')).items():
        print(f'{box}: published {when}; {len(paths)} matches')
        for path in paths:
            name = path.split('/')[0]
            for suffix in ('-azure1', '-azure2', '-azure3', '-azure4', '-azure6'):
                name = name.replace(suffix, '')
            matches.setdefault(name, {}).update({r['index']: r for r in rows_of(br, path)})
    for name in sorted(matches):
        rows = matches[name].values()
        x = [r[args.regime] for r in rows if r.get(args.regime) is not None]
        s = stat(x)
        nat = stat([r['native'] for r in rows if r.get('native') is not None]) if args.regime == 'common' else None
        if s:
            won, lost = sum(v > 0 for v in x), sum(v < 0 for v in x)
            cpu = sum(r['cpu'] for r in rows) / len(rows)
            extra = f' | native {nat[0]:+.3f} +- {nat[1]:.3f}' if nat and abs(nat[0] - s[0]) > 1e-9 else ''
            print(f'{name:28s} {s[2]:6d} boards  {s[0]:+.3f} +- {s[1]:.3f} IMPs/board  (won {won}, lost {lost}, flat {s[2] - won - lost}; sd {s[3]:.2f}; {cpu:.1f} cpu-s/board){extra}')
            kinds = sorted({r['systems'] for r in rows if r.get('systems')})
            for kind in kinds if len(kinds) > 1 else ():
                k = stat([r[args.regime] for r in rows if r.get('systems') == kind and r.get(args.regime) is not None])
                if k:
                    print(f'    {kind:34s} {k[2]:6d} boards  {k[0]:+.3f} +- {k[1]:.3f}')
    for a, b in args.pair:
        if a in matches and b in matches:
            both = sorted(set(matches[a]) & set(matches[b]))
            d = [matches[a][i][args.regime] - matches[b][i][args.regime] for i in both if matches[a][i].get(args.regime) is not None and matches[b][i].get(args.regime) is not None]
            s = stat(d)
            if s:
                print(f'{a} minus {b}: {s[0]:+.3f} +- {s[1]:.3f} IMPs/board on {s[2]} shared deals (sd of the difference {s[3]:.2f})')


if __name__ == '__main__':
    main()
