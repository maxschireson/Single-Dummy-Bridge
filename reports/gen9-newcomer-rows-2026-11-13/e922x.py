"""Exploratory, beside E9-22 (g9): how well rollout net v2 predicts the card play of bots it never saw, with the generic
row against the nearest known bot's row, on the Gen 9 cohort's boards (the registered population, the arrival run's
guests, has no recorded card decisions).

Newcomers to v2: 9a-32 and 8p-32 (not in its vocabulary). Control: 8s-32 and 71s-32 (in it). For each card decision
with a choice, by the bot in question as the deciding side (declarer for dummy's cards too), the log-loss of the card
it played under each row of the deciding side: '' (generic) and the rows listed in --rows; the other side's row is
its bot's own if v2 knows it, else ''.

usage: python3 e922x.py OUT.json BOARDS.json [...] --repo REPO --net NET.npz --scorer SCORER.npz [--rows 8s-32,71s-32,6-32]
"""
import collections
import json
import math
import sys

import numpy as np


def arg(flag, default=None, cast=str):
    return cast(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default


sys.path.insert(0, arg('--repo'))
from bridge_harness.core import Board, Game, card                  # noqa: E402
from bridge_harness.gen6_nets import FitScorer                      # noqa: E402
from bridge_harness.gen7_net import PolicyNet                       # noqa: E402

TARGETS = ('9a-32', '8p-32', '8s-32', '71s-32')


def main():
    out_path = sys.argv[1]
    files = [a for a in sys.argv[2:] if a.endswith('.json') and not a.startswith('--')]
    rows = [''] + [r for r in arg('--rows', '8s-32,71s-32,6-32').split(',') if r]
    net = PolicyNet(arg('--net'), FitScorer(arg('--scorer')))
    obs = collections.defaultdict(list)           # (bot, opponent) -> [(observation, card played)]
    for fn in files:
        for b in json.load(open(fn)).values():
            own = (b.get('conditions') or {}).get('own')
            if not own:
                continue
            for t in own['tables']:
                if t['declarer'] is None or not t['plays']:
                    continue
                d = dict(b['board'], contract=t['contract'], declarer=t['declarer'], auction=t['auction'])
                game = Game(Board.from_dict(d))
                names = t['assignments']
                for p in t['plays']:
                    o = game.observation()
                    c = card(p[1:])
                    bot = names[o.controller]
                    if bot in TARGETS and len(o.legal) > 1:
                        obs[(bot, names[(o.controller + 1) % 4])].append((o, c))
                    game.play(c)
    result, arrays = {}, {}
    for (bot, opp), items in sorted(obs.items()):
        other = opp if opp in net.vocab else ''
        os_, cs = [o for o, _ in items], np.array([c for _, c in items])
        res = {}
        for r in rows + ([bot] if bot in net.vocab and bot not in rows else []):
            net.who = (r, other)
            lp = net.log_policy(os_)
            arrays[f'{bot}|{opp}|{r or "generic"}'] = -lp[np.arange(len(cs)), cs]
            res[r or 'generic'] = float(-lp[np.arange(len(cs)), cs].mean())
            res[(r or 'generic') + '_se'] = float(lp[np.arange(len(cs)), cs].std(ddof=1) / math.sqrt(len(cs)))
        result[f'{bot} vs {opp}'] = dict(n=len(items), other_row=other or 'generic', nll=res)
        print(bot, 'vs', opp, len(items), {k: round(v, 4) for k, v in res.items() if not k.endswith('_se')}, flush=True)
    json.dump(result, open(out_path, 'w'), indent=1)
    np.savez_compressed(out_path.replace('.json', '-nll.npz'), **arrays)     # per decision, in board order


if __name__ == '__main__':
    main()
