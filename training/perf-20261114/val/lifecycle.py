#!/usr/bin/env python3
"""The lifecycle table: every net's scores on each frozen validation set, side by side.

    lifecycle.py --set V1-arena=eval_a.json,eval_b.json --set V1-stu=stu_a.json [--set ...] [--order net,net,...] > table.md

Inputs are eval_nets.py reports. For each set: log-loss, exact card and regret (tricks given up by the net's card
against the labels' gaps, on rated rows) over all rows, regret by phase, and log-loss for the bots with the most rows.
"""
import argparse
import json

PHASES = ('lead', 'tricks 1-4', 'tricks 5-8', 'tricks 9-13')


def load(paths):
    nets, meta = {}, {}
    for p in paths.split(','):
        r = json.load(open(p))
        meta = dict(rows=r['rows'], sha=r['data_sha256'], data=r['data'])
        nets.update(r['nets'])
    return nets, meta


def fmt(x, d=4):
    return '-' if x is None else f'{x:.{d}f}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--set', action='append', required=True, help='NAME=report.json[,report.json]')
    ap.add_argument('--order', default='')
    ap.add_argument('--bots', type=int, default=5)
    a = ap.parse_args()
    sets = [(s.split('=', 1)[0], *load(s.split('=', 1)[1])) for s in a.set]
    order = [x for x in a.order.split(',') if x]
    for name, nets, meta in sets:
        names = [n for n in order if n in nets] + [n for n in nets if n not in order]
        first = nets[names[0]]['scores']
        bots = sorted(first['by_bot'], key=lambda b: -first['by_bot'][b]['n'])[:a.bots]
        print(f"\n### {name}: {meta['rows']:,} rows, data sha256 {meta['sha']}\n")
        head = ['net', 'params', 'log-loss', 'exact', 'regret'] + [f'regret {p}' for p in PHASES] + [f'log-loss {b}' for b in bots]
        print('| ' + ' | '.join(head) + ' |')
        print('|' + '---|' * len(head))
        for n in names:
            s = nets[n]['scores']
            al = s['all']
            row = [n, f"{nets[n]['parameters'] / 1e6:.2f}M", fmt(al['nll']), fmt(al['agree']), fmt(al['regret'])]
            row += [fmt(s['by_phase'].get(p, {}).get('regret')) for p in PHASES]
            row += [fmt(s['by_bot'].get(b, {}).get('nll')) for b in bots]
            print('| ' + ' | '.join(row) + ' |')
        rows_n = {b: first['by_bot'][b]['n'] for b in bots}
        print('\nRows by bot: ' + ', '.join(f'{b} {n:,}' for b, n in rows_n.items()))


if __name__ == '__main__':
    main()
