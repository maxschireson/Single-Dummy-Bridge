#!/usr/bin/env python3
"""Writes configs/loop-bots.json, the bots of the rollout loop's round 0, from configs/x8-bots.json.

  python training/rollout-loop-20261113/make_bots.py

Round 0's player (two ids for one bot: a pair needs distinct ids, so self-play is z0a-v2~z0b-v2):
  z0a-v2, z0b-v2    x8's 8Z (8z-ft1: Gen 8 search at tricks 1 to 2, the search blended with rollouts at tricks 3 to 6,
                    rollouts alone from trick 7, claims, declarer mixing) with rollout net v2 (plan: 768 wide, a
                    vector for each side's bot) as the rollout net. Every simulated seat is told both sides are
                    8s-32, the nearest bot v2 was trained on.
  z0a-ft1, z0b-ft1  the same with rollout net v1 (ft): 8z-ft1 itself under the loop's ids.
The gate's outside opponent:
  8p-32-v41         Gen 8 card play, copied unchanged from configs/x8-bots.json.
The leverage control (no search, no claims, no mixing; top-card seats; the sandbox matches of 13 November):
  n-v41, n-v4       policy v4.1 / v4 alone at every trick, opening lead included
  r7-v41            v4.1's card through trick 6, rollouts alone on v4.1 from trick 7
  r7x-v4, r7x-v0    the same bot with v4 / v0 playing the simulated seats (table card and prior stay v4.1)
  r7f-v4            the bot built wholly on v4 (table card, prior and simulated seats)
  r3-v41            rollouts alone on v4.1 from trick 3
"""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V41 = 'models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz'
V4 = 'models/cardplay/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz'
V0 = 'models/cardplay/gen7-policy-v0-2026-11-11/gen7_policy_v0.npz'
V2 = 'models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz'       # transfer/rollout-net-v2-20261113 runs/w768/policy_epoch5.npz
Z = ['z0a-v2', 'z0b-v2', 'z0a-ft1', 'z0b-ft1']
CONTROL = ['n-v41', 'n-v4', 'r7-v41', 'r7x-v4', 'r7x-v0', 'r7f-v4', 'r3-v41']


def main():
    x8 = json.loads((ROOT / 'configs/x8-bots.json').read_text())
    bots = {}

    def z(label, rollout=None, names=None):
        b = copy.deepcopy(x8['8z-ft1'])
        b['label'] = label
        if rollout:
            b['rollout_policy'] = rollout
        if names:
            b['x8']['names'] = names
        b['x8']['capture'] = {'level': 1, 'forks': 8, 'audit': 'features', 'audit_search': False}
        b['x8']['claims']['opponents'] = sorted(set(b['x8']['claims']['opponents']) | set(Z))
        b['x8']['mix']['read_declarer'] = sorted(set(b['x8']['mix']['read_declarer']) | set(Z))
        for name in Z:
            b['gen7']['opponent_play_weight'][name] = 1.0
        return b

    for name in Z[:2]:
        bots[name] = z('Loop round 0: 8Z with rollout net v2 (every simulated seat read as 8s-32) as the rollout net; records kept, '
                       'no audit search', V2, {'self': '8s-32', '*': '8s-32'})
    for name in Z[2:]:
        bots[name] = z('Loop round 0 comparison: 8Z with rollout net v1 (ft), x8\'s 8z-ft1 under the loop\'s ids')
    bots['8p-32-v41'] = copy.deepcopy(x8['8p-32-v41'])        # no opponent_play_weight of its own: it reads every opponent at 1.0

    net = copy.deepcopy(x8['n-v41'])
    bots['n-v41'] = net
    bots['n-v4'] = dict(copy.deepcopy(net), gen7_policy=V4, label='Policy v4 alone: no search at any trick')
    g7 = copy.deepcopy(x8['8xl0-v41']['gen7'])
    g7['search_from_trick'] = 14
    for name in CONTROL:
        g7['opponent_play_weight'][name] = 1.0

    def roll(label, first=7, table=V41, inside=V41):
        return {'base': '6-32', 'label': label, 'engine': 'gen8x', 'policy_role': 'gen8x', 'gen7_policy': table, 'rollout_policy': inside,
                'gen7': copy.deepcopy(g7),
                'x8': {'stages': [{'from_trick': first, 'to_trick': 13, 'mode': 'rollout', 'layouts': 128, 'first': 32, 'cards': 4, 'prior': 0.02,
                                   'race': 2.5, 'slack': 0.05, 'seat': 'top'}],
                       'claims': {'cards': 0}, 'capture': {'level': 0, 'forks': 0}, 'mix': {}}}

    bots['r7-v41'] = roll("Control: policy v4.1's top card through trick 6, rollouts alone on v4.1 from trick 7 (128 layouts, top-card seats); "
                          'no search, no claims, no mix')
    bots['r7x-v4'] = roll("Control: r7-v41 with policy v4 playing the simulated seats (table card and prior stay v4.1)", inside=V4)
    bots['r7x-v0'] = roll("Control: r7-v41 with policy v0 playing the simulated seats (table card and prior stay v4.1)", inside=V0)
    bots['r7f-v4'] = roll("Control: the rollout bot built wholly on policy v4 (table card, prior and simulated seats)", table=V4, inside=V4)
    bots['r3-v41'] = roll("Control: policy v4.1's top card at the lead and tricks 1 to 2, rollouts alone on v4.1 from trick 3", first=3)
    out = ROOT / 'configs/loop-bots.json'
    out.write_text(json.dumps(bots, indent=1) + '\n')
    print(out, sorted(bots))


if __name__ == '__main__':
    main()
