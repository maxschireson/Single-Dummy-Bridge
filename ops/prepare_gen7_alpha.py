"""Freeze a Gen7 alpha cohort: a drained Gen6 run's unplayed deals, its bots unchanged, plus the Gen7 bots.

The Gen7 bots, their settings, the policy release and the match mix all come from the plan
(configs/round7-alpha.json); nothing about them is fixed here. A Gen7 bot is its Gen6 base bot
(same bidder, lead net, scorer, layout settings and sample count) with the gen7 engine, the
policy net, and the plan's `gen7` block written out in full, defaults included.

Carried over from the source run unchanged: tie-audit and fork settings, bidding conditions, room
seeding, the generation/variant labels the exporter keys on, and the facts about its corpus.

  python ops/prepare_gen7_alpha.py --source /path/to/drained/run --run /path/to/new/run [--plan configs/round7-alpha.json]
"""
import argparse
from copy import deepcopy
from dataclasses import asdict
import fcntl
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.arena_pairs import pair_members
from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import load, save
from bridge_harness.gen6 import Gen6Config
from bridge_harness.gen7 import ENGINE, resolved
from bridge_harness.loop_registry import sha, source_hash
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest
from ops.prepare_gen6 import verify_source

PLAN = ROOT / 'configs/round7-alpha.json'
GEN7_POLICY = 'artifacts/gen7/policy.npz'
RUNTIME = ('ops/gen5_runtime.py', 'ops/prepare_gen7_alpha.py')
# What the plan does not own: how tables are audited and forked, how rooms are seeded, the labels the
# exporter and report registration key on, and facts about the corpus the unplayed deals come from.
CARRIED = ('generation', 'variant', 'audit', 'ben_audit', 'bidding_conditions', 'gap_fork', 'two_self_rooms', 'independent_room_seeds',
           'independent_cohort', 'exclusion_families')


def load_plan(path=None, require_ready=True):
    plan = json.loads(Path(path or PLAN).read_text())
    if require_ready and (not plan['launch_enabled'] or plan['pending']):
        raise ValueError('Gen7 alpha plan is not ready: settle every `pending` item, empty the list and enable launch')
    entry = plan['artifacts'].get('gen7_policy') if set(plan['artifacts']) == {'gen7_policy'} else None
    if entry is None or not all(isinstance(entry.get(k), str) and entry[k] for k in ('release', 'file', 'restore', 'sha256')):
        raise ValueError('Gen7 alpha plan needs exactly one artifact, gen7_policy, with release, file, restore and sha256')
    if not plan['gen7_bots']:
        raise ValueError('Gen7 alpha plan needs at least one Gen7 bot')
    for bot in plan['gen7_bots'].values():
        resolved(bot.get('gen7'))
        Gen6Config(**bot.get('gen6', {}))
        samples = bot.get('samples', 1)
        if isinstance(samples, bool) or not isinstance(samples, int) or samples < 1:
            raise ValueError('Gen7 bot samples is a positive integer')
    if len(plan['roster']) < 2 or len(set(plan['roster'])) != len(plan['roster']):
        raise ValueError('Roster needs at least two distinct bots')
    for pair, weight in plan['pair_weights'].items():
        pair_members(pair)
        if isinstance(weight, bool) or not isinstance(weight, int) or weight < 1:
            raise ValueError('Pair weights are positive integers')
    return plan


def make_bots(old, plan):
    """Source bots unchanged, plus each Gen7 bot built from its Gen6 base bot's spec."""
    bots = deepcopy(old['bots'])
    for key, entry in plan['gen7_bots'].items():
        base = old['bots'].get(entry['base'])
        if key in bots or base is None or base.get('engine') != 'gen6':
            raise ValueError(f'Gen7 bot {key} needs a new id and a Gen6 base bot')
        spec = deepcopy(base)
        spec.pop('identity')
        spec.update(id=key, engine=ENGINE, policy_role='gen7-alpha', samples=entry.get('samples', base['samples']),
                    gen6=asdict(Gen6Config(**dict(base['gen6'], **entry.get('gen6', {})))),
                    gen7=resolved(entry.get('gen7')), gen7_policy=GEN7_POLICY)
        spec['artifact_sha256'] = dict(base['artifact_sha256'], gen7_policy=plan['artifacts']['gen7_policy']['sha256'])
        spec['identity'] = digest(spec)
        bots[key] = spec
    return bots


def check_mix(plan, bots, references):
    for name in plan['roster']:
        if name not in bots:
            raise ValueError(f'Unknown roster bot {name}')
    if plan['common_bidder'] not in bots:
        raise ValueError('Unknown common bidder')
    scheduled = set()
    for pair in plan['pair_weights']:
        candidate, opponent = pair_members(pair)
        if candidate not in bots or opponent not in bots:
            raise ValueError(f'Pair {pair} names an unknown bot')
        if references.get(candidate) not in bots:
            raise ValueError(f'{candidate} leads a pair and needs an audit reference bot')
        scheduled |= {candidate, opponent}
    idle = sorted(set(plan['gen7_bots']) - scheduled)
    if idle:
        raise ValueError(f'Gen7 bots in no pair: {idle}')


def release_file(entry, scorers):
    """The policy file of a release folder, rebuilt from its parts if needed, checked against the plan, and
    checked to have been trained on the readings of the hand-fit scorer the bots will play with."""
    folder = ROOT / entry['release']
    path = folder / entry['file']
    if not path.exists():
        subprocess.run([sys.executable, str(folder / entry['restore'])], check=True, cwd=folder, stdout=subprocess.DEVNULL)
    if sha(path) != entry['sha256']:
        raise ValueError('Gen7 policy does not match the plan: ' + entry['file'])
    trained_with = json.loads((folder / 'manifest.json').read_text()).get('scorer_sha256')
    if trained_with is None or scorers != {trained_with}:
        raise ValueError("The policy release names a different hand-fit scorer from the base bots'; its inputs would not mean what it learned")
    return path


def commit():
    try:
        return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def prepare(root, source, plan_path=None):
    root, source = Path(root).resolve(), Path(source).resolve()
    plan_path = Path(plan_path or PLAN)
    if root.exists():
        raise ValueError('Refusing to overwrite a frozen run')
    if not all((source / n).exists() for n in ('STOP', 'WATCHDOG_STOP')):
        raise ValueError('Drain the source collector and disable its recovery first')
    with (source / '.writer.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if list((source / 'failures').glob('*.json')):
            raise ValueError('Inspect preserved source failures first')
        old = json.loads((source / 'manifest.json').read_text())
        plan = load_plan(plan_path)
        verify_source(source, old)
        boards = list(load(source / old['corpus']))
        done = set()
        episodes = list((source / 'episodes').glob('*.json.gz'))
        receipts = list((source / 'receipts').glob('*.json'))
        if len(episodes) != len(receipts):
            raise ValueError('Source episodes/receipts incomplete')
        for path in receipts:
            r = json.loads(path.read_text())
            i = r['index']
            if i in done or not 0 <= i < len(boards) or r['manifest_identity'] != old['identity']:
                raise ValueError('Wrong source receipt identity')
            if r['family'] != deal_key(boards[i].hands, True) or r['episode_sha256'] != sha(source / 'episodes' / f'{i:06d}.json.gz'):
                raise ValueError('Source receipt/episode mismatch')
            done.add(i)
        keep = [i for i in range(old['target']) if i not in done]
        if not keep:
            raise ValueError('No unplayed source deals remain')
        bots = make_bots(old, plan)
        references = dict(old.get('audit_references', {}), **plan['audit_references'])
        check_mix(plan, bots, references)
        entry = plan['artifacts']['gen7_policy']
        policy = release_file(entry, {bots[k]['artifact_sha256']['scorer'] for k in plan['gen7_bots']})
        root.mkdir(parents=True)
        for folder in ('artifacts', 'assets'):
            if (source / folder).exists():
                shutil.copytree(source / folder, root / folder)
        (root / GEN7_POLICY).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(policy, root / GEN7_POLICY)
        for folder in ('episodes', 'receipts', 'failures'):
            (root / folder).mkdir()
        save([boards[i] for i in keep], root / 'corpus.jsonl')
        atomic_json(root / 'source-indices.json', keep)
        labels = dict(old.get('labels', {}), **plan.get('labels', {}))
        labels.update({key: bot.get('label', key) for key, bot in plan['gen7_bots'].items()})
        m = dict(schema=old['schema'], campaign=plan['campaign'], title=plan['title'],
            target=len(keep), seed=plan.get('seed', old['seed']), roster=plan['roster'], bots=bots,
            pair_weights=plan['pair_weights'], pair_schedule=[p for p, n in plan['pair_weights'].items() for _ in range(n)],
            audit_references=references, common_bidder=plan['common_bidder'],
            corpus='corpus.jsonl', corpus_sha256=sha(root / 'corpus.jsonl'), source_sha256=source_hash(),
            runtime_sha256={name: sha(ROOT / name) for name in RUNTIME},
            created_epoch=time.time(), source_generation=old['identity'], source_completed=len(done),
            source_indices='source-indices.json', source_indices_sha256=sha(root / 'source-indices.json'),
            labels=labels, order=plan['roster'], plan_sha256=sha(plan_path), source_commit=commit(),
            gen7_alpha=dict(bots=sorted(plan['gen7_bots']), policy_release=entry['release'], policy_sha256=entry['sha256']),
            model_note='Gen 7 alpha bots are their Gen 6 base bot (same bidder, lead net, hand-fit scorer, layouts and sample count) '
                       'with the gen7 engine (bridge_harness/gen7.py): the policy net weights the listed layouts by the play so far, '
                       'breaks ties, and from the tricks named in each bot\'s `gen7.tree` a short tree search over the net\'s likeliest '
                       'cards re-values the cards the Gen 6 search rates near its best. Settings are in each bot\'s `gen7` block. '
                       'Every other bot is unchanged from the source run. docs/gen7_alpha_2026-11-11.md has the details.',
            interpretation='Alpha cohort to validate the Gen 7 architecture and measure its speed; not a strength claim. '
                           'Common and native auctions are separate conditions; identical auctions reuse physical games. '
                           'Only unplayed source deals are allocated; completed source records are unchanged.')
        for key in CARRIED:
            if key in old:
                m[key] = deepcopy(old[key])
        m['identity'] = digest(m)
        atomic_json(root / 'manifest.json', m)
        atomic_json(root / 'state.json', dict(manifest_identity=m['identity'], completed=0, target=len(keep), by_pair={}, root_games=0, tables=0, epoch=time.time()))
        atomic_json(root / 'heartbeat.json', dict(epoch=time.time(), completed=0, workers=4, ben_workers=1, in_flight=[]))
        verify_generation(root, m)
        return m


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--plan', type=Path)
    a = p.parse_args()
    m = prepare(a.run, a.source, a.plan)
    print(json.dumps(dict(identity=m['identity'], target=m['target'], allocation=m['pair_weights'], policy=m['gen7_alpha'],
                          gen7={k: v['gen7'] for k, v in m['bots'].items() if v.get('engine') == ENGINE})))
