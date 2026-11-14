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
          + ['stu0-ps', 'stu0-psa', 'stu0-psb', 'stu3-ps', 'stu3-psa', 'stu3-psb', 'stuS-ps', 'stuM-ps', 'stu3-pst',
             'stu3-p2', 'stu3-pg', 'stu0-p2', 'stu3-px', 'stu3-pu', 'stu3-pux', 'stu3-pm', 'stuv41-ps', 'stu3-put', 'stu3-psti', 'stu0-pst', 'stu3-psta', 'stu3-pstb', 'stu3-psu', 'stu3-putb',
             'stuhf-pst', 'stubf-pst', 'stumf-pst', 'stuhs-pst', 'stubs-pst',
             'stum10-pst', 'stum10h-pst', 'stum10h4-pst', 'stus10-pst', 'stus10h-pst',
             'stum10F-pst', 'stum10A-pst', 'stum10B-pst', 'stuhA-pst', 'stubA-pst', 'stusAh-pst',
             'stu4-pst', 'stu4-put', 'stu4-psta', 'stu4-pstb', 'stu4-putb', 'stu4c-pst', 'stu4c-put', 'stu4c-psta', 'stu4c-pstb'])   # every bot that claims and mixes as Stu does
LEAD = {'layouts': 512, 'seat': 'draw', 'capture': 512}        # cards 13, prior 0, race 0 are the block's defaults: every lead, every layout
R1 = 'models/cardplay/stu-net-r1-20261113/policy.npz'          # train-r1/policy.npz on transfer/rollout-loop-azure5-20261113
BEN = {'ben64': 'ben64', 'ben': 'ben', 'ben200': 'ben64'}   # against BEN the net is told so (v2 knows ben64 and ben from BEN's own
                                                            # cards; BEN at its upstream 200 samples is read as ben64, the nearest it knows)
NAMES1 = {'self': 'stu0', '*': 'stu0', '8p-32-v41': '8s-32', **BEN}
R2 = 'models/cardplay/stu-net-r2-20261113/policy.npz'          # train-r2/policy.npz on transfer/rollout-loop-azure5-20261113
NAMES2 = {'self': 'stup0', '*': 'stup0', '8p-32-v41': '8s-32', **BEN}
R2S = 'models/cardplay/stu-net-r2s-20261113/policy.npz'        # train-r2s/policy.npz on the same branch
R3A = 'models/cardplay/stu-net-r3a-20261113/policy.npz'        # train-r3a/policy.npz on the same branch: the interim round
R3 = 'models/cardplay/stu-net-r3-20261113/policy.npz'          # train-r3/policy.npz on the same branch
R4 = 'models/cardplay/stu-net-r4-20261113/policy.npz'          # train-r4/policy.npz: round 4, with the USBC's human tables
R4C = 'models/cardplay/stu-net-r4c-20261113/policy.npz'        # train-r4c/policy.npz: round 4's control, without them
HUMAN = 'models/cardplay/stu-exp-human-20261114'               # exp_human.sh: hf, bf, mf, hs, bs .npz
STRONG = 'models/cardplay/stu-exp-strong-20261114/strong.npz'  # exp_strong.sh: from Gen 8 card play's rows of v2's set only
MIX = 'models/cardplay/stu-exp-strong-20261114/mix.npz'        # exp_strong.sh: as many rows of v2's set, bots in its proportions
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
    # BEN at its upstream default play sampling (Max, 23:31 UTC on 13 November: "a more principled and credible baseline"):
    # BEN (64)'s spec at another address, where ben_session.sh starts servers with sample_hands_play 200 and
    # min_sample_hands_play 20 (lorserker/ben's values), every other setting as BEN (64)'s lanes.
    bots['ben200'] = {'base': 'ben64', 'url': 'http://127.0.0.1:8090', 'samples': 200, 'config': '~/work/loop/ben/ben-200.conf',
                      'label': 'BEN at its upstream play sampling (200 layouts, at least 20), otherwise as BEN (64)'}
    # SiD (rollout) Stu R3 with round 3's net at the table too (candidate priors, reading the play) in place of policy v4.1:
    # alone, round 3's net beats v4.1 +1.36 +- 0.07 head to head (h3-nv41).
    bots['stu3-pst'] = dict(copy.deepcopy(bots['stu3-ps']), gen7_policy=R3)
    bots['stu3-pst']['label'] = ("Stu round 3 ladder (round 3's net inside and at the table, its own side read as stup0): pure with the "
                                 'opening lead from rollouts on the settings of every other card')
    # How the simulated seats take their cards (03:05 UTC on 14 November, draw_regret.py): the seats DRAW from the net, and a
    # card drawn from round 3's net told it is Stu gives up more than one drawn from v2 told it is Gen 8 (its probabilities
    # are flatter: 0.94 nats against 0.55), though its most probable card gives up less. -p2: the draw sharpened (the
    # probabilities squared, `power` 2); -pg: the most probable card (`seat: top`). The lead is rolled out the same way.
    def seats(base, label, **change):
        b = copy.deepcopy(bots[base])
        b['x8']['stages'] = [dict(st, **change) for st in b['x8']['stages']]
        b['x8']['lead'] = dict(b['x8']['lead'], **change)
        b['label'] = b['label'] + '; ' + label
        return b
    bots['stu3-p2'] = seats('stu3-ps', 'the simulated seats draw from the probabilities squared (power 2)', power=2.)
    bots['stu3-pg'] = seats('stu3-ps', "the simulated seats play the net's most probable card (seat top)", seat='top')
    bots['stu0-p2'] = seats('stu0-ps', 'the simulated seats draw from the probabilities squared (power 2)', power=2.)
    # Seats by side, and a bot told nothing about its opponent (Max, 03:12 to 03:28 UTC on 14 November: we may read
    # opponents' cards better than will carry to play against people; build the randomization in; defenders' equal
    # cards random for now).
    #   -px   the seats split: its own side drawn among the cards at least half as likely as the likeliest (what a bot
    #         knows of its own partnership's play), the other side among those at least a quarter as likely
    #   -pu   blind: stu3-p told nothing about who sits against it. The simulated opponents are the net's unknown player
    #         and are told nothing about this bot; their played cards are read at the weight of an opponent never met
    #         (0.3) and as cards of a side that may play any of its equal cards (`read_declarer`, `read_defender` '*')
    #   -pux  blind, the seats split, and its own defenders play a random one of their equal cards (partner reads them so)
    SPLIT = dict(seat='draw', cut=.5, seat_other='draw', power_other=1., cut_other=.25)
    bots['stu3-px'] = seats('stu3-ps', "its own side's simulated seats drawn among the cards at least half as likely as the likeliest, "
                                       "the other side's among those at least a quarter as likely", **SPLIT)
    def blind(base, label):
        b = copy.deepcopy(bots[base])
        b['x8']['blind'] = True
        b['x8']['names'] = {'self': b['x8']['names']['self'], '*': '', 'they_see': ''}
        b['x8']['mix'] = dict(b['x8']['mix'], read_declarer=['*'], read_defender=['*'])
        b['label'] = b['label'] + '; ' + label
        return b
    bots['stu3-pu'] = blind('stu3-p', 'BLIND: told nothing about who sits against it')
    bots['stu3-pux'] = blind('stu3-p', 'BLIND, the simulated seats split by side, its defenders playing a random one of their equal cards')
    bots['stu3-pux']['x8']['stages'] = [dict(st, **SPLIT) for st in bots['stu3-pux']['x8']['stages']]
    bots['stu3-pux']['x8']['mix']['defender'] = True
    # One net, blind (04:20 UTC on 14 November): round 3's net inside and at the table beat the reference +0.16 +- 0.09
    # (h3-pt, h3-ptb) where the same net inside only stood at -0.13 +- 0.09. At the table the net reads the opponents'
    # cards, and it was trained on the reference bot's own games, so some of that may be knowledge of this opponent. -put
    # is stu3-pst told nothing about who sits against it.
    bots['stu3-put'] = blind('stu3-pst', 'BLIND: told nothing about who sits against it')
    # Max, 04:28 UTC on 14 November: "Should it really be Stu + rollouts + don't go down in a cold game or slam? Is it
    # already if not we should try that." It is where the contract is certain (the winning-line logic, 10 cards or fewer,
    # games, slams and doubled contracts). Where it is only likely the rollouts choose by mean tricks, so a card that risks
    # the contract for an overtrick can win. -psti: the one-net bot with the rollouts choosing by IMPs (the stage's
    # `objective`: each card's swing in IMPs, layout by layout, against the card with the best mean tricks), the lead too.
    bots['stu3-psti'] = seats('stu3-pst', 'the rollouts choose by IMPs in place of mean tricks', objective='imps')
    # Max, 05:14 UTC on 14 November: "In the one-net comparison do we know if one net R3 improves over earlier one net
    # versions against Ben?" Not measured: -pst for round 0, rollout net v2 inside and at the table (told what it is told
    # inside: every seat 8s-32, BEN as BEN), the lead rolled out as stu0-ps. Against BEN (200) on the deals of b3-pst200.
    bots['stu0-pst'] = dict(copy.deepcopy(bots['stu0-ps']), gen7_policy=V2)
    bots['stu0-pst']['label'] = bots['stu0-ps']['label'].replace('Stu round 0 ladder: ', 'Stu round 0 ladder, rollout net v2 inside and at the table: ')
    # The one-net bot under two ids, for its self-play as training data (Max, 05:24 UTC on 14 November: two boxes of Gen 8
    # self-play, two of Stu's, one for tests; 05:10: "Simpler to have one not two").
    # Max, 05:37 UTC: "The sooner we begin injecting a little noise into the training data the better": its defenders, as its
    # declarer already does, play a random one of their equal cards (touching cards), which costs nothing.
    for twin in ('stu3-psta', 'stu3-pstb'):
        bots[twin] = copy.deepcopy(bots['stu3-pst'])
        bots[twin]['x8']['mix'] = dict(bots[twin]['x8']['mix'], defender=True)
        bots[twin]['label'] = bots['stu3-pst']['label'] + "; its defenders too play a random one of their equal cards (under a second id, for self-play records)"
    # Max, 06:22 UTC on 14 November: "We should only grade the bot on 'blind' opponents". The two-net bot of the gate, blind
    # (stu3-pu is the net-lead bot, blind); with stu3-put (the one-net bot, blind) it is graded on BEN (200).
    bots['stu3-psu'] = blind('stu3-ps', 'BLIND: told nothing about who sits against it')
    # The USBC's deals (Max, 07:20 to 07:36 UTC on 14 November): every bot old and new plays them, in the humans' contracts where
    # the auction fits our bidding and in self-play on its own auctions. Self-play needs two ids a bot: the twins below (the
    # same bot under a second id). SiD's twins: stu3-psta/-pstb (told they face Stu: known), stu3-put/-putb (blind).
    for cid in ('1', '4b', '5RZ32', '6-32'):
        bots[f'{cid}-tw'] = {'base': cid, 'label': f'{cid} under a second id, for self-play on the USBC deals'}
    for xid in ('7s-32-v41',):
        bots[xid] = copy.deepcopy(x8[xid])
        bots[f'{xid}-tw'] = dict(copy.deepcopy(x8[xid]), label=f'{xid} under a second id, for self-play on the USBC deals')
    bots['stu3-putb'] = copy.deepcopy(bots['stu3-put'])
    bots['stu3-putb']['label'] = bots['stu3-put']['label'] + ' (under a second id, for blind self-play)'
    # Max, 09:25 to 09:39 UTC on 14 November: should the USBC's adult boards (2021 to 2023, one table a deal with an auction
    # our bidder knows; usbc/human_episodes.py) go into round 4? A net trained on the experts' cards against one trained on as
    # many of the one-net SiD's self-play boards, each fine-tuned from round 3's net and each from scratch, alone and inside
    # the one-net rollout bot (exp_human.sh). hf/hs: the human boards (the net is told every seat is usbc); bf/bs: the bot
    # boards (every seat stup0); mf: both together, playing as stup0, which is how round 4 would use the human boards.
    for tag, own, what in (('hf', 'usbc', "round 3's net fine-tuned on the USBC's human boards"),
                           ('bf', 'stup0', "round 3's net fine-tuned on as many SiD self-play boards"),
                           ('mf', 'stup0', "round 3's net fine-tuned on the human boards and the SiD boards together, playing as SiD"),
                           ('hs', 'usbc', "a net trained from scratch on the USBC's human boards"),
                           ('bs', 'stup0', 'a net trained from scratch on as many SiD self-play boards'),
                           # Max, 09:43 UTC: the human boards with a medium set of other boards, and with more weight
                           ('m10', 'stup0', "round 1's net tuned as a round is on about 10,000 pure-Stu boards"),
                           ('m10h', 'stup0', "round 1's net tuned as a round is on about 10,000 pure-Stu boards and the human boards"),
                           ('m10h4', 'stup0', "round 1's net tuned as a round is on about 10,000 pure-Stu boards and the human boards four times over"),
                           ('s10', 'stup0', 'a net trained from scratch on about 10,000 pure-Stu boards'),
                           ('s10h', 'stup0', 'a net trained from scratch on about 10,000 pure-Stu boards and the human boards'),
                           # every expert table of those events, not one a deal (10:26 UTC, after the first part's result)
                           ('m10F', 'stup0', "round 1's net tuned as a round is on about 10,000 pure-Stu boards and every human table with a familiar auction"),
                           ('m10A', 'stup0', "round 1's net tuned as a round is on about 10,000 pure-Stu boards and every human table, auctions as bid"),
                           ('m10B', 'stup0', "round 1's net tuned as a round is on about 10,000 pure-Stu boards and every human table, the unfamiliar auctions blanked"),
                           ('hA', 'usbc', 'a net trained from scratch on every human table'),
                           ('bA', 'stup0', 'a net trained from scratch on as many pure-Stu boards as there are human tables'),
                           ('sAh', 'stup0', 'a net trained from scratch on those pure-Stu boards and every human table')):
        path = f'{HUMAN}/{tag}.npz'
        names = {'self': own, '*': own}
        bots[f'stu{tag}-n'] = alone(f'{what}, alone: its first card at every trick, no search, no rollouts, no claims', path, names)
        bots[f'stu{tag}-n']['label'] = bots[f'stu{tag}-n']['label'].replace('Stu round 0 ladder: ', 'Human-boards experiment: ')
        b = dict(copy.deepcopy(bots['stu3-pst']), rollout_policy=path, gen7_policy=path)
        b['x8']['names'] = dict(names)
        b['label'] = f'Human-boards experiment: the one-net SiD (rollouts on the settings of stu3-pst) with {what} inside and at the table'
        bots[f'stu{tag}-pst'] = b
    # Round 4 (cut about 13:00 UTC on 14 November), one net at the table and in the rollouts, in two nets (Max, 09:39 UTC: "If
    # we aren't sure we can do a R4a and an R4b"): stu4 with every USBC human table of 2021 to 2023 in its training (the
    # experiment above: they help the net alone at every dose), stu4c the control without them. -put: blind, the gate's bot.
    for tag, path, what in (('4', R4, "round 4's net (with the USBC's human tables)"), ('4c', R4C, "round 4's control net (without the human tables)")):
        b = dict(copy.deepcopy(bots['stu3-pst']), rollout_policy=path, gen7_policy=path)
        b['label'] = (f"Stu round 4 ladder ({what} inside and at the table, its own side read as stup0): pure with the opening lead from "
                      'rollouts on the settings of every other card')
        bots[f'stu{tag}-pst'] = b
        bots[f'stu{tag}-put'] = blind(f'stu{tag}-pst', 'BLIND: told nothing about who sits against it')
        bots[f'stu{tag}-n'] = alone(f'{what} alone, told its own side is stup0: its first card at every trick, no search, no rollouts, no claims',
                                    path, dict(NAMES2))
        bots[f'stu{tag}-n']['label'] = bots[f'stu{tag}-n']['label'].replace('Stu round 0 ladder: ', 'Stu round 4 ladder: ')
    # stu4c is round 4's net (Max, 15:39 and 15:50 UTC: no clear gain from the human tables inside the bot, "I kinda like the
    # idea of being trained only on bots"; 17:34: "likely adopt"): its twins play the one-net self-play from 17:45 UTC.
    for twin, base in (('stu4-psta', 'stu4-pst'), ('stu4-pstb', 'stu4-pst'), ('stu4c-psta', 'stu4c-pst'), ('stu4c-pstb', 'stu4c-pst')):
        bots[twin] = copy.deepcopy(bots[base])                 # the one-net bot under two ids for its self-play, defenders mixing
        bots[twin]['x8']['mix'] = dict(bots[twin]['x8']['mix'], defender=True)
        bots[twin]['label'] = bots[base]['label'] + "; its defenders too play a random one of their equal cards (under a second id, for self-play records)"
    bots['stu4-putb'] = copy.deepcopy(bots['stu4-put'])
    bots['stu4-putb']['label'] = bots['stu4-put']['label'] + ' (under a second id, for blind self-play)'
    # The nets alone as the rollouts use them: every card drawn from the net's probabilities (gen7 net_sample).
    for name, base in (('stu3-nd', 'stu3-n'), ('stu0-nd', 'stu0-n')):
        b = copy.deepcopy(bots[base])
        b['gen7']['net_sample'] = True
        b['label'] = b['label'] + '; every card DRAWN from its probabilities, as a simulated seat of the rollouts'
        bots[name] = b
    # Max, 02:26 UTC on 14 November: a net from the strongest bots' data against one from the present mix, the same size
    # (exp_strong.sh). Both read every side as Gen 8 card play (8s-32), as v2 does in SiD (rollout) Stu R0.
    for tag, path, what in (('S', STRONG, "Gen 8 card play's rows only"), ('M', MIX, "as many rows in v2's mix of bots")):
        b = dict(copy.deepcopy(bots['stu0-ps']), rollout_policy=path)
        b['label'] = f'Strong-data experiment: SiD (rollout) with a net trained from scratch on {what} of v2\'s set'
        bots[f'stu{tag}-ps'] = b
        bots[f'stu{tag}-n'] = alone(f'the net trained from scratch on {what} of v2\'s set, alone', path,
                                    {'self': '8s-32', '*': '8s-32', **BEN})
    # Gen 8 card play under two ids, for its self-play as training data (Max, 02:31 and 02:43 UTC: the best data the
    # strongest bots make, and only as much of Stu's own self-play as tells where we are). Read as 8s-32 in the rows.
    for twin in ('g8a', 'g8b'):
        bots[twin] = dict(copy.deepcopy(x8['8p-32-v41']), label='Gen 8 card play (8p-32-v41) under a second id, for self-play records')
    # Personalities of Gen 8 card play (bridge_harness/style.py; Max, 03:35 to 03:50 UTC on 14 November: more variability
    # in the opponent population, mostly directed, a variety of styles, about a quarter of an IMP a board on average).
    # Each is Gen 8 card play that keeps, of the cards its search rates within `near_tie` of the best, the ones its
    # style prefers; its net then chooses among those, as Gen 8's does among exact ties. For 15% of those decisions it is one
    # of the cards within the margin at random instead.
    # The margin is the dose: g8-<style> at 0.1 tricks, g8-<style>0 at 0 (among exactly tied cards only).
    STYLES = {'greedy': dict(tempo=1.), 'patient': dict(tempo=-1.), 'active': dict(active=1.), 'passive': dict(active=-1.),
              'high': dict(high=1.), 'low': dict(high=-1.)}
    TEXT = {'greedy': 'takes its tricks now', 'patient': 'ducks and waits', 'active': 'switches and leads from honours', 'passive': 'leads safely',
            'high': 'plays high cards freely', 'low': 'keeps its high cards'}
    for name, style in STYLES.items():
        for tag, margin in (('', .1), ('0', 0.)):
            b = copy.deepcopy(x8['8p-32-v41'])
            b['near_tie'] = margin
            b['gen7'] = dict(b['gen7'], style=dict(style, random=.15))
            b['label'] = (f'Gen 8 card play with a style: {name} ({TEXT[name]}) among the cards within {margin} tricks of its best, '
                          'a random one of them 15% of the time')
            bots[f'g8-{name}{tag}'] = b
    # SiD's own randomization (Max, 03:45 UTC: "we need to randomize ourselves a bit too or our similar opponents with big
    # nets will read us on defense too much. Maybe we can spend a quarter imp"): a random one of the candidates within 0.05
    # tricks of its best, declaring and defending. By its own rollout values that gives up 0.09 tricks a board
    # (bench/mix_budget.py on l3-p; 0.21 at 0.08), which overstates the real cost.
    bots['stu3-pm'] = copy.deepcopy(bots['stu3-ps'])
    bots['stu3-pm']['x8']['mix'] = dict(bots['stu3-pm']['x8']['mix'], near=.05, defender=True)
    bots['stu3-pm']['label'] = bots['stu3-pm']['label'] + '; plays a random one of its candidates within 0.05 tricks of the best, defending too'
    # Policy v4.1, the table net, playing the simulated seats as well, in place of a rollout net (Max, 04:07 UTC on 14
    # November: "And R3 vs 4.1 running the rollouts?"): the reference bot in every other respect. v4.1 takes no bot names.
    bots['stuv41-ps'] = dict(copy.deepcopy(bots['stu0-ps']), rollout_policy=V41)
    del bots['stuv41-ps']['x8']['names']
    bots['stuv41-ps']['label'] = bots['stu0-ps']['label'].replace('Stu round 0 ladder: ', 'Policy v4.1 inside the rollouts (and at the table): ')
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
    # Variable personalities (Max, 21:14 UTC on 14 November: "Update Sid to randomize personalities"; "SidVariable can be an
    # identifier"; "update gen 8/9 to also uptake this personality capability"): a persona per table and seat
    # (bridge_harness/persona.py: play style, bidding style, partner's knowledge, disclosure; partners correlated 0.5), drawn
    # per board by scripts/gen8_match.py. Every other bot is told the identifier, never the persona (a blind 8X bot too:
    # x8 read_variable). SidVariable is the gate's R4c bot; it keeps guaranteed contracts, so it floors its own kind's.
    sid = copy.deepcopy(bots['stu4c-put'])
    sid['persona'] = {'variable': True}
    sid['x8']['claims']['opponents'] = sorted(set(sid['x8']['claims']['opponents']) | {'SidVariable'})
    sid['label'] = ('SidVariable: stu4c-put (SiD (rollout) Stu R4c) with a persona per table and seat (play style among its candidates '
                    'within 0.05 tricks; bidding style at near 6, weights +-3), read by others by this identifier only')
    bots['SidVariable'] = sid
    g8 = copy.deepcopy(x8['8p-32-v41'])
    g8['near_tie'] = 0.
    g8['persona'] = {'variable': True}
    g8['label'] = ('Gen8Variable: Gen 8 card play (8p-32-v41) with a persona per table and seat (play style among exactly tied cards; '
                   'bidding style at near 6, weights +-3), read by others by this identifier only')
    bots['Gen8Variable'] = g8
    out = ROOT / 'configs/loop-bots.json'
    out.write_text(json.dumps(bots, indent=1) + '\n')
    print(out, sorted(bots))


if __name__ == '__main__':
    main()
