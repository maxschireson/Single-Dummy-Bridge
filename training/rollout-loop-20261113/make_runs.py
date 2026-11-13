#!/usr/bin/env python3
"""Writes runs.json, the list of the loop's runs for whoever reads its outputs (the dashboard), from the job files.

  python training/rollout-loop-20261113/make_runs.py

A run listed twice in a job file (a first pass, then more deals in the same folder) is one run here: `deals` is the
larger figure and `passes` lists both. A run's state is not here: read it from the box's transfer branch (rows in <run>/results.jsonl against `deals`, and
runs.log). This file says what each run is: its role, round, pair, deals, and for a Stu-family bot the net inside and
the rung of the ladder. DASHBOARD.md explains the roles and what to compute from the rows.
"""
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
BRANCHES = {'azure3': 'transfer/rollout-loop-azure3-20261113', 'azure5': 'transfer/rollout-loop-azure5-20261113',
            'sandbox': 'transfer/rollout-loop-sandbox-20261113', 'azure6': 'transfer/rollout-loop-azure6-20261113',
            'azure1': 'transfer/rollout-loop-azure1-20261113', 'azure2': 'transfer/rollout-loop-azure2-20261113'}
ROLES = (('s', 'collection'), ('r0', 'collection'), ('l', 'ladder'), ('g', 'gate'), ('d', 'data'), ('c-', 'control'), ('h', 'head-to-head'),
         ('pf-', 'preflight'))
RUNG = {'': 'stu', 'a': 'stu', 'b': 'stu', '-b50': 'b50', '-r6': 'r6', '-r3': 'r3', '-p': 'pure', '-pa': 'pure', '-pb': 'pure', '-pl': 'pure-sl',
        '-pr': 'pure-rl', '-pra': 'pure-rl', '-prb': 'pure-rl', '-ps': 'pure-rs', '-psa': 'pure-rs', '-psb': 'pure-rs', '-pt': 'pure-t', '-pv': 'pure-v', '-n': 'net', '-ns': 'net-s'}
RUNG_TEXT = {'stu': "Stu's own stages: search at the lead and tricks 1 to 2, blend at trust 0.25 at tricks 3 to 6, rollouts alone from trick 7",
             'b50': 'the blend at tricks 3 to 6 at trust 0.5', 'r6': 'rollouts alone from trick 6', 'r3': 'rollouts alone from trick 3',
             'pure': "the net's opening lead, rollouts alone from the second card on; no double dummy",
             'pure-sl': 'pure with a searched opening lead: the search decides the lead, rollouts alone from the second card on',
             'pure-rl': ('pure with the opening lead from rollouts: every distinct lead on 512 layouts of the three hidden hands, none '
                         'dropped; rollouts alone from the second card on'),
             'pure-rs': ("pure with the opening lead from rollouts on the settings of every other card (at most 4 candidates by the net's "
                         'prior, 32 then up to 128 layouts with the race); rollouts alone from the second card on'),
             'net-s': "the net alone, a longer-trained variant of the round's net (the epoch best on pure Stu's held-out cards within a limit on forgetting)",
             'pure-t': "pure, with the rollout net at the table as well (its lead, first choices and reading of the play) in place of policy v4.1",
             'pure-v': "pure, the rollouts' simulated seats playing by the net's value head (seat blend) in place of a draw from its probabilities",
             'net': "the net alone: its first card at every trick; no search, no rollouts, no claims, no mixing"}
# Round 0's collection is not waited on any more (PLAN.md): round 1 is cut when its training chain is ready.
ROUNDS = {'0': dict(collection_cut_boards=None, note="No board count is waited for. Round 1's set was cut at 10:29 UTC on 13 November "
                                                       '(1,009 boards of Stu-as-is). Since 12:37 UTC the collection is pure Stu playing '
                                                       'itself, one table a board: sp0 (the net\'s own lead) and spr0 (the lead rolled '
                                                       "out), side by side on azure5 since 14:29 UTC. A collection run's first_bot.rung "
                                                       'says which bot plays it, and tables_a_board 1 that its rows carry no IMPs.')}
# runs that are not in a job file any more
STATIC = [
    dict(name='r0', box='azure5', pair='z0a-v2~z0b-v2', seed=9001, first=0, deals=20000, records=True,
         note='Stopped by hand at 248 boards (09:08 UTC, 13 Nov) when the bot was renamed: the same bot as stu0a~stu0b, records without per-layout results.'),
    dict(name='s0', box='azure5', pair='stu0a~stu0b', seed=9001, first=1000, deals=19000, records=True,
         note=('Stu-as-is against itself. Paused at 976 boards (11:31 UTC, 13 Nov) when the collection moved to pure Stu; it and r0 are '
               "round 1's training set. Both rooms of a board are the same play card for card in 95% of boards (same seed by ply and "
               'seat), so a board holds one distinct table.')),
    dict(name='g0-v2', box='azure3', pair='z0a-v2~8p-32-v41', seed=131, first=0, deals=2000, records=False,
         note='Stopped by hand at 163 boards when the bot was renamed. Superseded by l0-stu0 and g0b-stu0.'),
    dict(name='g0-stu0', box='azure3', pair='stu0a~8p-32-v41', seed=131, first=0, deals=2000, records=False,
         note='Stopped by hand at 58 boards when azure3 was put on the collection first. Superseded by l0-stu0 and g0b-stu0.'),
]


def bot(name):
    """What a bot id says: Stu-family ids are stu<round>[v1][a|b|-rung]; z0a-v2 and z0b-v2 were round 0's first ids."""
    if name in ('z0a-v2', 'z0b-v2'):
        return dict(family='stu', round=0, net='v2', rung='stu')
    m = re.fullmatch(r'stu(\d+)(v1)?(a|b|-b50|-r6|-r3|-pra|-prb|-pr|-psa|-psb|-ps|-pa|-pb|-pl|-pt|-pv|-p|-ns|-n)?', name)
    if m:
        return dict(family='stu', round=int(m.group(1)), net='v1' if m.group(2) else ('v2' if m.group(1) == '0' else f'stu{m.group(1)}'),
                    rung=RUNG[m.group(3) or ''])
    return dict(family='other')


def role(name):
    for prefix, r in ROLES:
        if name.startswith(prefix):
            return r
    return 'other'


def run(name, box, pair, seed, first, deals, records, note=''):
    a, b = pair.split('~')
    out = dict(name=name, box=box, branch=BRANCHES[box], role=role(name), pair=pair, seed=int(seed), first=int(first), deals=int(deals),
               records=bool(records), first_bot=bot(a), second_bot=bot(b))
    if note:
        out['note'] = note
    return out


def main():
    runs = [run(**r) for r in STATIC]
    for box, jobs in (('azure5', 'jobs-azure5.txt'), ('azure5', 'jobs-azure5b.txt'), ('azure3', 'jobs-azure3.txt'), ('azure3', 'jobs-azure3b.txt'),
                      ('azure6', 'jobs-azure6.txt'), ('azure6', 'jobs-azure6b.txt'), ('azure5', 'jobs-azure5-r2.txt'),
                      ('azure6', 'jobs-azure6-r0c.txt'), ('azure6', 'jobs-azure6-r2.txt'), ('azure6', 'jobs-azure6-r2s.txt'),
                      ('azure2', 'jobs-azure2.txt'), ('azure2', 'jobs-azure2b.txt'), ('azure1', 'jobs-azure1.txt'), ('azure1', 'jobs-azure1b.txt'),
                      ('azure5', 'jobs-azure5-r3a.txt'), ('azure5', 'jobs-azure5-r3.txt'), ('azure1', 'jobs-azure1-r3.txt')):
        for line in (HERE / jobs).read_text().splitlines():
            stopped = line.startswith('#stopped ')
            if stopped:                             # a run taken out of the chain: listed and marked, not run
                line = line[len('#stopped '):]
            if not line.strip() or line.startswith('#'):
                continue
            name, pair, seed, first, deals, _workers, *options = line.split()
            again = next((r for r in runs if r['name'] == name and r['box'] == box), None)
            if again is not None:                   # a name that comes twice goes on in the same folder: the later line's deals
                again['passes'] = again.get('passes', [again['deals']]) + [int(deals)]
                again['deals'] = max(again['deals'], int(deals))
                continue
            runs.append(run(name, box, pair, seed, first, deals, '--episodes' in options))
            if '--one-room' in options:             # one table a board, no IMPs (a collection run between two ids of one bot)
                runs[-1]['tables_a_board'] = 1
            if stopped:
                runs[-1]['stopped'] = "at round 3's cut, 23:00 UTC on 13 November, for pure rollout (the lead rolled out as every other card)"
    for line in (HERE / 'jobs-azure3-later.txt').read_text().splitlines():      # taken out of the queue: listed, marked, not run
        if not line.strip() or line.startswith('#'):
            continue
        name, pair, seed, first, deals, _workers, *options = line.split()
        again = next((r for r in runs if r['name'] == name and r['box'] == 'azure3'), None)
        if again is not None:                       # a later pass of a run that has boards: the pass is what is shelved
            again['shelved_passes'] = again.get('shelved_passes', []) + [int(deals)]
            continue
        runs.append(run(name, 'azure3', pair, seed, first, deals, '--episodes' in options))
        runs[-1]['shelved'] = True
    for line in [x for f in ('jobs-azure3-ben.txt', 'jobs-azure3-ben3.txt') for x in (HERE / f).read_text().splitlines()]:    # against BEN: a shard a lane, folders NAME-1..NAME-<lanes>
        if not line.strip() or line.startswith('#'):
            continue
        name, pair, seed, first, deals, lanes, *options = line.split()
        runs.append(run(name, 'azure3', pair, seed, first, deals, '--episodes' in options))
        runs[-1].update(role='ben', shards=int(lanes), folders=[f'{name}-{n}' for n in range(1, int(lanes) + 1)])
    for r in runs:
        r.setdefault('queue_order', None)
    order = {}
    for r in runs:
        if r['name'] not in {s['name'] for s in STATIC} and r['role'] != 'ben' and not r.get('shelved') and not r.get('stopped'):
            order[r['box']] = order.get(r['box'], 0) + 1
            r['queue_order'] = order[r['box']]
    out = dict(what="The rollout loop's runs (Stu). Generated by make_runs.py from the job files; see DASHBOARD.md.",
               source_branch='research/rollout-loop-20261113', branches=BRANCHES, gate_seed=131, training_seeds=[9001],
               rungs=RUNG_TEXT, rounds=ROUNDS, runs=runs)
    (HERE / 'runs.json').write_text(json.dumps(out, indent=1) + '\n')
    print(len(runs), 'runs:', ', '.join(f"{r['name']}({r['role']})" for r in runs))


if __name__ == '__main__':
    main()
