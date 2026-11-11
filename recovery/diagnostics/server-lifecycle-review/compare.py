"""Compare frozen and recycled lifecycles in the actual 3-normal + BEN mix."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
    TF_NUM_INTRAOP_THREADS='1', TF_NUM_INTEROP_THREADS='1', TF_CPP_MIN_LOG_LEVEL='3')
import json
import multiprocessing as mp
from pathlib import Path
import resource
import subprocess
import sys
import time
import urllib.request
import urllib.error
NEW = Path('/workspace/scratch/c7932514d17d/gen6-ben-server-recycled')
MODE = sys.argv[1] if len(sys.argv) > 1 else 'orchestrate'
BASE = NEW.parent / 'gen6-ben-recycled' if MODE == 'baseline' else NEW
sys.path.insert(0, str(BASE))
RUN = BASE / ('runs/gen6-chatgpt-ben-recycled-20261111' if MODE == 'baseline' else 'runs/gen6-chatgpt-ben-server-recycled-20261111')
OUT = Path('/workspace/scratch/c7932514d17d/gen6-ben-recycled/runs/gen6-chatgpt-ben-recycled-20261111/diagnostics/server-lifecycle-review')
from concurrent.futures import ProcessPoolExecutor
from ops.gen5_runtime import initialize_worker, play
from bridge_harness.corpus import load
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.training import digest


def semantics(record):
    # Capture every root and audit action, score, seed, assignment and auction.
    # BEN has no gaps/audits; self-play gap CPU caps can change capture volume,
    # so separately compare the complete root + tie-audit trajectory.
    episodes = {}
    for key, episode in record['unique_tables'].items():
        tables = []
        for table in episode['tables']:
            if table.get('node', '').startswith('gap'):
                continue
            tables.append({k: table.get(k) for k in ('node', 'depth', 'status', 'ns_score', 'declarer_tricks')})
            tables[-1]['actions'] = [{k: action.get(k) for k in
                ('ply', 'seat', 'controller', 'player', 'card', 'behavior_probabilities', 'selected_probability', 'selected_pimc_gap')}
                for action in table['actions']]
        episodes[key] = dict(board=episode['board'], seed=episode.get('seed'),
            assignments=episode.get('assignments'), tables=tables)
    return dict(index=record['index'], family=record['family'], pair=record['pair'],
        versions=record['versions'], regimes=record['regimes'], episodes=episodes)


def probe(root, manifest, board, index):
    start = time.time()
    record = play(root, manifest, board, index)
    semantic = semantics(record)
    return dict(index=index, pid=os.getpid(), seconds=time.time()-start,
        maxrss_kb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        semantic=semantic, fingerprint=digest(semantic),
        audit_counts=[len(e.get('audits', [])) for e in record['unique_tables'].values()])


def collect():
    manifest = json.loads((RUN / 'manifest.json').read_text())
    verify_generation(RUN, manifest)
    boards = load(RUN / manifest['corpus'])
    os.environ['BRIDGE_DDS_CACHE'] = str(OUT / (MODE + '-preflight-cache.sqlite'))
    arguments = dict(max_workers=3, mp_context=mp.get_context('spawn'),
        initializer=initialize_worker, initargs=(str(RUN),))
    if MODE == 'baseline':
        from ops.ben_board_executor import BenBoardExecutor
        ben = BenBoardExecutor(OUT, initialize_worker, (str(RUN),))
    else:
        from ops.ben_board_executor import BenBoardExecutor
        from ops.ben_server_lifecycle import BenServer
        ben = BenBoardExecutor(OUT, initialize_worker, (str(RUN),), server_factory=lambda: BenServer(RUN))
    rows = []
    with ProcessPoolExecutor(**arguments) as normal, ben:
        futures = [normal.submit(probe, str(RUN), manifest, boards[i].to_dict(), i) for i in (1930, 1931, 1932)]
        for _ in range(3):
            row = ben.submit(probe, str(RUN), manifest, boards[3062].to_dict(), 3062).result(timeout=600)
            rows.append(row)
            print(json.dumps({k:v for k,v in row.items() if k != 'semantic'}), flush=True)
        rows.extend(f.result(timeout=600) for f in futures)
    (OUT / f'{MODE}-equivalence.json').write_text(json.dumps(rows))


def orchestrate():
    server_log = (OUT / 'recycling-preflight-server.log').open('w')
    server = subprocess.Popen([sys.executable, 'src/gameapi.py', '--config', str(RUN/'assets/ben-16.conf'),
        '--port', '8087', '--host', '127.0.0.1', '--record', 'false'],
        cwd=NEW.parent/'ben', stdout=server_log, stderr=subprocess.STDOUT)
    try:
        for _ in range(60):
            if server.poll() is not None:
                raise RuntimeError('BEN server exited')
            try:
                urllib.request.urlopen('http://127.0.0.1:8087/', timeout=2)
                break
            except urllib.error.HTTPError:
                break
            except urllib.error.URLError:
                time.sleep(1)
        else:
            raise RuntimeError('BEN startup timed out')
        for mode in ('baseline', 'candidate'):
            if mode == 'candidate': server.terminate(); server.wait(timeout=30)
            subprocess.run([sys.executable, str(Path(__file__).resolve()), mode], cwd=NEW, check=True)
        old = json.loads((OUT/'baseline-equivalence.json').read_text())
        new = json.loads((OUT/'candidate-equivalence.json').read_text())
        assert len(old) == len(new) == 6
        assert [r['fingerprint'] for r in old] == [r['fingerprint'] for r in new], 'Play trajectory changed'
        assert len({r['pid'] for r in new[:3]}) == 3, 'BEN process was reused'
        assert all(not any(r['audit_counts']) for r in new[:3]), 'BEN audits enabled'
        m = json.loads((RUN/'manifest.json').read_text())
        report = dict(status='passed', manifest=m['identity'], epoch=time.time(), boards_per_lifecycle=6,
            ben_replacements=3, ben_index=3062, self_indices=[621,622,623], production_commits=0,
            fingerprints=[r['fingerprint'] for r in new],
            ben_worker_pids=[r['pid'] for r in new[:3]], ben_maxrss_kb=[r['maxrss_kb'] for r in new[:3]],
            scope='Full runtime replay; root/tie-audit cards, probabilities, seeds, auctions, assignments and scores match; source/model/corpus hashes identical.')
        (OUT/'server-recycling-review.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report), flush=True)
    finally:
        server.terminate(); server.wait(timeout=30); server_log.close()


if __name__ == '__main__':
    if MODE == 'orchestrate':
        orchestrate()
    else:
        collect()
