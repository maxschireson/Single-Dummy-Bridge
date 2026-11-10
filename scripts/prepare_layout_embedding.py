"""Join exact DDS captures to clean public trajectories and freeze family splits."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys
import time
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.core import Board, Game, card

CLEAN = {'1', '2', '3', '3early', '3.5', '4b', 'Q'}
BAD = 'e179a71ed132dcd0f9ca06b486ec087e9f5b26edb4210e99ed2e04c9439b21ed'


def save(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n'); temp.replace(path)


def signature(family, trump, leader, partial, fixed, known, universe):
    return (family, trump, leader, tuple(partial), tuple(fixed),
            tuple(tuple(h) for h in known), tuple(universe))


def capture_key(d):
    p = d['positions'][0]; fixed = d['fixed_seats']
    partial = [13*s+r-2 for s, r in zip(p['trick_suits'], p['trick_ranks']) if r]
    return signature(d['context']['family'], p['trump'], p['leader'], partial, fixed,
                     [p['hands'][s] for s in fixed],
                     [sum(h[s] for h in p['hands']) for s in range(4)])


def masks(hands):
    return [[sum(1 << (c % 13 + 2) for c in h if c//13 == s) for s in range(4)] for h in hands]


def episode_index(path, family):
    raw = path.read_bytes(); ep = json.loads(gzip.decompress(raw))
    if ep['family'] != family:
        raise ValueError('Episode family mismatch')
    active = {ep.get('candidate'), ep.get('opponent')}
    if not active or not active <= CLEAN:
        return None, None
    found = {}
    for room in ep['unique_tables'].values():
        if room['status'] != 'ok':
            continue
        board = Board.from_dict(room['board'])
        if board.contract is None:
            continue
        for trajectory in room['tables']:
            if trajectory.get('status') != 'ok':
                continue
            game = Game(board)
            for action in trajectory['actions']:
                o = game.observation()
                if len(o.history) >= 16:
                    break
                if len(o.legal) > 1:
                    fixed = [s for s, h in enumerate(o.known_hands) if h is not None]
                    mh = masks(game.hands)
                    key = signature(family, o.contract.trump, o.leader, [c for s, c in o.trick], fixed,
                                    [mh[s] for s in fixed], [sum(h[s] for h in mh) for s in range(4)])
                    # Ambiguous public histories remain separate by choosing one valid
                    # clean history, then checking every admitted layout against its voids.
                    if key not in found:
                        voids = set()
                        for i, (seat, c) in enumerate(o.history):
                            led = o.history[i-i%4][1]//13
                            if c//13 != led:
                                voids.add((seat, led))
                        found[key] = dict(legal=list(o.legal), fixed=fixed, voids=sorted(voids),
                                          board=room['board'], history=[c for s, c in o.history],
                                          actor=o.actor, controller=o.controller, ply=len(o.history),
                                          declarer=o.contract.declarer, level=o.contract.level)
                game.play(card(action['card']))
    return found, hashlib.sha256(raw).hexdigest()


def main():
    p = argparse.ArgumentParser(); p.add_argument('--runs', type=Path, nargs='+', required=True)
    p.add_argument('--split-manifest', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    if (a.out/'dataset.json').exists():
        print((a.out/'dataset.json').read_text(), flush=True); return
    inherited = json.loads(a.split_manifest.read_text())
    splits = {x['family']: x['split'] for x in inherited['normalized_sources']}
    reserved = set(inherited['reserved_families'])
    base_manifest = Path(inherited['base'])/'manifest.json'
    if base_manifest.exists():
        base = json.loads(base_manifest.read_text())
        for e in base.get('families', []):
            splits[e['family']] = e['split']
    groups = {}; counters = Counter(); sources = {}; started = time.time()
    for run in a.runs:
        manifest = json.loads((run/'manifest.json').read_text())
        # Active names are filtered here; their frozen artifact identities are
        # checked against the run manifest before indexing a source episode.
        cache = {}
        for i, path in enumerate(sorted((run/'dds-expensive').glob('*.json.gz'))):
            record = json.loads(gzip.decompress(path.read_bytes())); counters['capture_records'] += 1
            if record['manifest_identity'] != manifest['identity']:
                raise ValueError('Capture manifest mismatch')
            family = record['context']['family']; bucket = int(family[:8], 16) % 10
            split = splits.get(family, 'test' if bucket == 0 else 'validation' if bucket == 5 else 'train')
            if family in reserved or split == 'test':
                counters['reserved_test_records'] += 1; continue
            source = run/'episodes'/f"{record['context']['index']:06d}.json.gz"
            if not source.exists():
                counters['missing_episode'] += 1; continue
            if source not in cache:
                ep = json.loads(gzip.decompress(source.read_bytes()))
                if ep['manifest_identity'] != manifest['identity']:
                    raise ValueError('Episode manifest mismatch')
                active = {ep.get('candidate'), ep.get('opponent')}
                if active <= CLEAN:
                    for who in active:
                        bot = manifest['bots'][who]
                        if ep['versions'][who] != bot['identity'] or bot['artifact_sha256'].get('policy') == BAD:
                            raise ValueError('Active policy identity mismatch')
                cache[source] = episode_index(source, family)
            index, checksum = cache[source]
            if index is None:
                counters['excluded_policy_records'] += 1; continue
            if not record['positions'] or record['call_kind'] != 'batch':
                counters['nonbatch'] += 1; continue
            key = capture_key(record)
            if key not in index:
                counters['no_matching_early_clean_observation'] += 1; continue
            context = index[key]; gid = hashlib.sha256(repr(key).encode()).hexdigest()
            g = groups.setdefault(gid, dict(family=family, split=split, context=context, worlds={}))
            legal = set(context['legal'])
            for pos, result in zip(record['positions'], record['results']):
                if any(pos['hands'][s][suit] for s, suit in context['voids']):
                    counters['incompatible_history_worlds'] += 1; continue
                y = {int(c): int(v) for c, v in result['scores'].items()}
                if set(y) != legal:
                    raise ValueError('All-legal-move label mismatch')
                partial = [13*s+r-2 if r else 255 for s, r in zip(pos['trick_suits'], pos['trick_ranks'])]
                raw = struct.pack('<BB3B16H', pos['trump'], pos['leader'], *partial,
                                  *(v for hand in pos['hands'] for v in hand))
                scores = np.full(52, -1, np.int8)
                for c, v in y.items():
                    scores[c] = v
                if raw in g['worlds']:
                    if g['worlds'][raw] != scores.tobytes():
                        raise ValueError('Conflicting exact labels')
                    counters['duplicate_worlds_removed'] += 1
                else:
                    g['worlds'][raw] = scores.tobytes()
            sources[str(source)] = checksum
            if i % 1000 == 0:
                save(a.out/'status.json', dict(stage='prepare', counters=dict(counters), groups=len(groups), seconds=time.time()-started))
        print(json.dumps(dict(stage='source_done', run=str(run), counters=dict(counters), groups=len(groups))), flush=True)
    records = []; families = sorted({g['family'] for g in groups.values()}); fi = {f:i for i,f in enumerate(families)}
    summary = {}; contexts = []
    for split in ('train', 'validation'):
        raws=[]; scores=[]; fixed=[]; starts=[0]; fam=[]; ids=[]
        for gid, g in sorted(groups.items()):
            if g['split'] != split or len(g['worlds']) < 8:
                continue
            # Stable hash order avoids capture-time artifacts and allows nested subsets.
            items = sorted(g['worlds'].items(), key=lambda kv:hashlib.sha256(kv[0]).digest())
            raws.extend(np.frombuffer(k, np.uint8) for k,v in items)
            scores.extend(np.frombuffer(v, np.int8) for k,v in items)
            f=np.zeros(4,np.uint8);f[g['context']['fixed']]=1;fixed.append(f)
            starts.append(len(raws));fam.append(fi[g['family']]);ids.append(gid)
            contexts.append(dict(id=gid, family=g['family'], split=split, **g['context']))
        if not raws:
            raise ValueError(f'No {split} rows after clean matching')
        target=a.out/f'{split}.npz'
        np.savez_compressed(target, raw=np.stack(raws), scores=np.stack(scores), fixed=np.stack(fixed),
                            starts=np.array(starts,np.int64), family=np.array(fam,np.int32), group=np.array(ids))
        summary[split]=dict(groups=len(ids), worlds=len(raws), families=len(set(fam)),sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    with gzip.open(a.out/'contexts.json.gz','wt') as f:json.dump(contexts,f,separators=(',',':'))
    save(a.out/'sources.json',dict(episodes=sources,families=families,split_manifest=str(a.split_manifest),
                                 split_manifest_sha256=hashlib.sha256(a.split_manifest.read_bytes()).hexdigest()))
    result=dict(schema='layout-embedding-data-v1',summary=summary,counters=dict(counters),seconds=time.time()-started,
                exclusions='Any episode with active v4/v4p or unknown bot name; test families never prepared.',
                scope='10-13 remaining tricks; exact all-move labels; clean root/fork public trajectories.',
                limitations=['Expensive-native-call selection bias; cached hits are absent.',
                             'Deduplicated layout weights are NOT posterior probabilities.',
                             'Grouping preserves one compatible public history; histories can differ across calls.',
                             'No unprovenanced 600k cache pretraining; preserves deal-level holdouts.'])
    save(a.out/'dataset.json',result);print(json.dumps(result),flush=True)


if __name__ == '__main__':main()
