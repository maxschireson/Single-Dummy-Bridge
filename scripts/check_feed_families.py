#!/usr/bin/env python3
"""Does a cohort hold deals a net was trained on? Feed branches checked against lists of deal families.

  python scripts/check_feed_families.py --families v41_training_families.txt.gz [--families OTHER.json] \\
         [--work DIR] [--verify 200] [--overlap] [--loose 50] [--json OUT] BRANCH[=COMMIT] [BRANCH ...]

For each branch (at its tip, or at COMMIT) and each cohort directory on it (a folder holding `corpus.jsonl`, or
`corpus-parts/`, and `episodes/`): how many deals of the cohort's corpus, how many of the boards played and how many of
the deals still waiting are in each list. A corpus line's family is the last 64 characters of its `id`, which is the
deal key the arena records as a board's `family` (`deal_key(hands, True)`); --verify N recomputes it from the hands on
N lines of each corpus and stops if one differs. A board's corpus line is its episode's number.

A folder of episodes with no corpus beside it (a collector's preflight boards, say) is read board by board when it
holds no more than --loose episodes (default 50), and reported as not checked otherwise.

--overlap adds what the cohorts share with each other: for each two cohorts, the deals in both corpora and how many of
them each has played; and, from the feeds' replay indexes (`arena/replays/data/<cohort>/index-N.json`), the boards two
cohorts played on the same deal with the same pair, where the dashboard counts the earlier board and the later one is
spent.

Nothing but trees, the corpus files and (with --overlap) the replay indexes is downloaded (a blobless fetch of each tip
into DIR, default ~/.cache/feed-families), so a feed with thousands of episodes takes seconds. A list is a text file
of family hashes, one a line (.gz or not), or a JSON list.

Written on 12 November 2026 to check the Gen 7.1 and Gen 8 cohorts against the families policy v4.1 was trained on
(`transfer/gen7-policy-v4.1-families-20261112`); Max's rule of that day: no bot plays a board in a family it has been
trained on, in the arena.
"""
import argparse
import collections
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
    ap.add_argument('--overlap', action='store_true', help='also: the deals cohorts share, and boards two cohorts played on the same deal with the same pair')
    ap.add_argument('--loose', type=int, default=50, help='read a folder of episodes that has no corpus board by board if it holds at most this many')
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
    corpora, boards = {}, {}
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
        cohorts, loose = {}, {}
        for n in names:
            m = re.match(r'^(?:(.*)/)?episodes/(\d+)\.json\.gz$', n)
            if m:
                cohorts.setdefault(m.group(1) or '', dict(played=[], corpus=None, parts=[]))['played'].append(int(m.group(2)))
            elif re.search(r'episodes/[^/]+\.json\.gz$', n):
                loose.setdefault(n.rsplit('/', 1)[0], []).append(n)
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
                loose[f"{folder}/episodes" if folder else 'episodes'] = [n for n in names if re.match(r'^' + re.escape(folder) + r'/?episodes/\d+\.json\.gz$', n)]
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
            corpora[f"{branch} {folder or '.'}"] = (fam, done)
            flag = 'HOLDS LISTED DEALS  ' if any(e['corpus'] for e in entry['lists'].values()) else 'clean  '
            print(f"  {flag}{folder or '.'}: corpus {len(fam)}, played {len(played)} | " + ' | '.join(text_))
        for folder, files in sorted(loose.items()):
            if len(files) > a.loose:
                print(f"  {folder}: {len(files)} episodes and no corpus beside them: NOT CHECKED (--loose {a.loose})")
                out[branch]['cohorts'][folder] = dict(episodes=len(files), corpus=None)
                continue
            fam = [json.loads(gzip.decompress(git('show', f'{tip}:{n}', binary=True))).get('family') for n in files]
            entry = dict(episodes=len(files), corpus=None, lists={name: dict(played=sum(f in s for f in fam)) for name, s in lists.items()})
            for name in lists:
                bad[name] += entry['lists'][name]['played']
            out[branch]['cohorts'][folder] = entry
            flag = 'HOLDS LISTED DEALS  ' if any(e['played'] for e in entry['lists'].values()) else 'clean  '
            print(f"  {flag}{folder}: {len(files)} episodes with no corpus beside them, read one by one | " + ' | '.join(f"{name}: {e['played']}" for name, e in entry['lists'].items()))
        if a.overlap:
            replay = {}
            for n in names:
                m = re.match(r'^arena/replays/data/([0-9a-f]{64})/index-\d+\.json$', n)
                if m:
                    replay.setdefault(m.group(1), []).append(n)
            for ident, files in replay.items():
                rows = [r for f in sorted(files) for r in json.loads(git('show', f'{tip}:{f}'))]
                boards[f'{branch} {ident[:12]}'] = [(r['family'], r.get('pair'), r.get('completed_epoch') or 0.) for r in rows if r.get('family')]
    print('\ndeals of the corpora checked that are in a list: ' + ', '.join(f'{k} {v}' for k, v in bad.items()))
    if a.overlap:
        print('\ncohorts whose corpora share deals, and how many of the shared deals each has played:')
        keys = list(corpora)
        deals = {k: set(v[0]) for k, v in corpora.items()}
        done = {k: {v[0][i] for i in v[1]} for k, v in corpora.items()}
        shared = []
        for i, x in enumerate(keys):
            for y in keys[i + 1:]:
                both = deals[x] & deals[y]
                if both:
                    shared.append(dict(a=x, b=y, deals=len(both), played_a=len(both & done[x]), played_b=len(both & done[y]), played_both=len(both & done[x] & done[y])))
                    print(f"  {x} and {y}: {len(both)} deals; played by the first {len(both & done[x])}, by the second {len(both & done[y])}, by both {len(both & done[x] & done[y])}")
        if not shared:
            print('  none')
        print('\nboards on a deal another cohort played earlier with the same pair (the later board is spent):')
        seen = collections.defaultdict(list)
        for k, rows in boards.items():
            for fam, pair, when in rows:
                seen[(fam, pair)].append((when, k))
        spent, other_pair = collections.Counter(), 0
        by_deal = collections.defaultdict(set)
        for (fam, pair), found in seen.items():
            by_deal[fam].update(k for _, k in found)
            if len({k for _, k in found}) > 1:
                found.sort()
                for when, k in found[1:]:
                    if k != found[0][1]:
                        spent[(k, found[0][1], pair)] += 1
        for (k, earlier, pair), n in sorted(spent.items(), key=lambda kv: -kv[1]):
            print(f"  {k}: {n} boards of {pair} on deals {earlier} played first")
        total = {k: len(rows) for k, rows in boards.items()}
        print(f"  in all {sum(spent.values())} of {sum(total.values())} boards published; deals played by more than one cohort (any pair): {sum(len(v) > 1 for v in by_deal.values())}")
        out['overlap'] = dict(corpora=shared, spent=[dict(cohort=k, earlier=e, pair=p, boards=n) for (k, e, p), n in spent.items()], boards=total)
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
