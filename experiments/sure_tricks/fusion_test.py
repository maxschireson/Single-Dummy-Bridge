#!/usr/bin/env python3
"""Run a declarer over the strategy-fusion deal sets and score it by set.

    python fusion_test.py fusion_deals.json --bot gen6 --seeds 2
    python fusion_test.py fusion_deals.json --bot pimc-make --seeds 10 --sets A6,B6
    python fusion_test.py fusion_deals.json --bot gen7 --seeds 5 --out gen7.jsonl

The bot plays declarer and dummy from the fixed opening lead; fusionlab.OracleDefender defends.
A set is passed in a seed only if the contract is made in every layout of the set: the layouts of a set
look alike to declarer until the critical decision and share one random stream per seed, so a line that
needs a guess fails at least one of them.

Bots: pimc-make | pimc-tricks | pimc-score (bridge_harness.players.PIMCPlayer, uniform layouts, 32 samples;
append -N for N samples), gen6 (local 6-32 as built in scripts/gen7_check.py), gen7 (the 7s-32 block of
configs/round7-candidate-phase1.json), gen7-notree. To test another player, pass any object with
.choose(observation, rng) to fusionlab.run().

Set SDB_ROOT to the Single-Dummy-Bridge checkout (DDS built, model files restored).
"""
import argparse
import collections
import json
import time

from fusionlab import Board, DDS, SEATS, make_bot, run, tricks_text

KEYS = ('id', 'hands', 'contract', 'declarer', 'dealer', 'vulnerability', 'auction', 'opening_lead')


def board(d):
    """The Board is given its set's id, not its own: runner.decision_rng seeds each decision from the board
    id, the seed and the history, so with one id the layouts of a set get the same random stream and a
    declarer makes the same choice in each of them until it has seen something different."""
    return Board.from_dict(dict({k: d[k] for k in KEYS}, id=d['set']))


def play(d, bot, seed, dds, plain=False):
    b = board(d)
    t = run(b, bot, avoid='' if plain else d.get('avoid', ''), seed=seed, dds=dds, critical=() if plain else d.get('critical', ()))
    need = b.contract.level + 6
    return dict(deal=d['id'], set=d['set'], seed=seed, tricks=t['declarer_tricks'], made=t['declarer_tricks'] >= need,
                play=tricks_text(t['actions']),
                est=[dict(ply=a['ply'], seat=a['seat'], card=a['card'], tree=a.get('gen7_tree', {}).get('consulted'),
                          est={k: round(v['utility'], 3) for k, v in a['estimates'].items()})
                     for a in t['actions'] if a.get('estimates') and a['controller'] == SEATS[b.contract.declarer]])


def summarise(rows, sets):
    by = collections.defaultdict(dict)
    for r in rows:
        by[r['seed']][r['deal']] = r['made']
    out = []
    for st in sets:
        seeds = [s for s in by if all(d in by[s] for d in st['deals'])]
        if not seeds:
            continue
        per_deal = {d: sum(by[s][d] for s in seeds) for d in st['deals']}
        passed = sum(all(by[s][d] for d in st['deals']) for s in seeds)
        out.append(dict(set=st['id'], kind=st['kind'], seeds=len(seeds), passed=passed, per_deal=per_deal))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('deals')
    p.add_argument('--bot', required=True)
    p.add_argument('--seeds', type=int, default=2)
    p.add_argument('--sets')
    p.add_argument('--out')
    p.add_argument('--plain-defence', action='store_true', help='double-dummy defender with no tie-break rules')
    a = p.parse_args()
    data = json.load(open(a.deals))
    only = set(a.sets.split(',')) if a.sets else None
    sets = [s for s in data['sets'] if not only or s['id'] in only]
    deals = {d['id']: d for d in data['deals']}
    bot, dds, rows = make_bot(a.bot), DDS(cache_path=''), []
    f = open(a.out, 'a') if a.out else None
    started = time.time()
    for st in sets:
        for did in st['deals']:
            for seed in range(1, a.seeds + 1):
                r = play(deals[did], bot, seed, dds, a.plain_defence)
                r['bot'] = a.bot
                rows.append(r)
                if f:
                    f.write(json.dumps(r) + '\n')
                    f.flush()
    print('%s, %d seeds, %.0f s' % (a.bot, a.seeds, time.time() - started))
    for s in summarise(rows, sets):
        cells = '  '.join('%s %d/%d' % (d, n, s['seeds']) for d, n in s['per_deal'].items())
        print('  %-4s %-9s set passed %d/%d   %s' % (s['set'], s['kind'], s['passed'], s['seeds'], cells))


if __name__ == '__main__':
    main()
