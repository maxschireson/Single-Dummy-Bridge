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
Pure Stu as the main line (Max, 11:25 UTC: "Should we just do pure Stu (with single dummy guarantee)?"; 11:27: "I don't
mind a different lead"):
  stu0-pa, stu0-pb  stu0-p under two ids, so that it can play itself (the collection `sp0`)
  stu0-pl           stu0-p with the searched opening lead Stu-as-is and Gen 8 play, in place of the net's own lead. The
                    gap between stu0-pl and stu0-p on the same deals is what the net's lead costs.
The opening lead from rollouts (Max, 11:29 UTC: "we could try rollouts for the lead but with more layouts and more choices
- try everything for 512 because you don't know, and let the rollouts teach you... Same methodology but different
parameters"):
  stu0-pr           stu0-p with the lead rolled out (x8_player's `lead` block): every distinct lead (touching cards are one)
                    on 512 layouts of the three hidden hands, drawn as the search draws them for its own lead; none is
                    dropped on the way; the seats are drawn from the net as at every other trick. The record keeps all 512
                    layouts with every lead's result in each.
  stu0-pra, stu0-prb    stu0-pr under two ids, for self-play
  stu0-pt           stu0-p with rollout net v2 at the table as well (its lead, its first choices, its reading of the play),
                    in place of policy v4.1: the control for stu2-pt
  stu0-pv           stu0-p whose simulated seats play by rollout net v2's value head (`seat: blend`): the control for stu2-pv
Round 2 (PLAN.md): round 1's net with every weight trained on pure Stu's games, its rows named `stup0`:
  stu2-p            pure Stu with that net in the rollouts, told its own side is stup0 and Gen 8 card play is 8s-32
  stu2-pr           the same with the opening lead rolled out
  stu2-pt           stu2-p with that net at the table as well: what it learned of leads and first choices shows here
  stu2-pv           stu2-p whose simulated seats play the card with the best log-probability minus ten times the net's
                    value head (`seat: blend`), where round 0's draw from its probabilities: the rollout values put to use
  stu2-n            that net alone
  stu2-ns           round 2's longer-trained variant alone (train-r2s/: the same rows, the epoch best on pure Stu's held-out
                    cards with the other bots' log-loss within 0.02 of the start, epoch 5 where round 2's net is epoch 1)
Round 3 (told its own side is stup0): stu3a-n the interim net alone (train-r3a/, about half of round 3's tables);
stu3-n round 3's net alone (train-r3/); stu3-p, stu3-pr pure Stu and pure Stu with rolled-out leads with round 3's net
inside, and stu3-pa/-pb, stu3-pra/-prb the same under two ids for self-play; stu3-ps (-psa/-psb) with the lead as stu0-ps.
  stu0-ps, stu0-psa, stu0-psb  pure with the opening lead rolled out on the settings of every other card (Max, 22:16 UTC)
The same five bots with rollout net v1 (ft) inside (Max, 09:27 UTC: "We should measure v1 rungs too"). v1 takes no bot
names. stu0v1 is x8's 8z-ft1 with the loop's records and lists.
  stu0v1, stu0v1-b50, stu0v1-r6, stu0v1-r3, stu0v1-p
The nets alone, as the ladder's lowest rung (the dashboard session's ask for Max, 09:58 UTC: how a net's improvement shows
without rollouts as well as with them): the net's first card at every trick, no search, no rollouts, no claims, no mixing.
  stu0-n            rollout net v2, told both sides are 8s-32 as Stu's rollouts tell it
  stu0v1-n          rollout net v1 (ft)
Round 1 (PLAN.md): the same bots with round 1's net inside (models/cardplay/stu-net-r1-20261113/policy.npz, fetched
from train-r1/ on azure5's transfer branch). The net is told its own side is Stu (`stu0`, the name of Stu's rows in
its training set) and the other side is Stu too, except the outside opponent 8p-32-v41, which it is told is 8s-32.
  stu1a, stu1b      round 1's Stu (two ids for self-play)
  stu1-b50, stu1-r6, stu1-r3, stu1-p, stu1-n      its ladder
Copied unchanged from configs/x8-bots.json:
  8z-ft1            x8's 8Z with rollout net v1 (ft)
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
RUNGS = ['-b50', '-r6', '-r3', '-p']
STU1 = ['stu1a', 'stu1b']
FAMILY = (STU + ['stu0' + r for r in RUNGS] + ['stu0v1'] + ['stu0v1' + r for r in RUNGS]
          + STU1 + ['stu1' + r for r in RUNGS] + ['stu0-pa', 'stu0-pb', 'stu0-pl']
          + ['stu0-pr', 'stu0-pra', 'stu0-prb'] + ['stu0-pt', 'stu0-pv', 'stu2-p', 'stu2-pr', 'stu2-pt', 'stu2-pv']
          + ['stu3-p', 'stu3-pr', 'stu3-pa', 'stu3-pb', 'stu3-pra', 'stu3-prb']
          + ['stu0-ps', 'stu0-psa', 'stu0-psb', 'stu3-ps', 'stu3-psa', 'stu3-psb'])   # every bot that claims and mixes as Stu does
LEAD = {'layouts': 512, 'seat': 'draw', 'capture': 512}        # cards 13, prior 0, race 0 are the block's defaults: every lead, every layout
R1 = 'models/cardplay/stu-net-r1-20261113/policy.npz'          # train-r1/policy.npz on transfer/rollout-loop-azure5-20261113
BEN = {'ben64': 'ben64', 'ben': 'ben'}      # against BEN the net is told so (v2 knows both from BEN's own cards); no other match changes
NAMES1 = {'self': 'stu0', '*': 'stu0', '8p-32-v41': '8s-32', **BEN}
R2 = 'models/cardplay/stu-net-r2-20261113/policy.npz'          # train-r2/policy.npz on transfer/rollout-loop-azure5-20261113
NAMES2 = {'self': 'stup0', '*': 'stup0', '8p-32-v41': '8s-32', **BEN}
R2S = 'models/cardplay/stu-net-r2s-20261113/policy.npz'        # train-r2s/policy.npz on the same branch
R3A = 'models/cardplay/stu-net-r3a-20261113/policy.npz'        # train-r3a/policy.npz on the same branch: the interim round
R3 = 'models/cardplay/stu-net-r3-20261113/policy.npz'          # train-r3/policy.npz on the same branch
V1 = 'models/cardplay/rollout-net-v1-20261113/policy_ft.npz'
CONTROL = ['n-v41', 'n-v4', 'r7-v41', 'r7x-v4', 'r7x-v0', 'r7f-v4', 'r3-v41']


def main():
    x8 = json.loads((ROOT / 'configs/x8-bots.json').read_text())
    bots = {}

    for name in STU:
        b = copy.deepcopy(x8['8z-ft1'])
        b['label'] = ('Stu, round 0: 8Z with rollout net v2 as the rollout net (every simulated seat read as 8s-32); every '
                      "layout's result kept for every candidate; no audit search")
        b['rollout_policy'] = V2
        b['x8']['names'] = {'self': '8s-32', '*': '8s-32', **BEN}
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
    for twin in ('stu0-pa', 'stu0-pb'):                        # pure Stu under two ids, for self-play
        bots[twin] = copy.deepcopy(bots['stu0-p'])
    bots['stu0-pl'] = copy.deepcopy(bots['stu0-p'])
    bots['stu0-pl']['label'] = ('Stu round 0 ladder: pure with a searched opening lead (the search decides the lead as in Stu-as-is; rollouts '
                                'alone from the second card on)')
    bots['stu0-pl']['gen7']['search_from_trick'] = 1            # no `lead` block: the lead falls to the search
    for name in ('stu0-pr', 'stu0-pra', 'stu0-prb'):
        b = copy.deepcopy(bots['stu0-p'])
        b['label'] = ('Stu round 0 ladder: pure with the opening lead from rollouts (every distinct lead on 512 layouts of the three hidden '
                      'hands, none dropped; rollouts alone from the second card on)')
        b['x8']['lead'] = dict(LEAD)
        bots[name] = b
    # Max, 22:16 UTC on 13 November: the lead rolled out as every other card is (the stage's own candidates, layouts and
    # race), in place of every lead card on 512 layouts: cheaper, and it still gives the net a rated lead to learn from.
    stage = bots['stu0-p']['x8']['stages'][0]
    for name in ('stu0-ps', 'stu0-psa', 'stu0-psb'):
        b = copy.deepcopy(bots['stu0-p'])
        b['label'] = ("Stu round 0 ladder: pure with the opening lead from rollouts on the same settings as every other card "
                      f"(at most {stage['cards']} candidates by the net's prior, {stage['first']} then up to {stage['layouts']} layouts with the race); "
                      'rollouts alone from the second card on')
        b['x8']['lead'] = {k: v for k, v in stage.items() if k not in ('from_trick', 'to_trick', 'mode')}
        bots[name] = b
    for name in ['stu0' + r for r in RUNGS]:                    # the same rungs with rollout net v1 (ft), which takes no names
        b = copy.deepcopy(bots[name])
        b['label'] = b['label'].replace('Stu round 0 ladder: ', 'Stu round 0 ladder, rollout net v1 (ft) inside: ')
        b['rollout_policy'] = V1
        del b['x8']['names']
        bots[name.replace('stu0', 'stu0v1')] = b
    b = copy.deepcopy(bots['stu0a'])
    b['label'] = "Stu round 0 ladder, rollout net v1 (ft) inside: Stu's own stages (x8's 8z-ft1 with the loop's records and lists)"
    b['rollout_policy'] = V1
    del b['x8']['names']
    bots['stu0v1'] = b
    assert x8['8z-ft1']['rollout_policy'] == V1

    def alone(label, policy, names=None):
        b = {'base': '6-32', 'label': 'Stu round 0 ladder: ' + label, 'engine': 'gen8x', 'policy_role': 'gen8x', 'gen7_policy': policy,
             'gen7': copy.deepcopy(x8['n-v41']['gen7']),
             'x8': {'stages': [], 'claims': {'cards': 0}, 'capture': {'level': 0, 'forks': 0}, 'mix': {}}}
        assert b['gen7']['search_from_trick'] == 14 and not b['gen7']['net_sample']
        if names:
            b['x8']['names'] = names
        return b

    bots['stu0-n'] = alone('rollout net v2 alone, told both sides are 8s-32: its first card at every trick, no search, no rollouts, no claims',
                           V2, {'self': '8s-32', '*': '8s-32', **BEN})
    bots['stu0v1-n'] = alone('rollout net v1 (ft) alone: its first card at every trick, no search, no rollouts, no claims', V1)
    # Round 1: round 0's bots with round 1's net in place of rollout net v2, and the names it was trained with.
    for old, new in zip(STU, STU1):
        b = copy.deepcopy(bots[old])
        b['label'] = ("Stu, round 1: round 0's Stu with round 1's net as the rollout net (its own side read as stu0, Gen 8 card play as "
                      '8s-32, any other opponent as stu0)')
        b['rollout_policy'] = R1
        b['x8']['names'] = dict(NAMES1)
        bots[new] = b
    for r in RUNGS:
        b = copy.deepcopy(bots['stu0' + r])
        b['label'] = b['label'].replace('Stu round 0 ladder: ', "Stu round 1 ladder (round 1's net inside): ")
        b['rollout_policy'] = R1
        b['x8']['names'] = dict(NAMES1)
        bots['stu1' + r] = b
    bots['stu1-n'] = alone("round 1's net alone, told its own side is stu0: its first card at every trick, no search, no rollouts, no claims",
                           R1, dict(NAMES1))
    bots['stu1-n']['label'] = bots['stu1-n']['label'].replace('Stu round 0 ladder: ', 'Stu round 1 ladder: ')
    # Round 2: pure Stu with round 2's net, and the control with v2 at the table.
    bots['stu0-pt'] = dict(copy.deepcopy(bots['stu0-p']), gen7_policy=V2,
                           label='Stu round 0 ladder: pure, with rollout net v2 at the table as well (its lead, first choices and reading of the play)')
    bots['stu0-pv'] = copy.deepcopy(bots['stu0-p'])
    bots['stu0-pv']['label'] = "Stu round 0 ladder: pure, the simulated seats playing by rollout net v2's value head (seat blend) in place of a draw"
    bots['stu0-pv']['x8']['stages'] = [dict(st, seat='blend') for st in bots['stu0-pv']['x8']['stages']]
    for name, base, change in (('stu2-p', 'stu0-p', {}), ('stu2-pr', 'stu0-pr', {}), ('stu2-pt', 'stu0-p', {'gen7_policy': R2}),
                               ('stu2-pv', 'stu0-p', {})):
        b = dict(copy.deepcopy(bots[base]), rollout_policy=R2, **change)
        b['x8']['names'] = dict(NAMES2)
        b['label'] = ("Stu round 2 ladder (round 2's net inside, its own side read as stup0): "
                      + {'stu2-p': "pure: policy v4.1's lead, rollouts alone from the second card on",
                         'stu2-pr': 'pure with the opening lead from rollouts',
                         'stu2-pt': "pure, with round 2's net at the table as well (its lead, first choices and reading of the play)",
                         'stu2-pv': "pure, the simulated seats playing by the net's value head (seat blend) in place of a draw"}[name])
        if name == 'stu2-pv':
            b['x8']['stages'] = [dict(st, seat='blend') for st in b['x8']['stages']]
        bots[name] = b
    bots['stu2-n'] = alone("round 2's net alone, told its own side is stup0: its first card at every trick, no search, no rollouts, no claims",
                           R2, dict(NAMES2))
    bots['stu2-n']['label'] = bots['stu2-n']['label'].replace('Stu round 0 ladder: ', 'Stu round 2 ladder: ')
    bots['stu2-ns'] = alone("round 2's longer-trained net (epoch 5) alone, told its own side is stup0: its first card at every trick", R2S, dict(NAMES2))
    bots['stu2-ns']['label'] = bots['stu2-ns']['label'].replace('Stu round 0 ladder: ', 'Stu round 2 ladder: ')
    for name, base in (('stu3-p', 'stu0-p'), ('stu3-pa', 'stu0-p'), ('stu3-pb', 'stu0-p'), ('stu3-pr', 'stu0-pr'), ('stu3-pra', 'stu0-pr'),
                       ('stu3-prb', 'stu0-pr'), ('stu3-ps', 'stu0-ps'), ('stu3-psa', 'stu0-ps'), ('stu3-psb', 'stu0-ps')):                 # round 3's net inside pure Stu; -pa/-pb, -pra/-prb: two ids for self-play
        b = dict(copy.deepcopy(bots[base]), rollout_policy=R3)
        b['x8']['names'] = dict(NAMES2)
        b['label'] = ("Stu round 3 ladder (round 3's net inside, its own side read as stup0): "
                      + {'stu0-p': "pure: policy v4.1's lead, rollouts alone from the second card on", 'stu0-pr': 'pure with the opening lead from rollouts',
                         'stu0-ps': 'pure with the opening lead from rollouts on the settings of every other card'}[base])
        bots[name] = b
    for name, path, what in (('stu3a-n', R3A, "the interim round 3 net (about half of round 3's tables)"), ('stu3-n', R3, "round 3's net")):
        bots[name] = alone(what + ' alone, told its own side is stup0: its first card at every trick, no search, no rollouts, no claims',
                           path, dict(NAMES2))
        bots[name]['label'] = bots[name]['label'].replace('Stu round 0 ladder: ', 'Stu round 3 ladder: ')
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
