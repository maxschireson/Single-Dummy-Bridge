"""E9-19 report (cheap version): per pair, plain against re-scored IMPs; boards where the contracts differ apart.

Predictions (team/gen9:experiments/E9-19.md): on boards where the two tables' contracts differ, the per-board standard
deviation falls by at least 30%; on every pair whose plain mean is more than 2 SE from zero, the re-scored mean has the
same sign.

usage: python3 e919_report.py RESULTS.jsonl [RESULTS.jsonl ...]
"""
from collections import defaultdict
import json
import math
import sys


def stats(xs):
    n = len(xs)
    if n < 2:
        return n, float('nan'), float('nan'), float('nan')
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    return n, m, sd, sd / math.sqrt(n)


def main(paths):
    rows = [json.loads(line) for p in paths for line in open(p)]
    by = defaultdict(list)
    for r in rows:
        by[r['pair']].append(r)
    print(f'{len(rows)} boards, {sum(r["differ"] for r in rows)} with different contracts at the two tables')
    print('| Pair | Boards | Contracts differ | Plain mean +- SE | Re-scored mean +- SE | SD plain | SD re-scored | SD where contracts differ: plain, re-scored | ESS median |')
    print('| --- | ---: | ---: | --- | --- | ---: | ---: | --- | ---: |')
    signs_ok, signs_n = 0, 0
    for pair, rs in sorted(by.items()):
        n, mp, sp, ep = stats([r['plain'] for r in rs])
        _, mr, sr, er = stats([r['rescored'] for r in rs])
        d = [r for r in rs if r['differ']]
        _, _, sdp, _ = stats([r['plain'] for r in d])
        _, _, sdr, _ = stats([r['rescored'] for r in d])
        ess = sorted(min(r['ess']) for r in d if r.get('ess'))
        med = ess[len(ess) // 2] if ess else float('nan')
        print(f'| {pair} | {n} | {len(d)} | {mp:+.3f} +- {ep:.3f} | {mr:+.3f} +- {er:.3f} | {sp:.2f} | {sr:.2f} | {sdp:.2f}, {sdr:.2f} | {med:.0f} |')
        if abs(mp) > 2 * ep:
            signs_n += 1
            signs_ok += (mr > 0) == (mp > 0)
    d = [r for r in rows if r['differ']]
    _, _, sdp, _ = stats([r['plain'] for r in d])
    _, _, sdr, _ = stats([r['rescored'] for r in d])
    _, _, allp, _ = stats([r['plain'] for r in rows])
    _, _, allr, _ = stats([r['rescored'] for r in rows])
    fall = 1 - sdr / sdp if sdp == sdp and sdp > 0 else float('nan')
    print(f'\nWhere contracts differ ({len(d)} boards): SD {sdp:.2f} plain, {sdr:.2f} re-scored, a fall of {fall:.1%} '
          f'(prediction: at least 30%: {"met" if fall >= .30 else "not met"}).')
    print(f'All boards: SD {allp:.2f} plain, {allr:.2f} re-scored ({1 - allr / allp:.0%} lower).')
    print(f'Pairs more than 2 SE from zero: {signs_n}; same sign after re-scoring: {signs_ok} '
          f'(prediction: all: {"met" if signs_ok == signs_n else "not met"}).')


if __name__ == '__main__':
    main(sys.argv[1:])
