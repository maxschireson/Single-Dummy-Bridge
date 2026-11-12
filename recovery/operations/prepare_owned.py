"""Prepare Gen7 from this producer's unused deals and verified historical actors."""
from copy import deepcopy
import fcntl
import json
from pathlib import Path
import shutil
import sys
import time

BASE = Path(__file__).resolve().parent
RUNTIME = BASE / 'runtime'
SOURCE = Path('/workspace/work/gen6-fast-selfplay-stream/run')
CATALOG = Path('/workspace/work/arena-artifact-snapshot/recovery')
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
    assert not RUN.exists(), 'Do not overwrite an immutable cohort'
    assert all((SOURCE / n).exists() for n in ('STOP', 'WATCHDOG_STOP'))
    with (SOURCE / '.writer.lock').open('a+') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not list((SOURCE / 'failures').glob('*.json'))
        old = json.loads((SOURCE / 'manifest.json').read_text())
        verify_source(SOURCE, old)
        catalog = json.loads((CATALOG / 'manifest.json').read_text())
        assert digest({k:v for k,v in catalog.items() if k != 'identity'}) == catalog['identity']
        boards = load(SOURCE / old['corpus'])
        done = set()
        receipts = sorted((SOURCE / 'receipts').glob('*.json'))
        assert len(receipts) == len(list((SOURCE / 'episodes').glob('*.json.gz')))
        source_receipts = []
        for path in receipts:
            row = json.loads(path.read_text()); i = row['index']
            assert i not in done and row['manifest_identity'] == old['identity']
            assert row['family'] == deal_key(boards[i].hands, True)
            assert row['episode_sha256'] == sha(SOURCE / 'episodes' / f'{i:06d}.json.gz')
            source_receipts.append(dict(index=i, receipt_sha256=sha(path), episode_sha256=row['episode_sha256']))
            done.add(i)
        keep = [i for i in range(old['target']) if i not in done]
        assert keep and len(keep) + len(done) == old['target']
        plan_path = RUNTIME / 'configs/round7-candidate-phase1-nonben.json'
        plan = load_plan(plan_path)
        # Add named historical opponents to an in-memory actor catalog only.
        # The old manifest and its completed records remain byte-for-byte untouched.
        source_catalog = dict(old, bots=deepcopy(old['bots']))
        origins = {key: SOURCE for key in old['bots']}
        for key in ('5RZ32', '1'):
            spec = deepcopy(catalog['bots'][key])
            assert digest({k:v for k,v in spec.items() if k != 'identity'}) == spec['identity']
            for role, checksum in spec['artifact_sha256'].items():
                assert sha(CATALOG / spec[role]) == checksum
            source_catalog['bots'][key] = spec
            origins[key] = CATALOG
        bots = make_bots(source_catalog, plan)
        refs = {'7s-32': '3'}
        check_mix(plan, bots, refs)
        policy = release_file(plan['artifacts']['gen7_policy'], {bots['7s-32']['artifact_sha256']['scorer']})
        assert bots['7s-32']['gen7']['tree'][0]['trust'] == .3
        RUN.mkdir()
        for name in ('episodes', 'receipts', 'failures'):
            (RUN / name).mkdir()
        for key, spec in source_catalog['bots'].items():
            for role in spec['artifact_sha256']:
                dest = RUN / spec[role]
                if not dest.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(origins[key] / spec[role], dest)
        (RUN / GEN7_POLICY).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(policy, RUN / GEN7_POLICY)
        save([boards[i] for i in keep], RUN / 'corpus.jsonl')
        atomic_json(RUN / 'source-indices.json', keep)
        atomic_json(RUN / 'source-completed-inventory.json', source_receipts)
        atomic_json(RUN / 'plan.json', plan)
        labels = {k: old['labels'].get(k, catalog['labels'].get(k, k)) for k in bots}
        labels['7s-32'] = plan['gen7_bots']['7s-32']['label']
        m = dict(schema=old['schema'], generation=old['generation'], variant=old['variant'],
            effective_generation=7, campaign=plan['campaign'], title='Gen 7 phase 1 · Codex non-BEN collector',
            target=len(keep), seed=old['seed'], roster=plan['roster'], order=plan['roster'], bots=bots,
            pair_weights=plan['pair_weights'], pair_schedule=list(plan['pair_weights']),
            audit_references=refs, common_bidder=plan['common_bidder'],
            audit=old['audit'], ben_audit=old['ben_audit'], gap_fork=old['gap_fork'],
            bidding_conditions=['common','native'], two_self_rooms=False,
            independent_cohort=True, exclusion_families=old['exclusion_families'],
            corpus='corpus.jsonl', corpus_sha256=sha(RUN / 'corpus.jsonl'),
            source_sha256=source_hash(), runtime_sha256={p:sha(RUNTIME / p) for p in PINNED_RUNTIME},
            created_epoch=time.time(), source_generation=old['identity'], source_completed=len(done),
            source_indices='source-indices.json', source_indices_sha256=sha(RUN / 'source-indices.json'),
            source_completed_inventory='source-completed-inventory.json',
            source_completed_inventory_sha256=sha(RUN / 'source-completed-inventory.json'),
            source_commit='fe382f9b91c3c91ea0950281be5d8bf8e25e82ac',
            plan_sha256=sha(plan_path), preparation_sha256=sha(Path(__file__)),
            labels=labels, model_note=plan['model_note'], interpretation=plan['interpretation'],
            actor_catalog=dict(manifest=catalog['identity'], publication='13e0fc7b884ecfa546f693a9bac0d92b520f1247', actors=['5RZ32','1']),
            gen7_alpha=dict(bots=['7s-32'], policy_release=plan['artifacts']['gen7_policy']['release'],
                            policy_sha256=plan['artifacts']['gen7_policy']['sha256']),
            worker_lifecycle=dict(normal_workers=3, ben_workers=0, retry_failures=False),
            phase1=dict(per_pair_target=2000, pooled_across_collectors=True,
                        owned_pairs=list(plan['pair_weights']), phase2_authorized=False),
            lineage_note='All unused families from this independent producer only; no shared source shard needed (1/1). '
                         'Historical opponents added from verified actor artifacts; original source manifest and records unchanged.')
        m['identity'] = digest(m)
        atomic_json(RUN / 'manifest.json', m)
        atomic_json(RUN / 'state.json', dict(manifest_identity=m['identity'], completed=0, target=len(keep),
            by_pair={}, root_games=0, tables=0, failures=0, epoch=time.time()))
        atomic_json(RUN / 'heartbeat.json', dict(epoch=time.time(), completed=0, workers=3, ben_workers=0, in_flight=[]))
        shutil.copy2(SOURCE / 'manifest.json', RUN / 'source-manifest.json')
        shutil.copy2(CATALOG / 'manifest.json', RUN / 'actor-source-manifest.json')
        verify_generation(RUN, m)
        assert sha(SOURCE / 'manifest.json') == sha(RUN / 'source-manifest.json')
        print(json.dumps(dict(manifest=m['identity'], source_completed=len(done), remaining_families=len(keep),
            pairs=m['pair_weights'], actor=m['bots']['7s-32']['identity'], gen7=m['bots']['7s-32']['gen7'])))
        return m


if __name__ == '__main__':
    prepare()
