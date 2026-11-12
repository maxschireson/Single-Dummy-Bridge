#!/usr/bin/env python3
"""Does a cohort hold deals a net was trained on? Feed branches checked against lists of deal families.

  python scripts/check_feed_families.py --families v41_training_families.txt.gz [--families OTHER.json] \\
         [--work DIR] [--verify 200] [--json OUT] BRANCH[=COMMIT] [BRANCH ...]

For each branch (at its tip, or at COMMIT) and each cohort directory on it (a folder holding `corpus.jsonl`, or
`corpus-parts/`, and `episodes/`): how many deals of the cohort's corpus, how many of the boards played and how many of
the deals still waiting are in each list. A corpus line's family is the last 64 characters of its `id`, which is the
deal key the arena records as a board's `family` (`deal_key(hands, True)`); --verify N recomputes it from the hands on
N lines of each corpus and stops if one differs. A board's corpus line is its episode's number.

Nothing but trees and the corpus files is downloaded (a blobless fetch of each tip into DIR, default
~/.cache/feed-families), so a feed with thousands of episodes takes seconds. A list is a text file of family hashes,
one a line (.gz or not), or a JSON list.

Written on 12 November 2026 to check the Gen 7.1 and Gen 8 cohorts against the families policy v4.1 was trained on
(`transfer/gen7-policy-v4.1-families-20261112`); Max's rule of that day: no bot plays a board in a family it has been
trained on, in the arena.
"""
import argparse
import gzip
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zlib

REPO = os.environ.get('FEED_REPO', 'https://github.com/maxschireson/Single-Dummy-Bridge')
HEX = re.compile(r'([0-9a-f]{64})$')


def read_list(path):
    raw = gzip.open(path, 'rt').read() if str(path).endswith('.gz') else Path(path).read_text()
    return set(json.loads(raw)) if raw.lstrip().startswith('[') else set(raw.split())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('branches', nargs='+', metavar='BRANCH[=COMMIT]')
    ap.add_argument('--families', action='append', required=True)
    ap.add_argument('--work', default=str(Path.home() / '.cache' / 'feed-families'))
    ap.add_argument('--verify', type=int, default=0, help='recompute the deal key from the hands on this many lines of each corpus')
    ap.add_argument('--json')
    a = ap.parse_args()
    lists = {Path(p).name: read_list(p) for p in a.families}
    work = Path(a.work)
    if not (work / 'HEAD').exists():
        subprocess.run(['git', 'init', '--bare', '-q', str(work)], check=True)
        for k, v in (('remote.origin.url', REPO), ('remote.origin.promisor', 'true'), ('remote.origin.partialclonefilter', 'blob:none'), ('gc.auto', '0')):
            subprocess.run(['git', '--git-dir', str(work), 'config', k, v], check=True)

    def git(*args, binary=False):
        r = subprocess.run(['git', '--git-dir', str(work), *args], capture_output=True, timeout=900)
        if r.returncode:
            raise RuntimeError(r.stderr.decode(errors='replace')[-300:])
        return r.stdout if binary else r.stdout.decode()

    if a.verify:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from bridge_harness.bidding_env import deal_key
        from bridge_harness.core import Board
    out, bad = {}, {k: 0 for k in lists}
    print('lists: ' + ', '.join(f'{k} ({len(v)})' for k, v in lists.items()))
    for spec in a.branches:
        branch, _, commit = spec.partition('=')
        try:
            git('fetch', '-q', '--depth', '1', '--filter=blob:none', '--no-tags', 'origin', commit or branch)
            tip = commit or git('rev-parse', 'FETCH_HEAD').strip()
            when = git('log', '-1', '--format=%cI', tip).strip()
            names = git('ls-tree', '-r', '--name-only', tip).split('\n')
        except Exception as e:
            print(f'{branch}: {e}')
            out[branch] = dict(error=str(e))
            continue
        cohorts = {}
        for n in names:
            m = re.match(r'^(.*?)/?episodes/(\d+)\.json\.gz$', n)
            if m:
                cohorts.setdefault(m.group(1), dict(played=[], corpus=None, parts=[]))['played'].append(int(m.group(2)))
            m = re.match(r'^(.*?)/?corpus\.jsonl$', n)
            if m:
                cohorts.setdefault(m.group(1), dict(played=[], corpus=None, parts=[]))['corpus'] = n
            m = re.match(r'^(.*?)/?corpus-parts/corpus\.jsonl\.gz\.part-\d+$', n)
            if m:
                cohorts.setdefault(m.group(1), dict(played=[], corpus=None, parts=[]))['parts'].append(n)
        out[branch] = dict(tip=tip, committed=when, cohorts={})
        print(f'\n{branch} at {tip[:10]} ({when})')
        for folder, c in sorted(cohorts.items()):
            if c['corpus']:
                text = git('show', f"{tip}:{c['corpus']}")
            elif c['parts']:
                dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
                text = b''.join(dec.decompress(git('show', f'{tip}:{p}', binary=True)) for p in sorted(c['parts'])).decode()
            else:
                print(f"  {folder or '.'}: {len(c['played'])} episodes and no corpus beside them: NOT CHECKED")
                out[branch]['cohorts'][folder] = dict(episodes=len(c['played']), corpus=None)
                continue
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
            fam = [r.get('family') or (HEX.search(r.get('id') or '') or [None, None])[1] for r in rows]
            if any(f is None for f in fam):
                print(f"  {folder or '.'}: {sum(f is None for f in fam)} corpus lines carry no family: NOT CHECKED")
                continue
            if a.verify:
                step = max(1, len(rows) // a.verify)
                wrong = sum(deal_key(Board.from_dict(r).hands, True) != f for r, f in list(zip(rows, fam))[::step])
                if wrong:
                    raise SystemExit(f'{branch} {folder}: the id of {wrong} sampled corpus lines is not the deal key of their hands')
            played = sorted(i for i in set(c['played']) if i < len(fam))
            done = set(played)
            entry = dict(corpus=len(fam), played=len(played), lists={})
            text_ = []
            for name, s in lists.items():
                e = dict(corpus=sum(f in s for f in fam), played=sum(fam[i] in s for i in played), waiting=sum(f in s for i, f in enumerate(fam) if i not in done))
                entry['lists'][name] = e
                bad[name] += e['corpus']
                text_.append(f"{name}: corpus {e['corpus']}, played {e['played']}, waiting {e['waiting']}")
            out[branch]['cohorts'][folder] = entry
            flag = 'HOLDS LISTED DEALS  ' if any(e['corpus'] for e in entry['lists'].values()) else 'clean  '
            print(f"  {flag}{folder or '.'}: corpus {len(fam)}, played {len(played)} | " + ' | '.join(text_))
    print('\ndeals of the corpora checked that are in a list: ' + ', '.join(f'{k} {v}' for k, v in bad.items()))
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
