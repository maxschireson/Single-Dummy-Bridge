"""Statistics of an X9 conditional-claims pilot (g9, Gen 9, G9-A11): decisions, floors, commitments, moves, forks, time.

usage: python3 pilot_stats.py RUN_DIR [RUN_DIR ...]
"""
import collections
import glob
import gzip
import json
import math
import statistics as st
import sys


def walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def stats(run):
    rows = [json.loads(line) for line in open(f'{run}/results.jsonl')]
    c, moved_boards, forks = collections.Counter(), set(), []
    for f in sorted(glob.glob(f'{run}/episodes/*.json.gz')):
        d = json.loads(gzip.open(f, 'rt').read())
        main = [a for t in d['unique_tables'].values() for a in t['tables'][0]['actions']]     # tables[1:] are fork branches
        c['main-line actions'] += len(main)
        for o in main:
            x = o.get('x9')
            if not isinstance(x, dict):
                continue
            c['decisions with x9 notes'] += 1
            if x.get('cells') is not None:
                c['conditional questions asked'] += 1
            if x.get('applied'):
                c['floors applied'] += 1
            if x.get('preferred'):
                c['preference active'] += 1
            if (x.get('chosen_floor') or 0) >= .9:
                c['committed (chosen floor >= 0.9)'] += 1
            if x.get('kept') is not None:
                c['later decisions under a commitment'] += 1
            if x.get('moved'):
                c['card moved'] += 1
                moved_boards.add(f)
            if o.get('prediction_units') == 'x9-against-no-conditional':
                c['forks named'] += 1
    cand = [r['search']['candidate']['seconds'] for r in rows]
    opp = [r['search']['opponent']['seconds'] for r in rows]
    d = [a - b for a, b in zip(cand, opp)]
    dec = sum(r['search']['candidate']['decisions'] for r in rows)
    imps = [r['common'] for r in rows]                      # common-auction IMPs (native equals common in these pilots)
    out = dict(boards=len(rows), **c, boards_with_a_move=len(moved_boards),
               seconds_a_board=round(st.mean(cand), 3), control_seconds=round(st.mean(opp), 3),
               extra_seconds=round(st.mean(d), 3), extra_se=round(st.stdev(d) / math.sqrt(len(d)), 3),
               extra_pct=round(100 * st.mean(d) / st.mean(opp), 1), decisions=dec,
               nonzero_boards=sum(1 for x in imps if x), imps_a_board=round(st.mean(imps), 4))
    return out


if __name__ == '__main__':
    for run in sys.argv[1:]:
        print(run)
        for k, v in stats(run).items():
            print(f'  {k}: {v}')
