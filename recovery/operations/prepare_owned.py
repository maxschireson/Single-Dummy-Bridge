"""Prepare this owned Gen8 successor with the stock authorized preparer."""
import argparse
import json
from pathlib import Path
import shutil
import sys

BASE = Path(__file__).resolve().parent
RUNTIME = BASE / 'runtime'
SOURCE = Path('/workspace/work/gen71-compare-codex-20261112/run')
RUN = BASE / 'run'
PLAN = RUNTIME / 'configs/round8-candidate.json'
sys.path.insert(0, str(RUNTIME))
from bridge_harness.loop_registry import sha
from bridge_harness.training import digest
from ops import prepare_gen7_alpha as prep


def main(exclusions):
    assert not RUN.exists()
    assert sha(exclusions) == '0b8ac2b7f41b91915f518c42f76701728097b4151acb5d0e964051c261eca0e2'
    old = json.loads((SOURCE / 'manifest.json').read_text())
    inventory = []
    for path in sorted((SOURCE / 'receipts').glob('*.json')):
        row = json.loads(path.read_text())
        inventory.append(dict(index=row['index'], receipt_sha256=sha(path), episode_sha256=row['episode_sha256']))
    assert len(inventory) == 1974
    original = prep.atomic_json

    def write(path, data):
        if Path(path) == RUN / 'manifest.json':
            assert data['source_completed'] == 1974
            assert data['target'] == 20257 - 1974
            assert data['bots']['71s-32'] == old['bots']['71s-32']
            assert data['bots']['8s-32']['identity'].startswith('269fdf1854f4')
            assert data['bots']['8c-32']['identity'].startswith('f60c9782f5c8')
            assert data['gen8']['rule_bidders']['8c-32'] == 'f50e95de93ac0dbeef213be965d966c75693932b1f039128d46b752321e6164c'
            assert data['evaluation_exclusions']['families'] == 34092
            assert data['evaluation_exclusions']['sha256'] == sha(exclusions)
            for name in ('source-indices.json', 'manifest.json'):
                shutil.copy2(SOURCE / name, RUN / ('ancestor-source-indices.json' if name == 'source-indices.json' else 'source-manifest.json'))
            shutil.copy2(PLAN, RUN / 'plan.json')
            original(RUN / 'source-completed-inventory.json', inventory)
            data.update(effective_generation=8, title='Gen8 candidate · Codex main arena mix',
                worker_lifecycle=dict(normal_workers=3, ben_workers=0, retry_failures=False),
                preparation_sha256=sha(Path(__file__)), source_manifest_sha256=sha(RUN / 'source-manifest.json'),
                source_completed_inventory_sha256=sha(RUN / 'source-completed-inventory.json'),
                ancestor_source_indices_sha256=sha(RUN / 'ancestor-source-indices.json'),
                collection_control=dict(gen71_comparison_gate_enabled=False, selfplay_launch_enabled=False,
                    stop_on_source_budget=True, stop_on_failure=True),
                lineage_note='Only unplayed families from this independent producer. All1974Gen7.1and every earlier cohort remain preserved and permanently retired. '
                    'Authorized Gen8 main mix at792c4cb; full34092-family union excluded; no shared capsule shard; no BEN server.')
            data['identity'] = digest({k: v for k, v in data.items() if k != 'identity'})
        return original(path, data)

    prep.atomic_json = write
    m = prep.prepare(RUN, SOURCE, PLAN, exclude_families=exclusions)
    print(json.dumps(dict(manifest=m['identity'], target=m['target'], source_completed=m['source_completed'],
        pairs=m['pair_weights'], actors={k: m['bots'][k]['identity'] for k in m['roster']},
        source_commit=m['source_commit'], systems=m['systems'], exclusions=m['evaluation_exclusions'])), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--exclude-families', type=Path, required=True)
    main(parser.parse_args().exclude_families)
