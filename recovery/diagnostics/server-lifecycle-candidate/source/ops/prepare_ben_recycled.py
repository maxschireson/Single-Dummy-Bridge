"""Prepare a versioned continuation retaining exact indices and prior receipts."""
import fcntl
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.loop_registry import sha, source_hash
from bridge_harness.training import digest
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from ops.gen5_runtime import state


def main():
    old_base = ROOT.parent / 'gen6-ben-recycled'
    source = old_base / 'runs/gen6-chatgpt-ben-recycled-20261111'
    root = ROOT / 'runs/gen6-chatgpt-ben-server-recycled-20261111'
    assert not root.exists(), 'Never overwrite a prepared cohort'
    locks = []
    for name in ('.supervisor.lock', '.writer.lock', '.capture-report.lock'):
        f = (source / name).open('a+')
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        locks.append(f)
    subprocess.run([str(old_base / '.venv/bin/python'), '-c',
        "import json;from pathlib import Path;from bridge_harness.mixed_arena import verify_generation;"
        "r=Path('runs/gen6-chatgpt-ben-recycled-20261111');verify_generation(r,json.loads((r/'manifest.json').read_text()))"],
        cwd=old_base, check=True)
    old = json.loads((source / 'manifest.json').read_text())
    assert old['identity'] == '65a7fd0a5b5090678b8892f1958bb451eeadf58d7df6af0044d3ad8f13ec41f5'
    rows = []
    inventory = {}
    for p in sorted((source / 'receipts').glob('*.json')):
        r = json.loads(p.read_text())
        assert r['manifest_identity'] in (old['identity'],old['retained_manifest'])
        assert sha(source / 'episodes' / f"{r['index']:06d}.json.gz") == r['episode_sha256']
        rows.append(r); inventory[p.name] = sha(p)
    assert len(rows) == 2015 == len(list((source / 'episodes').glob('*.json.gz')))
    assert len({r['index'] for r in rows}) == len({r['family'] for r in rows}) == 2015
    assert source_hash() == old['source_sha256']
    root.mkdir(parents=True)
    for folder in ('artifacts', 'assets', 'history', 'episodes', 'receipts'):
        shutil.copytree(source / folder, root / folder)
    for name in ('corpus.jsonl', 'source-indices.json', 'original-source-indices.json', 'plan.json', 'capture-equivalence.json'):
        if (source / name).exists():
            shutil.copy2(source / name, root / name)
    archive = root / 'history' / old['identity']
    archive.mkdir()
    for p in source.iterdir():
        if p.is_file() and p.suffix == '.json':
            shutil.copy2(p, archive / p.name)
    shutil.copy2(source / 'corpus.jsonl', archive / 'corpus.jsonl')
    for folder in ('episodes', 'receipts', 'failures', 'resolved-failures', 'diagnostics'):
        shutil.copytree(source / folder, archive / folder)
    for folder in ('bridge_harness', 'ops', 'scripts', 'configs', 'native'):
        shutil.copytree(old_base / folder, archive / 'runtime' / folder,
            ignore=shutil.ignore_patterns('__pycache__'))
    for name in ('launch_local.py', 'snapshot_feed.py', 'publish_authenticated.js', 'publish_dashboard.js', 'observe_launcher.py'):
        shutil.copy2(old_base / name, archive / 'runtime' / name)
    for folder in ('failures', 'resolved-failures', 'diagnostics'):
        (root / folder).mkdir()
    atomic_json(root / 'retained-receipts.json', inventory)
    m = {k: v for k, v in old.items() if k != 'identity'}
    runtime = set(old['runtime_sha256']) | {'ops/ben_board_executor.py', 'ops/ben_server_lifecycle.py', 'ops/diagnostic_supervisor.py',
        'ops/retained_receipts.py', 'ops/prepare_ben_recycled.py', 'ops/report_gen7_capture.py', 'ops/preflight_ben_recycling.py', 'launch_local.py'}
    m.update(campaign='gen6-ben-server-recycled-20261111', title='Gen6 fast self-play and BEN16 · recycled BEN workers',
        created_epoch=time.time(), source_generation=old['identity'], source_completed=2015,
        retained_manifest=old['identity'], retained_manifests=[old['identity'],old['retained_manifest']], retained_receipts='retained-receipts.json',
        retained_receipts_sha256=sha(root / 'retained-receipts.json'),
        runtime_sha256={n: sha(ROOT / n) for n in sorted(runtime)},
        worker_lifecycle={'ben_servers_per_board': 1, 'ben_boards_per_process': 1, 'normal_workers': 3, 'retry': False,
            'exit_status_required_before_commit': True},
        transition_note='Runtime-only continuation: all 8128 corpus indices and RNG seeds unchanged; 2015 exact prior receipts retained and pinned. Original unresolved failure archived, not silently cleared. No play/model/capture changes.')
    m['identity'] = digest(m)
    atomic_json(root / 'manifest.json', m)
    atomic_json(root / 'state.json', state(rows, m))
    atomic_json(root / 'heartbeat.json', dict(epoch=0, completed=2015, in_flight=[], workers=4, ben_workers=1))
    (root / 'STOP').write_text('Prepared only; remove after equivalence and lifecycle preflight passes.\n')
    verify_generation(root, m)
    print(json.dumps({'manifest': m['identity'], 'retained': len(rows), 'pending': m['target'] - len(rows)}))


if __name__ == '__main__':
    main()
