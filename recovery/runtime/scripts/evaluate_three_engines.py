#!/usr/bin/env python3
"""Extend the frozen 200-deal bidding-sampler comparison with full-search BEN.

Each original deal gets BEN/uniform and BEN/informed partnership-swapped pairs.
The existing informed/uniform games are replay-validated and reused verbatim.
No auctions, model weights, search budgets, or completed games are regenerated.
"""
import argparse
from contextlib import contextmanager
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.request import urlopen

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.bidding_sampling import AuctionWeights, WeightedSampler
from bridge_harness.core import Board, Game, SEATS, card, hand_text, imps, symbol
from bridge_harness.corpus import load
from bridge_harness.players import BenPlayer, PIMCPlayer
from bridge_harness.report import summarize
from bridge_harness.runner import play_table, replay
from bridge_harness.training import digest

VARIANTS = ('uniform32', 'bidding32')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, indent=2) + '\n')
    tmp.replace(path)


def read_record(path):
    with gzip.open(path, 'rt') as f:
        return json.load(f)


def write_record(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    with gzip.open(tmp, 'wt') as f:
        json.dump(data, f)
    tmp.replace(path)


def validate(record, board, seed, expected_candidate, expected_baseline):
    """Check identity, settings, legal replay and the BEN information boundary."""
    if record['board'] != board.to_dict():
        raise ValueError('Changed deal, auction, contract, vulnerability, or lead')
    c = record['config']
    for key, expected in dict(mode='partnership', seed=seed, samples=32,
                              objective='tricks', batch=True, near_tie=.125,
                              candidate=expected_candidate, baseline=expected_baseline).items():
        if c[key] != expected:
            raise ValueError(f'Unexpected comparison setting: {key}')
    if record['assignments'] != [[expected_candidate, expected_baseline] * 2,
                                 [expected_baseline, expected_candidate] * 2]:
        raise ValueError('Incorrect partnership swap')
    replay(record)
    for i, table in enumerate(record['tables']):
        g = Game(board)
        for action in table['actions']:
            o = g.observation()
            if action['player'] != record['assignments'][i][o.controller]:
                raise ValueError('Wrong player for seat')
            if action['player'] in VARIANTS and len(o.legal) > 1:
                if not (action.get('samples') == action.get('dds_calls') == 32
                        and action.get('batch') and action.get('objective') == 'tricks'):
                    raise ValueError('Changed PIMC budget/objective')
            if action['player'] == 'ben' and not action.get('forced'):
                expected = dict(hand=hand_text(o.original_hand(o.controller)),
                                seat=SEATS[o.controller], dealer=SEATS[o.dealer],
                                vul=o.vulnerability, ctx=BenPlayer.context(o.auction),
                                matchtype='IMP', details='false')
                endpoint = 'play' if o.history else 'lead'
                if o.history:
                    expected.update(dummy=hand_text(o.original_hand(o.contract.dummy)),
                                    played=''.join(symbol(c) for _, c in o.history), format='false')
                if action['request'] != expected or action['endpoint'] != endpoint:
                    raise ValueError('BEN request contains incorrect information')
            g.play(card(action['card']))
    if record['status'] == 'ok':
        if len(record['tables']) != 2 or any(len(t['actions']) != 52 for t in record['tables']):
            raise ValueError('Incomplete pair marked successful')
        a, b = record['tables']
        difference = a['ns_score'] - b['ns_score']
        if record['score_difference'] != difference or record['imps'] != imps(difference):
            raise ValueError('Incorrect oriented score')


def source_paths(source):
    return [source / 'play-corpus.jsonl', source / 'protocol.json', source / 'auction_weights.npz']


def prepare(args):
    source, out = args.source_run.resolve(), args.out.resolve()
    original = json.loads((source / 'protocol.json').read_text())
    boards = load(source / 'play-corpus.jsonl')
    ids = [digest(b.hands) for b in boards]
    assert len(boards) == len(set(ids)) == 200
    assert ids == original['play_deal_ids']
    assert sha(source / 'auction_weights.npz') == original['weights_sha256']
    assert all(b.contract and b.opening_lead is None for b in boards)
    hashes = {}
    for b, did in zip(boards, ids):
        path = source / 'episodes' / f'{did}.json.gz'
        r = read_record(path)
        validate(r, b, original['decision_seed'], 'bidding32', 'uniform32')
        assert r['status'] == 'ok'
        hashes[did] = sha(path)
    if (out / 'protocol.json').exists():
        raise ValueError('Protocol already frozen; use run or report')
    out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.ben_config, out / 'ben.conf')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.ben_dir, text=True).strip()
    code_files = [ROOT / 'bridge_harness' / (n + '.py') for n in
                  ('core', 'runner', 'players', 'sampling', 'bidding_sampling', 'auction_belief', 'dds', 'report')]
    protocol = dict(schema_version=1, created_unix=time.time(), original_source=str(source),
                    independent_deals=200, deal_ids=ids, decision_seed=original['decision_seed'],
                    source_hashes={p.name: sha(p) for p in source_paths(source)},
                    original_episode_hashes=hashes, code_hashes={str(p.relative_to(ROOT)): sha(p) for p in code_files},
                    native_sha256=sha(ROOT / 'bridge_harness/libbridge_dds.so'),
                    ben_revision=revision, ben_config_sha256=sha(out / 'ben.conf'),
                    comparisons=['bidding32 - uniform32', 'ben - uniform32', 'ben - bidding32'],
                    new_games=800, reused_games=400, samples=32, objective='tricks', near_tie=.125,
                    ben_settings='Unmodified portable neural/DDS calibration config; two DDS threads; full play search',
                    fairness='Same 200 deals/auctions/contracts/vulnerability; partnerships swapped; natural opening leads; as-configured time budgets',
                    stop_rule='All 200 deals; failures retained; no outcome-dependent stopping or replacement',
                    population='Previously inspected frozen-model BEN-neural-auction test population; no additional tuning',
                    sign='Positive favors the first named engine; paired trick swing includes declaring and defending')
    write_json(out / 'protocol.json', protocol)
    print(json.dumps({k:v for k,v in protocol.items() if k not in ('deal_ids','original_episode_hashes','code_hashes')}, indent=2))


def verify_frozen(out):
    p = json.loads((out / 'protocol.json').read_text())
    source = Path(p['original_source'])
    for name, expected in p['source_hashes'].items():
        if sha(source / name) != expected: raise ValueError(f'Changed source: {name}')
    for name, expected in p['code_hashes'].items():
        if sha(ROOT / name) != expected: raise ValueError(f'Changed engine code: {name}')
    if sha(out / 'ben.conf') != p['ben_config_sha256']: raise ValueError('Changed BEN config')
    if sha(ROOT / 'bridge_harness/libbridge_dds.so') != p['native_sha256']: raise ValueError('Changed native solver')
    return p, source


@contextmanager
def server(args, out):
    log_path = out / f'ben-worker-{args.worker_index}.log'
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
               TF_NUM_INTRAOP_THREADS='1', TF_NUM_INTEROP_THREADS='1')
    url = f'http://127.0.0.1:{args.port}'
    with log_path.open('a') as log:
        process = subprocess.Popen([str(args.ben_python), '-u', 'src/gameapi.py', '--config', str(out/'ben.conf'),
                                    '--host', '127.0.0.1', '--port', str(args.port), '--nolimit', 'true',
                                    '--record', 'false'], cwd=args.ben_dir, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            ready = False
            for _ in range(240):
                if process.poll() is not None: raise RuntimeError('BEN exited during startup; see worker log')
                try:
                    with urlopen(url, timeout=1) as response: response.read()
                    ready = True
                    break
                except OSError: time.sleep(.5)
            if not ready: raise TimeoutError('BEN startup exceeded 120 seconds')
            yield url
        finally:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()


def play_pair(board, variant, weights, url, seed, path, progress, timeout):
    if path.exists():
        r = read_record(path)
        validate(r, board, seed, 'ben', variant)
        if r['status'] == 'ok': return r
        raise RuntimeError(f'Existing failed pair retained at {path}; inspect before explicitly retrying')
    if variant == 'bidding32':
        ours = PIMCPlayer(32, 'tricks', True, .125,
                         sampler_factory=lambda o: WeightedSampler(o, weights.logits(o), 1.))
    else:
        ours = PIMCPlayer(32, 'tricks', True, .125)
    players = {'ben': BenPlayer(url, timeout), variant: ours}
    r = dict(schema_version=1, status='incomplete', board=board.to_dict(),
             config=dict(mode='partnership', candidate='ben', baseline=variant, samples=32,
                         objective='tricks', batch=True, near_tie=.125, seed=seed),
             assignments=[['ben', variant] * 2, [variant, 'ben'] * 2], tables=[])
    started = time.perf_counter()
    table_dir = path.parent / 'tables' / path.stem.removesuffix('.json')
    table_dir.mkdir(parents=True, exist_ok=True)
    try:
        for index, assignment in enumerate(r['assignments']):
            table_path = table_dir / f'{index}.json.gz'
            if table_path.exists():
                table = read_record(table_path)
                if table['status'] != 'ok': raise RuntimeError('Failed table requires inspection')
            else:
                def event(action):
                    write_json(progress, dict(updated_unix=time.time(), board=board.id, variant=variant,
                                             table=index, ply=action['ply'], player=action['player'],
                                             last_decision_seconds=action['seconds'], pair_seconds=time.perf_counter()-started))
                table = play_table(board, assignment, players, seed, on_event=event)
                write_record(table_path, table)
            r['tables'].append(table)
            if table['status'] != 'ok': break
        r['status'] = 'ok' if len(r['tables']) == 2 and all(t['status']=='ok' for t in r['tables']) else 'error'
        if r['status'] == 'ok':
            a, b = r['tables']
            r['score_difference'] = a['ns_score'] - b['ns_score']
            r['imps'] = imps(r['score_difference'])
            r['first_difference'] = next((i for i,(x,y) in enumerate(zip(a['actions'],b['actions'])) if x['card'] != y['card']), None)
        validate(r, board, seed, 'ben', variant)
        write_record(path, r)
        return r
    finally:
        ours.close()


def report(out):
    protocol, source = verify_frozen(out)
    boards = load(source / 'play-corpus.jsonl')
    rows = {v:{} for v in VARIANTS}
    originals = {}
    for b in boards:
        did = digest(b.hands)
        original = source / 'episodes' / f'{did}.json.gz'
        if sha(original) != protocol['original_episode_hashes'][did]: raise ValueError('Changed original episode')
        originals[did] = read_record(original)
        for v in VARIANTS:
            path = out / v / f'{did}.json.gz'
            if path.exists():
                r = read_record(path); validate(r, b, protocol['decision_seed'], 'ben', v)
                rows[v][did] = r
    common = [d for d in protocol['deal_ids'] if all(d in rows[v] and rows[v][d]['status']=='ok' for v in VARIANTS)]
    compact = lambda rs: {k:v for k,v in summarize(rs).items() if k != 'largest_differences'}
    result = dict(planned_deals=200, matched_completed_deals=len(common), complete=len(common)==200,
                  updated_unix=time.time(), reused_full_200=compact(list(originals.values())),
                  common_deal_ids=common, matched_comparisons={}, all_ben_progress={})
    for v in VARIANTS:
        result['all_ben_progress']['ben - '+v] = compact(list(rows[v].values()))
        result['matched_comparisons']['ben - '+v] = compact([rows[v][d] for d in common])
    result['matched_comparisons']['bidding32 - uniform32'] = compact([originals[d] for d in common])
    write_json(out/'summary.json', result)
    print(json.dumps(dict(matched_completed_deals=len(common), planned_deals=200,
                         comparisons={k:{m:s[m] for m in ('completed_pairs','mean_tricks','mean_imps','tricks_cluster_bootstrap_95_interval')}
                                      for k,s in result['matched_comparisons'].items()})), flush=True)
    return result


def run(args):
    out = args.out.resolve()
    protocol, source = verify_frozen(out)
    revision = subprocess.check_output(['git','rev-parse','HEAD'], cwd=args.ben_dir, text=True).strip()
    if revision != protocol['ben_revision']: raise ValueError('Changed BEN revision')
    boards = load(source/'play-corpus.jsonl')
    assert 0 <= args.worker_index < args.workers
    # Exclusive worker lock prevents two invocations from writing the same games.
    import fcntl
    with (out/f'worker-{args.worker_index}.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        weights = AuctionWeights(source/'auction_weights.npz')
        with server(args, out) as url:
            for index, board in enumerate(boards):
                if index % args.workers != args.worker_index: continue
                variants = VARIANTS if index % 2 == 0 else VARIANTS[::-1]
                for variant in variants:
                    path = out/variant/f'{digest(board.hands)}.json.gz'
                    result = play_pair(board, variant, weights, url, protocol['decision_seed'], path,
                                       out/f'progress-{args.worker_index}.json', args.timeout)
                    if result['status'] != 'ok': raise RuntimeError(f'Failed pair retained: {path}')
                print(json.dumps(dict(worker=args.worker_index, completed_original_index=index,
                                      deal_id=digest(board.hands), unix=time.time())), flush=True)
                if args.workers == 1: report(out)
        write_json(out/f'worker-{args.worker_index}-complete.json', dict(completed_unix=time.time()))
    report(out)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('prepare','run','report'))
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--source-run', type=Path)
    p.add_argument('--ben-dir', type=Path)
    p.add_argument('--ben-python', type=Path)
    p.add_argument('--ben-config', type=Path)
    p.add_argument('--port', type=int, default=8891)
    p.add_argument('--workers', type=int, default=1)
    p.add_argument('--worker-index', type=int, default=0)
    p.add_argument('--timeout', type=float, default=600)
    args = p.parse_args()
    if args.mode == 'prepare': prepare(args)
    elif args.mode == 'run': run(args)
    else: report(args.out.resolve())


if __name__ == '__main__': main()
