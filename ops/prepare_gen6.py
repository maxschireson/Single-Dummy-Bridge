"""Freeze a Gen6 cohort: the source run's unplayed deals, its bots unchanged, plus the Gen6 bots.

The match mix comes from the plan (configs/round6.json); nothing about it is fixed here.
The source run is checked by its manifest, bot identities, artifacts and corpus. Its pinned
source-code hash is not compared, because the Gen6 engine is new code under bridge_harness/.

  python ops/prepare_gen6.py --source /path/to/drained/run --run /path/to/new/run [--plan configs/round6.json]
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
from bridge_harness.gen6 import ENGINE, Gen6Config
from bridge_harness.loop_registry import sha, source_hash
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest

GEN6_FILES = dict(bidding='artifacts/gen6/bidder.keras', lead_belief='artifacts/gen6/lead_belief.npz', scorer='artifacts/gen6/scorer.npz')


def load_plan(path=None, require_ready=True):
    plan = json.loads(Path(path or ROOT / 'configs/round6.json').read_text())
    if require_ready and (not plan['launch_enabled'] or plan['pending']):
        raise ValueError('Gen6 plan is not ready: set the match mix, empty `pending` and enable launch')
    if set(plan['artifacts']) != set(GEN6_FILES) or not plan['gen6_bots']:
        raise ValueError('Gen6 plan needs the bidder, lead net and scorer, and at least one Gen6 bot')
    for entry in plan['gen6_bots'].values():
        Gen6Config(**entry.get('gen6', {}))
    if len(plan['roster']) < 2 or len(set(plan['roster'])) != len(plan['roster']):
        raise ValueError('Roster needs at least two distinct bots')
    for pair, weight in plan['pair_weights'].items():
        pair_members(pair)
        if isinstance(weight, bool) or not isinstance(weight, int) or weight < 1:
            raise ValueError('Pair weights are positive integers')
    gap_fork_block(plan)
    return plan


def gap_fork_block(plan):
    """The plan's optional `gap_fork` settings, checked, as they go into the manifest (None = no gap forks).

    {"per_band": 2, "bands": [0.125, 0.5], "max_cpu_share": 1.5}; see bridge_harness.fork_audit.GapForks
    and docs/gen7_data_capture_2026-11-11.md.
    """
    value = plan.get('gap_fork')
    if not value:
        return None
    from bridge_harness.fork_audit import GapForks
    if set(value) - {'per_band', 'bands', 'max_cpu_share'}:
        raise ValueError('Unknown gap_fork setting')
    checked = GapForks(**value)
    return dict(per_band=checked.per_band, bands=list(checked.bands), max_cpu_share=checked.max_cpu_share)


def make_bots(old, plan):
    """Source bots unchanged, plus each Gen6 bot built from its base bot's spec."""
    bots = deepcopy(old['bots'])
    for key, entry in plan['gen6_bots'].items():
        base = old['bots'].get(entry['base'])
        if key in bots or base is None or base.get('engine'):
            raise ValueError(f'Gen6 bot {key} needs a new id and an ordinary base bot')
        if base['artifact_sha256']['bidding'] != plan['lead_state_bidder_sha256']:
            raise ValueError('The base bot must bid with the Gen5 bidder that the lead net takes its features from')
        spec = deepcopy(base)
        spec.pop('identity')
        spec.update(id=key, engine=ENGINE, near_tie=0., policy_role='pimc-ties-only', samples=entry.get('samples', base['samples']),
                    lead_state_bidder=base['bidding'], gen6=asdict(Gen6Config(**entry.get('gen6', {}))), **GEN6_FILES)
        spec['artifact_sha256'] = dict(base['artifact_sha256'], lead_state_bidder=plan['lead_state_bidder_sha256'],
                                       **{k: plan['artifacts'][k]['sha256'] for k in GEN6_FILES})
        spec['identity'] = digest(spec)
        bots[key] = spec
    return bots


def check_mix(plan, bots, references):
    for name in plan['roster']:
        if name not in bots:
            raise ValueError(f'Unknown roster bot {name}')
    if plan['common_bidder'] not in bots:
        raise ValueError('Unknown common bidder')
    for pair in plan['pair_weights']:
        candidate, opponent = pair_members(pair)
        if candidate not in bots or opponent not in bots or candidate == opponent:
            raise ValueError(f'Pair {pair} needs two different known bots')
        if references.get(candidate) not in bots:
            raise ValueError(f'{candidate} leads a pair and needs an audit reference bot')


def verify_source(source, old):
    if digest({k: v for k, v in old.items() if k != 'identity'}) != old['identity']:
        raise ValueError('Source manifest changed')
    for spec in old['bots'].values():
        if digest({k: v for k, v in spec.items() if k != 'identity'}) != spec['identity']:
            raise ValueError('Source bot identity changed')
        for key, expected in spec['artifact_sha256'].items():
            if sha(source / spec[key]) != expected:
                raise ValueError('Source artifact changed')
    if sha(source / old['corpus']) != old['corpus_sha256']:
        raise ValueError('Source corpus changed')


def release_file(entry):
    """The model file of a release folder, rebuilt from its parts if needed and checked."""
    folder = ROOT / entry['release']
    path = folder / entry['file']
    if not path.exists():
        subprocess.run([sys.executable, str(folder / entry['restore'])], check=True, cwd=folder, stdout=subprocess.DEVNULL)
    if sha(path) != entry['sha256']:
        raise ValueError('Gen6 artifact does not match the plan: ' + entry['file'])
    return path


def prepare(root, source, plan_path=None):
    root, source = Path(root).resolve(), Path(source).resolve()
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
        files = {key: release_file(plan['artifacts'][key]) for key in GEN6_FILES}
        root.mkdir(parents=True)
        for folder in ('artifacts', 'assets'):
            if (source / folder).exists():
                shutil.copytree(source / folder, root / folder)
        for key, target in GEN6_FILES.items():
            (root / target).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(files[key], root / target)
        for folder in ('episodes', 'receipts', 'failures'):
            (root / folder).mkdir()
        save([boards[i] for i in keep], root / 'corpus.jsonl')
        atomic_json(root / 'source-indices.json', keep)
        labels = dict(old.get('labels', {}), **plan.get('labels', {}))
        labels.update({key: entry.get('label', key) for key, entry in plan['gen6_bots'].items()})
        m = dict(schema='gen5-arena-manifest-v1', generation=6, variant='6', campaign=plan['campaign'], title=plan['title'],
            target=len(keep), seed=plan['seed'], roster=plan['roster'], bots=bots,
            pair_weights=plan['pair_weights'], pair_schedule=[p for p, n in plan['pair_weights'].items() for _ in range(n)],
            audit_references=references, common_bidder=plan['common_bidder'],
            corpus='corpus.jsonl', corpus_sha256=sha(root / 'corpus.jsonl'), source_sha256=source_hash(),
            runtime_sha256={name: sha(ROOT / name) for name in ('ops/gen5_runtime.py', 'ops/prepare_gen6.py')},
            audit=old['audit'], ben_audit=old['ben_audit'], bidding_conditions=old['bidding_conditions'],
            created_epoch=time.time(), source_generation=old['identity'], source_completed=len(done),
            source_indices='source-indices.json', source_indices_sha256=sha(root / 'source-indices.json'),
            labels=labels, order=plan['roster'], plan_sha256=sha(Path(plan_path or ROOT / 'configs/round6.json')),
            engine_commit=plan.get('authorized_engine_commit'),
            model_note='Gen6 bots use the gen6 play engine (bridge_harness/gen6.py): lead belief net at the opening lead, '
                       'hand-fit scorer on hand-type classes until the deal list starts, the scorer-weighted deal list after that, '
                       'and the policy net only among cards within near_tie of the best. Their bidder is the Gen 6 candidate. '
                       'Every other bot is unchanged from the source run. docs/gen6_architecture_2026-11-11.md has the details.',
            interpretation='Common and native auctions are separate conditions; identical auctions reuse physical games. '
                           'Only unplayed source deals are allocated; completed source records are unchanged.')
        if gap_fork_block(plan):
            m['gap_fork'] = gap_fork_block(plan)
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
    print(json.dumps(dict(identity=m['identity'], target=m['target'], allocation=m['pair_weights'],
                          gen6={k: v['gen6'] for k, v in m['bots'].items() if v.get('engine') == ENGINE})))
