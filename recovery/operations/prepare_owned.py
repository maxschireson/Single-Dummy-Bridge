"""Use the stock Gen7.1 preparer, adding this producer's recovery/ownership metadata before its first manifest write."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

BASE = Path(__file__).resolve().parent
RUNTIME = BASE / 'runtime'
SOURCE = Path('/workspace/work/gen7-selfplay-capture-final-codex-20261112/run')
RUN = BASE / 'run'
PLAN = RUNTIME / 'configs/round71-compare.json'
sys.path.insert(0, str(RUNTIME))
from bridge_harness.loop_registry import sha
from bridge_harness.training import digest
from ops import prepare_gen7_alpha as prep


def main():
    assert not RUN.exists()
    old = json.loads((SOURCE / 'manifest.json').read_text())
    plan = json.loads(PLAN.read_text())
    inventory = []
    for p in sorted((SOURCE / 'receipts').glob('*.json')):
        row = json.loads(p.read_text())
        inventory.append(dict(index=row['index'], receipt_sha256=sha(p), episode_sha256=row['episode_sha256']))
    original = prep.atomic_json

    def write(path, data):
        if Path(path) == RUN / 'manifest.json':
            assert data['source_completed'] == len(inventory) == 437
            assert data['bots']['7s-32'] == old['bots']['7s-32']
            before, after = data['bots']['7s-32'], data['bots']['71s-32']
            assert {k for k in before if before[k] != after[k]} == {'id', 'identity', 'gen7_policy', 'artifact_sha256'}
            assert before['gen7'] == after['gen7'] and before['samples'] == after['samples'] == 32
            shutil.copy2(SOURCE / 'manifest.json', RUN / 'source-manifest.json')
            shutil.copy2(SOURCE / 'source-indices.json', RUN / 'ancestor-source-indices.json')
            shutil.copy2(PLAN, RUN / 'plan.json')
            original(RUN / 'source-completed-inventory.json', inventory)
            data.update(effective_generation=7.1, title='Gen 7.1 · Codex comparison with Gen7.0 and Gen6',
                worker_lifecycle=dict(normal_workers=3, ben_workers=0, retry_failures=False),
                bidding_conditions=['common', 'native'], preparation_sha256=sha(Path(__file__)),
                source_manifest_sha256=sha(RUN / 'source-manifest.json'),
                source_completed_inventory_sha256=sha(RUN / 'source-completed-inventory.json'),
                ancestor_source_indices_sha256=sha(RUN / 'ancestor-source-indices.json'),
                gen71_gate=dict(pair='71s-32~7s-32', minimum_boards=1000, confidence=0.95,
                    require_lower_above_zero=True, pooled_across_collectors=True,
                    condition='common', metric='played IMPs per board for71s-32',
                    selfplay_plan='configs/round71-selfplay.json', selfplay_launch_enabled=False,
                    external_tests_excluded=True),
                lineage_note='Only unused families from this independent producer; no shared shard. '
                             'All437Gen7.0capture records and every earlier frozen cohort remain preserved. '
                             'Same bots/models except new71s-32 uses policyv4.1; old7s-32 identity unchanged.')
            data['identity'] = digest({k:v for k,v in data.items() if k != 'identity'})
        return original(path, data)

    prep.atomic_json = write
    m = prep.prepare(RUN, SOURCE, PLAN)
    print(json.dumps(dict(manifest=m['identity'], target=m['target'], source_completed=m['source_completed'],
        pairs=m['pair_weights'], old_actor=m['bots']['7s-32']['identity'], new_actor=m['bots']['71s-32']['identity'],
        policy=m['bots']['71s-32']['artifact_sha256']['gen7_policy'], source_commit=m['source_commit'])))


if __name__ == '__main__':
    main()
