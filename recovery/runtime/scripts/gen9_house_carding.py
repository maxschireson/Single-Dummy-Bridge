#!/usr/bin/env python3
"""G9-S6: the house bots' own carding, measured against declared schemes.

Gen 9 work in progress (sam, signals). For every recorded main table, the defenders' spot cards and
opening leads are scored against each candidate scheme with signal_experience.occasions: how often
the card played is the one the scheme prescribes for the true hand. Two populations: the full class
held (what a reader of these bots sees), and the class cut to the bot's own tie set (what its
tie-break actually chose among). For a two-message signal, chance is 1/2 against the full class only
if no middle spot is played, so the share of middle spots is reported beside it.

  python scripts/gen9_house_carding.py EPISODES [EPISODES ...] --out house_carding.json
"""
import argparse
from collections import defaultdict
import glob
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.core import Board, card  # noqa: E402
from bridge_harness.signal_experience import honesty, occasions, replay_plays  # noqa: E402
from bridge_harness.signals import SignalModel  # noqa: E402

BASE = dict(length_lead_vs_suit='4th', length_lead_vs_nt='4th', lead_from_ak='ace', honor_sequence_lead='top',
            signal_on_partner_lead='attitude', signal_on_declarer_lead='count', first_discard='attitude', trump_signal='count')
SCHEMES = {
    'standard': dict(BASE, attitude='standard', count='standard'),
    'upside_down': dict(BASE, attitude='upside_down', count='upside_down'),
    'count_on_partner_std': dict(BASE, signal_on_partner_lead='count', attitude='standard', count='standard'),
    'count_on_partner_ud': dict(BASE, signal_on_partner_lead='count', attitude='upside_down', count='upside_down'),
    'suitpref_on_partner': dict(BASE, signal_on_partner_lead='suit_preference', signal_on_declarer_lead='suit_preference'),
    'discards_odd_even': dict(BASE, first_discard='odd_even'),
    'discards_lavinthal': dict(BASE, first_discard='lavinthal'),
    'leads_3rd_5th': dict(BASE, length_lead_vs_suit='3rd_5th', length_lead_vs_nt='3rd_5th', lead_from_ak='king'),
    'leads_attitude': dict(BASE, length_lead_vs_suit='attitude', length_lead_vs_nt='attitude', honor_sequence_lead='rusinow'),
}


def ties(a):
    t = a.get('proposal_probabilities') or a.get('behavior_probabilities') or {}
    return {card(k) for k, p in t.items() if p > 0}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('episodes', nargs='+')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    models = {k: SignalModel(v) for k, v in SCHEMES.items()}
    tally = defaultdict(lambda: [0, 0, 0.])         # (bot, scheme, population, key) -> [hits, occasions, sum of 1/n]
    tables = 0
    for path in sorted(f for d in args.episodes for f in glob.glob(str(Path(d) / '*.json.gz'))):
        with gzip.open(path, 'rt') as f:
            episode = json.load(f)
        for record in episode['unique_tables'].values():
            board = Board.from_dict(record['board'])
            main_tables = [t for t in record['tables'] if t.get('depth', 0) == 0]
            if board.contract is None or not main_tables:
                continue
            actions = main_tables[0]['actions']
            plays = replay_plays(board, actions)
            allowed = {i: ties(a) for i, a in enumerate(actions)}
            tables += 1
            side = 1 - board.contract.declarer % 2
            roles = {a['player'] for a in actions if 'NESW'.index(a['seat']) % 2 == side}
            if len(roles) != 1:
                continue
            bot = episode.get(roles.pop(), '?')
            for name, model in models.items():
                for population, cut in (('class', None), ('ties', allowed)):
                    for key, n, s, hit in occasions(board, plays, model, side, cut):
                        t = tally[(bot, name, population, key)]
                        t[0] += hit
                        t[1] += 1
                        t[2] += 1 / n
    out = defaultdict(dict)
    for (bot, name, population, key), (hits, total, chance) in sorted(tally.items()):
        stat = {'kind': 'count', 'n': {'hit/2': float(hits), 'all/2': float(total)}} if not key.startswith('lead') else None
        h = honesty(stat, prior_mean=.5, prior_n=2., eps=0.) if stat else (None, None)
        out[bot][f'{name}|{population}|{key}'] = dict(occasions=total, hit_rate=round(hits / total, 4), chance=round(chance / total, 4),
                                                    honesty=None if h[0] is None else round(h[0], 3), sd=None if h[1] is None else round(h[1], 3))
    Path(args.out).write_text(json.dumps(dict(tables=tables, schemes=SCHEMES, bots=out), indent=1))
    print(f'{tables} tables')
    for bot, rows in out.items():
        print(f'\n{bot}')
        for k, v in rows.items():
            if v['occasions'] >= 30:
                print(f"  {k:>62} n={v['occasions']:5d} hit={v['hit_rate']:.3f} chance={v['chance']:.3f} h={v['honesty']}")


if __name__ == '__main__':
    main()
