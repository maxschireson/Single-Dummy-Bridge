"""E9-0: what a nat of reading is worth. One table from the matches of helped bots against the same unhelped bot.

    python3 scripts/gen9_e9_0_report.py --run n02=RUNDIR --run n04=RUNDIR ... [--gain n02=CALDIR ...] [--out report.md]

A RUNDIR holds results.jsonl of scripts/gen9_match.py (one row a board, `native` = the helped bot's IMPs). A CALDIR is
a run of the same bot with --episodes: the decisions' `oracle_near` notes give the realised gain in nats (the x axis).
Matches on the same seed share deals by `index`, so differences between settings are paired.
"""
import argparse
import glob
import gzip
import json
import math
from pathlib import Path


def rows(run):
    out = {}
    path = Path(run) / 'results.jsonl'
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            out[int(r['index'])] = float(r['native'])
    return out


def mean_se(xs):
    n = len(xs)
    if n < 2:
        return (xs[0] if xs else float('nan')), float('nan')
    m = sum(xs) / n
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) / n)


def gains(cal):
    """Gain notes of every decision in a calibration run: [(trick, declaring, gain)], and decisions without help."""
    notes, plain = [], 0

    def walk(x):
        nonlocal plain
        if isinstance(x, dict):
            g6 = x.get('gen6') if isinstance(x.get('gen6'), dict) else None
            if 'oracle_near' in x:
                notes.append(float(x['oracle_near']['gain']))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    for f in sorted(glob.glob(str(Path(cal) / 'episodes' / '*'))):
        op = gzip.open if f.endswith('.gz') else open
        with op(f, 'rt') as h:
            text = h.read()
        for chunk in ([text] if text.lstrip().startswith('{') and '\n{' not in text.strip() else text.splitlines()):
            if chunk.strip():
                walk(json.loads(chunk))
    boards = len(glob.glob(str(Path(cal) / 'episodes' / '*')))
    return notes, boards


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', action='append', default=[], help='label=RUNDIR')
    p.add_argument('--gain', action='append', default=[], help='label=CALDIR (a run with --episodes)')
    p.add_argument('--pair', action='append', default=[], help='a-b: the paired difference of two labels on shared deals')
    p.add_argument('--out')
    a = p.parse_args()
    runs = dict(x.split('=', 1) for x in a.run)
    cals = dict(x.split('=', 1) for x in a.gain)
    data = {k: rows(v) for k, v in runs.items()}
    L = ['| Setting | Boards | IMPs a board | Won / lost / flat | Helped decisions a board | Gain a helped decision, nats | Nats a board | IMPs per nat a board |',
         '| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |']
    summary = {}
    for k, d in data.items():
        xs = list(d.values())
        if not xs:
            L.append(f'| {k} | 0 | | | | | | |')
            continue
        m, se = mean_se(xs)
        won, lost = sum(x > 0 for x in xs), sum(x < 0 for x in xs)
        g = per = total = None
        if k in cals:
            notes, boards = gains(cals[k])
            if notes and boards:
                g, per = sum(notes) / len(notes), len(notes) / boards
                total = g * per
        summary[k] = dict(boards=len(xs), imps=m, se=se, gain=g, helped=per, nats_board=total)
        L.append(f'| {k} | {len(xs):,} | {m:+.3f} ± {se:.3f} | {won} / {lost} / {len(xs) - won - lost} | '
                 + (f'{per:.1f} | {g:+.2f} | {total:.1f} | {m / total:+.4f} ± {se / total:.4f} |' if total else ' | | | |'))
    for pair in a.pair:
        x, y = pair.split('-', 1)
        shared = sorted(set(data.get(x, {})) & set(data.get(y, {})))
        if len(shared) > 1:
            m, se = mean_se([data[x][i] - data[y][i] for i in shared])
            L.append('')
            L.append(f'{x} minus {y} on {len(shared):,} shared deals: {m:+.3f} ± {se:.3f} IMPs a board.')
    text = '\n'.join(L) + '\n'
    if a.out:
        Path(a.out).write_text(text)
        Path(a.out).with_suffix('.json').write_text(json.dumps(summary, indent=1))
    print(text)


if __name__ == '__main__':
    main()
