"""Freeze this producer's unused Gen7 phase1 deals under the authorized self-play mix."""
from copy import deepcopy
import fcntl
import json
from pathlib import Path
import shutil
import sys
import time

BASE = Path(__file__).resolve().parent
RUNTIME = BASE / 'runtime'
SOURCE = Path('/workspace/work/gen7-selfplay-codex-20261112/run')
RUN = BASE / 'run'
sys.path.insert(0, str(RUNTIME))
from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import load, save
from bridge_harness.loop_registry import sha, source_hash
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest
from ops.prepare_gen6 import verify_source
from ops.prepare_gen7_alpha import load_plan, make_bots, check_mix, release_file, GEN7_POLICY, RUNTIME as PINNED_RUNTIME


def prepare():
    assert not RUN.exists(), 'Never overwrite an immutable run'
    assert all((SOURCE / n).exists() for n in ['STOP', 'WATCHDOG_STOP'])
    with (SOURCE / '.writer.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not list((SOURCE / 'failures').glob('*.json'))
        old = json.loads((SOURCE / 'manifest.json').read_text())
        verify_source(SOURCE, old)
        boards = load(SOURCE / old['corpus'])
        done = set(); inventory = []
        receipts = sorted((SOURCE / 'receipts').glob('*.json'))
        assert len(receipts) == len(list((SOURCE / 'episodes').glob('*.json.gz')))
        for p in receipts:
            row = json.loads(p.read_text()); i = row['index']
            assert i not in done and row['manifest_identity'] == old['identity']
            assert row['family'] == deal_key(boards[i].hands, True)
            assert row['episode_sha256'] == sha(SOURCE / 'episodes' / f'{i:06d}.json.gz')
            done.add(i); inventory.append(dict(index=i, receipt_sha256=sha(p), episode_sha256=row['episode_sha256']))
        keep = [i for i in range(old['target']) if i not in done]
        plan_path = RUNTIME / 'configs/round7-phase1-selfplay.json'
        plan = load_plan(plan_path)
        # Rebuild the existing Gen7 actor from its base only in memory, then require exact identity.
        catalog = deepcopy(old); catalog['bots'].pop('7s-32')
        bots = make_bots(catalog, plan)
        assert bots['7s-32'] == old['bots']['7s-32']
        references = dict(old['audit_references'], **plan['audit_references'])
        check_mix(plan, bots, references)
        policy = release_file(plan['artifacts']['gen7_policy'], {bots['7s-32']['artifact_sha256']['scorer']})
        RUN.mkdir()
        for folder in ['episodes', 'receipts', 'failures']:
            (RUN / folder).mkdir()
        for folder in ['artifacts', 'assets']:
            if (SOURCE / folder).exists():
                shutil.copytree(SOURCE / folder, RUN / folder)
        shutil.copy2(policy, RUN / GEN7_POLICY)
        save([boards[i] for i in keep], RUN / 'corpus.jsonl')
        atomic_json(RUN / 'source-indices.json', keep)
        atomic_json(RUN / 'source-completed-inventory.json', inventory)
        atomic_json(RUN / 'plan.json', plan)
        shutil.copy2(SOURCE / 'manifest.json', RUN / 'source-manifest.json')
        shutil.copy2(SOURCE / 'source-indices.json', RUN / 'ancestor-source-indices.json')
        m = dict(schema=old['schema'], generation=old['generation'], variant=old['variant'],
            effective_generation=7, campaign=plan['campaign'], title='Gen 7 · Codex standard self-play and Gen6 comparison',
            target=len(keep), seed=old['seed'], roster=plan['roster'], order=plan['roster'], bots=bots,
            pair_weights=plan['pair_weights'], pair_schedule=[p for p,n in plan['pair_weights'].items() for _ in range(n)],
            audit_references=references, common_bidder=plan['common_bidder'],
            audit=old['audit'], ben_audit=old['ben_audit'], gap_fork=old['gap_fork'],
            bidding_conditions=['self', 'common', 'native'], two_self_rooms=False,
            independent_cohort=True, exclusion_families=old['exclusion_families'],
            corpus='corpus.jsonl', corpus_sha256=sha(RUN / 'corpus.jsonl'), source_sha256=source_hash(),
            runtime_sha256={p:sha(RUNTIME / p) for p in PINNED_RUNTIME}, created_epoch=time.time(),
            source_generation=old['identity'], source_completed=len(done),
            source_indices='source-indices.json', source_indices_sha256=sha(RUN / 'source-indices.json'),
            source_completed_inventory_sha256=sha(RUN / 'source-completed-inventory.json'),
            ancestor_source_indices_sha256=sha(RUN / 'ancestor-source-indices.json'),
            source_commit='317cea385dad6bdceda266ec0b750dc48c98340f',
            plan_sha256=sha(plan_path), preparation_sha256=sha(Path(__file__)),
            labels=old['labels'], model_note=plan['model_note'], interpretation=plan['interpretation'],
            gen7_alpha=old['gen7_alpha'], worker_lifecycle=dict(normal_workers=3, ben_workers=0, retry_failures=False),
            phase1=dict(per_pair_target=2000, pooled_across_collectors=True, owned_pairs=['7s-32~6-32'],
                        retired_anchor_pairs=['7s-32~5RZ32','7s-32~1'], phase2_authorized=False,
                        selfplay_authority='Max04:09, 2026-11-12;round7-phase1-selfplay.json',
                        next_action='At the comparison target, drain and prepare a new self-play-only cohort.'),
            lineage_note='Only unused families of this independent producer; no shared shard. '
                         'Parent records without gap capture,564 earlier Gen7 phase1 deals, and3710 Gen6 deals remain frozen; capture is restored only in this new identity.')
        m['identity'] = digest(m)
        atomic_json(RUN / 'manifest.json', m)
        atomic_json(RUN / 'state.json', dict(manifest_identity=m['identity'], completed=0, target=m['target'],
                    by_pair={}, root_games=0, tables=0, failures=0, epoch=time.time()))
        atomic_json(RUN / 'heartbeat.json', dict(epoch=time.time(), completed=0, workers=3, ben_workers=0, in_flight=[]))
        verify_generation(RUN, m)
        print(json.dumps(dict(manifest=m['identity'], remaining=len(keep), preserved=len(done), actor=bots['7s-32']['identity'], pairs=m['pair_weights'])))


if __name__ == '__main__':
    prepare()
