#!/usr/bin/env python3
"""Writes configs/loop-bots.json, the bots of the rollout loop's round 0, from configs/x8-bots.json.

  python training/rollout-loop-20261113/make_bots.py

Stu (Max's name for the loop's bot, 13 November 09:05 UTC), round 0. Two ids for one bot, because a pair needs distinct
ids: self-play is stu0a~stu0b.
  stu0a, stu0b      x8's 8Z (8z-ft1: Gen 8 search at tricks 1 to 2, the search blended with rollouts at tricks 3 to 6,
                    rollouts alone from trick 7, claims, declarer mixing) with rollout net v2 (plan: 768 wide, a
                    vector for each side's bot) as the rollout net. Every simulated seat is told both sides are
                    8s-32, the nearest bot v2 was trained on. Records keep every layout's result for every candidate
                    (capture level 2, up to 128 layouts), so a target other than mean tricks can be rebuilt later.
The ladder (Max, 13 November 09:24 UTC: calibrate also with rollouts one trick sooner, at a higher weight, and pure):
round 0's Stu with only the boundary between search and rollouts moved. Each is measured against 8p-32-v41 on the gate's
deals, which are never trained on.
  stu0-b50          the blend at tricks 3 to 6 at trust 0.5 (Stu: 0.25)
  stu0-r6           rollouts alone from trick 6 (the blend at tricks 3 to 5)
  stu0-r3           rollouts alone from trick 3 (the search at tricks 1 to 2 only)
  stu0-p            pure: the net's own opening lead, rollouts alone from the second card on; no double dummy anywhere.
                    The claims stay (the exact single-dummy solver).
Copied unchanged from configs/x8-bots.json:
  8z-ft1            x8's 8Z with rollout net v1 (ft), for comparisons with Stu
  8p-32-v41         Gen 8 card play, the gate's outside opponent
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
STU = ['stu0a', 'stu0b']
FAMILY = STU + ['stu0-b50', 'stu0-r6', 'stu0-r3', 'stu0-p']      # every bot that claims and mixes as Stu does
CONTROL = ['n-v41', 'n-v4', 'r7-v41', 'r7x-v4', 'r7x-v0', 'r7f-v4', 'r3-v41']


def main():
    x8 = json.loads((ROOT / 'configs/x8-bots.json').read_text())
    bots = {}

    for name in STU:
        b = copy.deepcopy(x8['8z-ft1'])
        b['label'] = ('Stu, round 0: 8Z with rollout net v2 as the rollout net (every simulated seat read as 8s-32); every '
                      "layout's result kept for every candidate; no audit search")
        b['rollout_policy'] = V2
        b['x8']['names'] = {'self': '8s-32', '*': '8s-32'}
        b['x8']['capture'] = {'level': 2, 'layouts': 128, 'forks': 8, 'audit': 'features', 'audit_search': False}
        b['x8']['claims']['opponents'] = sorted(set(b['x8']['claims']['opponents']) | set(FAMILY))
        b['x8']['mix']['read_declarer'] = sorted(set(b['x8']['mix']['read_declarer']) | set(FAMILY))
        for other in FAMILY:
            b['gen7']['opponent_play_weight'][other] = 1.0
        bots[name] = b
    blend = dict(bots['stu0a']['x8']['stages'][0])
    rollout = dict(bots['stu0a']['x8']['stages'][1])
    assert (blend['mode'], blend['from_trick'], blend['to_trick'], rollout['mode'], rollout['from_trick']) == ('blend', 3, 6, 'rollout', 7)

    def rung(label, stages, search_from=None):
        b = copy.deepcopy(bots['stu0a'])
        b['label'] = 'Stu round 0 ladder: ' + label
        b['x8']['stages'] = stages
        if search_from is not None:
            b['gen7']['search_from_trick'] = search_from
        return b

    bots['stu0-b50'] = rung('the blend at tricks 3 to 6 at trust 0.5', [dict(blend, trust=.5), rollout])
    bots['stu0-r6'] = rung('rollouts alone from trick 6', [dict(blend, to_trick=5), dict(rollout, from_trick=6)])
    bots['stu0-r3'] = rung('rollouts alone from trick 3', [dict(rollout, from_trick=3)])
    bots['stu0-p'] = rung("pure: the net's opening lead, rollouts alone from the second card on, no double dummy", [dict(rollout, from_trick=1)],
                          search_from=14)
    bots['8z-ft1'] = copy.deepcopy(x8['8z-ft1'])
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
