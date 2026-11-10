"""Frozen, resumable common-auction 5RZ-192 versus BEN-16 paired match."""
import argparse
import configparser
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from urllib.request import urlopen

for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
          'TF_NUM_INTRAOP_THREADS', 'TF_NUM_INTEROP_THREADS'):
    os.environ[k] = '1'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['BRIDGE_DDS_CACHE'] = ''
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from bridge_harness.bidding_env import make_board, deal_key
from bridge_harness.core import Board, imps
from bridge_harness.gen5_arena import auction
from bridge_harness.gen5r import reduction, load_plan
from bridge_harness.loop_registry import sha
from bridge_harness.runner import play_table, replay
from bridge_harness.selfplay import atomic_json

MODELS = dict(policy='models/cardplay/gen5-2026-11-10/policy.npz',
              belief='models/cardplay/gen5-belief-2026-11-10/belief.npz',
              bidding='models/bidding/gen5-2026-11-10/bidder.keras')
EXPECTED = dict(policy='03e70a6f6021c8bed471dc9de53f462b0e991320ff4ad7734bcc20f54c5aff18',
                belief='99330ad3b1387a6fd8d78b297b3d1c915dbb67f5e9e624c871b997c0352fd37a',
                bidding='9ee52f3baa79c837001e0cb515c61a9a179cb1bf66cd5503e46331245c014dcc')


def write_gz(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    with gzip.open(tmp, 'wt') as f:
        json.dump(data, f, separators=(',', ':'))
    tmp.replace(path)


def read_gz(path):
    with gzip.open(path, 'rt') as f:
        return json.load(f)


def prepare(a):
    if (a.run / 'manifest.json').exists():
        return verify(a.run)
    from bridge_harness.bidding_ppo import Policy
    from ops.prepare_ben_round5 import validate
    a.run.mkdir(parents=True, exist_ok=True)
    for k, p in MODELS.items():
        assert sha(ROOT / p) == EXPECTED[k], k
    config = ROOT / 'configs/ben-gen5-16.conf'
    cfg = configparser.ConfigParser(interpolation=None); cfg.read(config)
    validate(cfg, 16)
    provenance = json.loads((ROOT / 'configs/ben-gen5-16.provenance.json').read_text())
    assert sha(config) == provenance['config_sha256']
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=a.ben, text=True).strip()
    assert revision == provenance['source_commit']
    for item in provenance['model_sha256'].values():
        assert sha(a.ben / item['path']) == item['sha256'], item['path']
    spec = dict(id='5RZ192', samples=192, near_tie=0., exploration=0.,
                belief_kind='public', policy_role='pimc-ties-only',
                policy=MODELS['policy'], belief=MODELS['belief'],
                layout_reduction=reduction(load_plan(), 192))
    boards = [make_board(a.seed, i, 'test') for i in range(a.boards)]
    assert len({deal_key(b.hands, True) for b in boards}) == a.boards
    atomic_json(a.run / 'reserved-families.json', [deal_key(b.hands, True) for b in boards])
    bidder = Policy.load(ROOT / MODELS['bidding'])
    auctions = []
    for i, b in enumerate(boards):
        bid_board, decisions = auction(b, [bidder] * 4)
        auctions.append(dict(index=i, family=deal_key(b.hands, True), board=bid_board.to_dict(),
                             raw_board=b.to_dict(), bidding=decisions))
        if (i + 1) % 20 == 0:
            print(json.dumps(dict(phase='auctions', completed=i + 1)), flush=True)
    atomic_json(a.run / 'auctions.json', auctions)
    (a.run / 'ben.conf').write_bytes(config.read_bytes())
    code = {str(p.relative_to(ROOT)): sha(p) for p in (ROOT / 'bridge_harness').glob('*.py')}
    code['scripts/match_gen5rz_ben.py'] = sha(Path(__file__))
    ben_code = {str(p.relative_to(a.ben)): sha(p) for p in (a.ben / 'src').rglob('*.py')}
    m = dict(schema='gen5rz-ben-common-v1', target=a.boards, seed=a.seed,
             candidate=spec, opponent='BEN-16', candidate_models=EXPECTED,
             model_paths=MODELS, ben_root=str(a.ben), ben_source_revision=revision,
             ben_models=provenance['model_sha256'], ben_config_sha256=sha(a.run / 'ben.conf'),
             ben_code_hashes=ben_code, code_hashes=code,
             dds_path='bridge_harness/libbridge_dds.so',
             dds_sha256=sha(ROOT / 'bridge_harness/libbridge_dds.so'),
             auctions_sha256=sha(a.run / 'auctions.json'),
             reserved_families_sha256=sha(a.run / 'reserved-families.json'),
             source_commit='552c13837e7f660464d0fba644c3d557bda59905',
             evaluation_only=True, persistent_dds_cache=False, created=time.time(),
             bidding='current Gen5 candidate-2 neural-only bidder, all four seats; common auction in both rooms',
             rooms='5RZ NS / BEN EW; BEN NS / 5RZ EW; alternate play order',
             sample_note='5RZ budget 192, large positions draw 768 then solve at most 192 representatives; BEN retained target 16',
             interpretation='positive IMPs favor 5RZ; paired whole-board cardplay comparison, not equal-time guarantee')
    atomic_json(a.run / 'manifest.json', m)
    return m


def verify(run):
    m = json.loads((run / 'manifest.json').read_text())
    for k, path in m['model_paths'].items():
        assert sha(ROOT / path) == m['candidate_models'][k], path
    for path, digest in m['code_hashes'].items():
        assert sha(ROOT / path) == digest, path
    for file, field in [('auctions.json', 'auctions_sha256'), ('ben.conf', 'ben_config_sha256'),
                        ('reserved-families.json', 'reserved_families_sha256')]:
        assert sha(run / file) == m[field], file
    assert sha(ROOT / m['dds_path']) == m['dds_sha256']
    for path, digest in m['ben_code_hashes'].items():
        assert sha(Path(m['ben_root']) / path) == digest, path
    for item in m['ben_models'].values():
        assert sha(Path(m['ben_root']) / item['path']) == item['sha256'], item['path']
    return m


def worker(a):
    from bridge_harness.mixed_arena import ArenaPlayer
    from bridge_harness.round5_ben import Round5BenPlayer
    m = verify(a.run)
    server = None; players = {}; server_log = None
    try:
        server_log = (a.run / f'ben-{a.worker}.log').open('a')
        port = a.port + a.worker
        server = subprocess.Popen([sys.executable, '-u', 'src/gameapi.py', '--config', str(a.run / 'ben.conf'),
                                   '--host', '127.0.0.1', '--port', str(port), '--nolimit', 'true', '--record', 'false'],
                                  cwd=m['ben_root'], stdout=server_log, stderr=subprocess.STDOUT)
        url = f'http://127.0.0.1:{port}'
        for _ in range(180):
            if server.poll() is not None:
                raise RuntimeError('BEN startup failed; inspect own server log')
            try:
                with urlopen(url, timeout=1) as r:
                    r.read()
                break
            except OSError:
                time.sleep(.5)
        else:
            raise RuntimeError('BEN startup timeout')
        players = {'5RZ': ArenaPlayer(m['candidate'], ROOT), 'ben': Round5BenPlayer(url, 600, 16)}
        rows = json.loads((a.run / 'auctions.json').read_text())
        for row in rows:
            i = row['index']
            if i % a.workers != a.worker or (a.limit is not None and i >= a.limit):
                continue
            target = a.run / 'episodes' / f'{i:04d}.json.gz'
            if target.exists():
                continue
            started = time.time(); tables = []
            board = Board.from_dict(row['board'])
            for room in ((0, 1) if i % 2 == 0 else (1, 0)):
                room_file = a.run / 'tables' / f'{i:04d}-{room}.json.gz'
                assignments = ['5RZ' if seat % 2 == room else 'ben' for seat in range(4)]
                if room_file.exists():
                    record = read_gz(room_file)
                    assert record['board'] == row['board'] and record['assignments'] == assignments
                    replay(record)
                else:
                    def progress(action):
                        if action['player'] == '5RZ' and not action.get('forced'):
                            gap = action['estimates'][action['card']]['gap_to_best']
                            assert gap <= 1.0001e-9, ('non-tie policy move', i, room, action['ply'], gap)
                        atomic_json(a.run / f'worker-{a.worker}-status.json',
                                    dict(index=i, room=room, ply=action['ply'], player=action['player'],
                                         seconds=action['seconds'], updated=time.time()))
                    table = play_table(board, assignments, players, seed=m['seed'] + i, on_event=progress)
                    record = dict(board=row['board'], tables=[table], assignments=assignments)
                    if table['status'] != 'ok':
                        atomic_json(a.run / f'failed-{i}-{room}.json', record)
                        raise RuntimeError(table['traceback'])
                    replay(record)
                    write_gz(room_file, record)
                tables.append(dict(room=room, record=record))
            tables.sort(key=lambda t: t['room'])
            scores = [t['record']['tables'][0]['ns_score'] for t in tables]
            result = dict(index=i, family=row['family'], tables=tables,
                          score_difference=scores[0] - scores[1], imps=imps(scores[0] - scores[1]),
                          seconds=time.time() - started, completed=time.time())
            write_gz(target, result)
            print(json.dumps(dict(index=i, imps=result['imps'], seconds=result['seconds'])), flush=True)
    except Exception:
        with (a.run / 'errors.jsonl').open('a') as f:
            f.write(json.dumps(dict(worker=a.worker, error=traceback.format_exc(), time=time.time())) + '\n')
        raise
    finally:
        for p in players.values():
            p.close()
        if server:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill(); server.wait()
        if server_log:
            server_log.close()


def summarize(run, legal=False):
    from scipy.stats import t as student_t
    m = json.loads((run / 'manifest.json').read_text())
    rows = [read_gz(p) for p in sorted((run / 'episodes').glob('*.json.gz'))]
    vals = np.array([r['imps'] for r in rows], float); n = len(rows)
    times = {p: [] for p in ('5RZ', 'ben')}; nf = {p: [] for p in times}
    gaps = []; reduction_count = 0; policy_count = 0; passed = 0
    for row in rows:
        scores = []
        for room in row['tables']:
            record = room['record']
            if legal:
                replay(record)
            table = record['tables'][0]; scores.append(table['ns_score'])
            passed += record['board']['contract'] is None
            for a in table['actions']:
                times[a['player']].append(a['seconds'])
                if not a.get('forced'):
                    nf[a['player']].append(a['seconds'])
                    if a['player'] == '5RZ':
                        gaps.append(a['estimates'][a['card']]['gap_to_best'])
                        reduction_count += 'layout_reduction' in a
                        policy_count += 'selector_predictions' in a
        assert row['imps'] == imps(scores[0] - scores[1])
    assert len({r['family'] for r in rows}) == n
    assert not gaps or max(gaps) <= 1.0001e-9
    se = float(vals.std(ddof=1) / math.sqrt(n)) if n > 1 else None
    mean = float(vals.mean()) if n else None
    report = dict(boards=n, target=m['target'], complete=n == m['target'],
                  total_imps=int(vals.sum()), imps_per_board=mean, se=se,
                  ci95=[mean - float(student_t.ppf(.975, n-1)) * se,
                        mean + float(student_t.ppf(.975, n-1)) * se] if n > 1 else None,
                  wins=int((vals > 0).sum()), losses=int((vals < 0).sum()), ties=int((vals == 0).sum()),
                  passed_out_tables=passed, candidate_nonforced_decisions=len(gaps),
                  candidate_policy_tiebreaks=policy_count, candidate_reduced_positions=reduction_count,
                  maximum_selected_pimc_gap=max(gaps) if gaps else None,
                  timing={p: dict(decisions=len(v), total_seconds=sum(v),
                                  seconds_per_paired_board=sum(v)/n if n else None,
                                  nonforced_mean_ms=1000 * float(np.mean(nf[p])) if nf[p] else None)
                          for p, v in times.items()},
                  replay_verified_tables=len(rows)*2 if legal else None, updated=time.time())
    atomic_json(run / 'result.json', report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare', 'run', 'worker', 'summary'])
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--ben', type=Path, default=Path('/workspace/scratch/63fa72341134/ben-runtime'))
    p.add_argument('--boards', type=int, default=100)
    p.add_argument('--seed', type=int, default=202611101745)
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--worker', type=int, default=0)
    p.add_argument('--port', type=int, default=18740)
    p.add_argument('--limit', type=int)
    a = p.parse_args(); a.run = a.run.resolve(); a.ben = a.ben.resolve()
    if a.command == 'summary':
        print(json.dumps(summarize(a.run, legal=True)), flush=True); return
    if a.command == 'worker':
        worker(a); return
    prepare(a)
    if a.command == 'prepare':
        print(json.dumps(dict(phase='prepared', target=a.boards)), flush=True); return
    import fcntl
    lock = (a.run / 'writer.lock').open('a'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    children = []
    for i in range(a.workers):
        log = (a.run / f'worker-{i}.log').open('a')
        cmd = [sys.executable, '-u', __file__, 'worker', '--run', str(a.run), '--workers', str(a.workers),
               '--worker', str(i), '--port', str(a.port)]
        if a.limit is not None:
            cmd.extend(['--limit', str(a.limit)])
        children.append((subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT), log))
    atomic_json(a.run / 'started.json', dict(time=time.time(), workers=a.workers, target=a.boards, limit=a.limit))
    last = -1
    while any(c.poll() is None for c, _ in children):
        time.sleep(10)
        r = summarize(a.run)
        if r['boards'] != last:
            print(json.dumps(r), flush=True); last = r['boards']
    for _, log in children:
        log.close()
    print(json.dumps(summarize(a.run, legal=True)), flush=True)
    if any(c.returncode for c, _ in children):
        raise SystemExit('Worker failed; retained tables and errors in run directory')


if __name__ == '__main__':
    main()
