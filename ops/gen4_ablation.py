"""Matched Gen4 component diagnosis, separate from the live arena cohort."""
import argparse
from copy import deepcopy
from concurrent.futures import FIRST_COMPLETED, wait
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.core import Board, imps
from bridge_harness.corpus import load, save
from bridge_harness.bidding_env import deal_key
from bridge_harness.fork_audit import ForkBudget, collect_board
from bridge_harness.improvement import read, writer_lock
from bridge_harness.loop_registry import sha, source_hash
from bridge_harness.mixed_arena import ArenaPlayer, verify_generation
from bridge_harness.runner import replay
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest
from ops.independent_workers import IndependentWorkers

VARIANTS = ('4', '4p', '4b')


def initialize(source, dest, count):
    if dest.exists():
        raise ValueError('Refusing to overwrite diagnostic run')
    original = read(source/'manifest.json')
    verify_generation(source, original)
    boards = load(source/original['corpus'])
    # Selection uses only family hashes, never completion speed or scores.
    boards.sort(key=lambda b: digest(['gen4-component-ablation-v1', deal_key(b.hands, True)]))
    if not 1 <= count <= len(boards):
        raise ValueError('Invalid diagnostic hand count')
    dest.mkdir(parents=True)
    for folder in ('artifacts', 'assets'):
        shutil.copytree(source/folder, dest/folder)
    bots = {v: deepcopy(original['bots'][v]) for v in ('4', '3')}
    for name, belief_parent, policy_parent in [('4p', '3', '4'), ('4b', '4', '3')]:
        spec = deepcopy(bots['3'])
        spec.pop('identity')
        spec['id'] = name
        for component, parent in [('belief', belief_parent), ('policy', policy_parent)]:
            spec[component] = bots[parent][component]
            spec['artifact_sha256'][component] = bots[parent]['artifact_sha256'][component]
        spec['identity'] = digest(spec)
        bots[name] = spec
    save(boards[:count], dest/'corpus.jsonl')
    manifest = dict(schema='gen4-component-ablation-v1', campaign='gen4-components',
        bots=bots, target=count, corpus='corpus.jsonl', corpus_sha256=sha(dest/'corpus.jsonl'),
        source_sha256=source_hash(), runtime_sha256={'ops/gen4_ablation.py': sha(Path(__file__))},
        seed=202611091617, source_manifest_identity=original['identity'],
        created_epoch=time.time(), variants=list(VARIANTS), baseline='3',
        settings=dict(samples=32, near_tie=.125, exploration=0),
        protocol='Each family: 4, 4p and 4b each play Gen3 with swapped partnerships, same v4 auction and decision seed. No historical-bidder crossover or policy forks.',
        interpretation='Exploratory component diagnosis. Frozen source-cohort deals are reused explicitly; never pool these observations with its published scores. No training or promotion.',
        comparisons={'4p-3':'Gen4 policy effect with Gen3 belief',
                     '4b-3':'Gen4 belief effect with Gen3 policy',
                     '4-3':'Whole Gen4 update under common bidding',
                     '4-4b':'Policy effect with Gen4 belief',
                     '4-4p':'Belief effect with Gen4 policy',
                     'interaction':'(4-3) - (4p-3) - (4b-3); descriptive interaction in IMP units'})
    manifest['identity'] = digest(manifest)
    atomic_json(dest/'manifest.json', manifest)
    atomic_json(dest/'state.json', summary([], manifest))
    return manifest


def validate(record, manifest, board, index):
    if (record['manifest_identity'] != manifest['identity'] or record['index'] != index
        or record['board'] != board.to_dict() or record['family'] != deal_key(board.hands, True)
        or record['versions'] != {k:v['identity'] for k,v in manifest['bots'].items()}
        or set(record['matches']) != set(VARIANTS)):
        raise ValueError('Diagnostic identity changed')
    for version in VARIANTS:
        match = record['matches'][version]
        for room, episode in enumerate(match['rooms']):
            replay(episode)
            seats = [version, '3', version, '3'] if room == 0 else ['3', version, '3', version]
            if (episode['assignments'] != seats or episode['board'] != board.to_dict()
                or episode['versions'] != record['versions'] or len(episode['tables']) != 1
                or episode['audits']):
                raise ValueError('Diagnostic assignment changed')
        if len(match['rooms']) != 2:
            raise ValueError('Missing swapped room')
        delta = match['rooms'][0]['tables'][0]['ns_score'] - match['rooms'][1]['tables'][0]['ns_score']
        if match['imps'] != imps(delta):
            raise ValueError('Wrong IMP orientation')


def play(root, manifest, board_dict, index):
    board = Board.from_dict(board_dict)
    players = {}
    versions = {k:v['identity'] for k,v in manifest['bots'].items()}
    try:
        for key, spec in manifest['bots'].items():
            players[key] = ArenaPlayer(spec, root)
        matches = {}
        seed = int(digest([manifest['seed'], board.id, 'play'])[:12], 16)
        order = sorted(VARIANTS, key=lambda v:digest([seed,v]))
        for version in order:
            rooms = {}
            room_order = (0,1) if int(digest([seed,version,'order'])[:4],16)%2 == 0 else (1,0)
            for room in room_order:
                seats = [version, '3', version, '3'] if room == 0 else ['3', version, '3', version]
                rooms[room] = collect_board(board, players, seats, seed,
                    ForkBudget(probability=0, multiplier=1, max_depth=0, max_forks=0), versions)
            matches[version] = dict(rooms=[rooms[0], rooms[1]],
                imps=imps(rooms[0]['tables'][0]['ns_score']-rooms[1]['tables'][0]['ns_score']))
        record = dict(manifest_identity=manifest['identity'], index=index, board=board_dict,
            family=deal_key(board.hands, True), versions=versions, matches=matches, completed_epoch=time.time())
        validate(record, manifest, board, index)
        return record
    finally:
        for player in players.values():
            player.close()


def summary(records, manifest):
    import numpy as np
    from scipy.stats import t
    values = {v: np.array([r['matches'][v]['imps'] for r in records], float) for v in VARIANTS}
    contrasts = {'4p-3': values['4p'], '4b-3': values['4b'], '4-3': values['4'],
                 '4-4b': values['4']-values['4b'], '4-4p': values['4']-values['4p'],
                 'interaction': values['4']-values['4p']-values['4b']}
    stats = {}
    for name, a in contrasts.items():
        mean = float(a.mean()) if len(a) else None
        half = float(t.ppf(.975,len(a)-1)*a.std(ddof=1)/np.sqrt(len(a))) if len(a)>1 else None
        stats[name] = dict(n=len(a), total=float(a.sum()), mean=mean,
            descriptive_95_ci=[mean-half,mean+half] if half is not None else None)
    return dict(manifest_identity=manifest['identity'], completed=len(records), target=manifest['target'],
        tables=6*len(records), comparisons=stats, epoch=time.time(),
        interpretation='Positive means favor the named update. Differences are paired within family; descriptive interim intervals, no automatic promotion.')


def collect(root, workers):
    with writer_lock(root):
        m = read(root/'manifest.json'); verify_generation(root, m)
        boards = load(root/m['corpus']); records = []
        for path in sorted((root/'episodes').glob('*.json.gz')):
            r = read(path); validate(r,m,boards[r['index']],r['index']); records.append(r)
        done = {r['index'] for r in records}
        if len(done) != len(records) or len({r['family'] for r in records}) != len(records):
            raise ValueError('Duplicate diagnostic family')
        os.environ['BRIDGE_DDS_CACHE'] = str(root/'dds-cache.sqlite')
        IndependentWorkers.run = root
        jobs = iter(i for i in range(len(boards)) if i not in done)
        pending = {}
        with IndependentWorkers(max_workers=workers) as pool:
            def submit():
                if (root/'STOP').exists(): return
                index = next(jobs, None)
                if index is not None:
                    pending[pool.submit(play,str(root),m,boards[index].to_dict(),index)] = index
            for _ in range(workers): submit()
            while pending:
                completed,_ = wait(pending,timeout=10,return_when=FIRST_COMPLETED)
                atomic_json(root/'heartbeat.json',dict(epoch=time.time(),completed=len(records),in_flight=sorted(pending.values()),workers=workers))
                for future in completed:
                    index = pending.pop(future)
                    record = future.result()
                    path = root/'episodes'/f'{index:06}.json.gz'
                    if path.exists(): raise ValueError('Refusing to overwrite episode')
                    atomic_json(path,record,compressed=True); records.append(record)
                    atomic_json(root/'state.json',summary(records,m))
                    print(json.dumps(dict(completed=len(records),target=m['target'])),flush=True)
                    submit()
        atomic_json(root/'state.json',summary(records,m))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['init','run','status'])
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--source',type=Path)
    p.add_argument('--count',type=int,default=200)
    p.add_argument('--workers',type=int,default=4)
    a = p.parse_args(); root = a.run.resolve()
    if a.mode == 'init': initialize(a.source.resolve(),root,a.count)
    elif a.mode == 'run': collect(root,a.workers)
    else: print(json.dumps(read(root/'state.json'),indent=2))


if __name__ == '__main__': main()
