#!/usr/bin/env python3
"""G9-X2's tables: every reading in nats and in tricks saved a board, side by side, from the bench's report JSON.

  python scripts/gen9_reading_bench_report.py LABEL=REPORT.json [...] --against NAME [--readings A,B,...] [--board 2] > tables.md

REPORT.json is `scripts/gen9_reading_bench.py report --out OUT --against NAME --json REPORT.json`. A bench table is one
side's decisions at one table (the house bots' against BEN; declarer's on the relabelled house tables); `--board` is the
number of such tables a board has for the bot (2 against BEN: the house bot decides at both tables of the deal; 1 for
the relabelled tables, where only declarer's decisions are stored). Standard errors take the deal as the unit.
"""
import argparse
import json

BANDS = ('all', 'declarer deciding', 'defender deciding', 'tricks 1-2', 'tricks 3-4', 'tricks 5-6', 'tricks 7-9', 'tricks 10-13')


def pm(x, k=3):
    return f'{x[0]:+.{k}f} ± {x[1]:.{k}f}'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('reports', nargs='+')
    ap.add_argument('--against', required=True)
    ap.add_argument('--readings')
    ap.add_argument('--board', type=float, default=2.)
    ap.add_argument('--imps-a-trick', type=float, default=3.6)
    a = ap.parse_args()
    for item in a.reports:
        label, path = item.split('=', 1)
        r = json.loads(open(path).read())
        names = a.readings.split(',') if a.readings else r['nets']
        print(f"\n### {label}: {r['decisions']:,} decisions on {r['tables']} tables of {r['deals']} deals\n")
        print('Each reading against no reading: the true layout\'s log weight gained (nats a decision) and double-dummy tricks saved '
              f'a board ({a.board:g} bench table{"s" if a.board != 1 else ""} a board).\n')
        bands = [b for b in BANDS if b in r['groups'][f'as built | {names[0]}']]
        print('| Reading | ' + ' | '.join(bands) + ' |')
        print('| --- |' + ' --- |' * len(bands))
        for n in names:
            g = r['groups'][f'as built | {n}']
            cells = []
            for b in bands:
                e = g[b]
                t = [e['saved_a_table'][0] * a.board, e['saved_a_table'][1] * a.board]
                cells.append(f"{e['log_weight_gain'][0]:+.2f} n, {pm(t)} t")
            print(f'| {n} | ' + ' | '.join(cells) + ' |')
        print(f'\nPaired against {a.against} on the same decisions: nats a decision more, tricks a board more, IMPs a board at '
              f'{a.imps_a_trick:g} a trick.\n')
        print('| Reading | ' + ' | '.join(bands) + ' |')
        print('| --- |' + ' --- |' * len(bands))
        for n in names:
            if n == a.against or f'paired | {n}' not in r['groups']:
                continue
            g = r['groups'][f'paired | {n}']
            cells = []
            for b in bands:
                if b not in g:
                    cells.append('')
                    continue
                e = g[b]
                t = [e['a_table'][0] * a.board, e['a_table'][1] * a.board]
                cells.append(f"{e['log_weight_more'][0]:+.2f} n, {pm(t)} t, {t[0] * a.imps_a_trick:+.2f} IMPs")
            print(f'| {n} | ' + ' | '.join(cells) + ' |')


if __name__ == '__main__':
    main()
