"""Rebuild Gen3 outcome supervision from complete arena continuations.

No IMP differences enter outcome training. Replayed branch prefixes are omitted;
the forced fork card is labeled using its parent's observable search features.
The existing canonical 80/10/10 family partition is preserved.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time

for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.auction_policy import public_extra
from bridge_harness.policy_selector import encode, INPUT_KEYS
from bridge_harness.training import input_tensors, digest
from bridge_harness.bidding_env import deal_key
from bridge_harness.core import Board, Game, card
from bridge_harness.loop_registry import sha
from bridge_harness.selfplay import atomic_json
from scripts.policy_choice_data import family_split, validate_event, scores, weights


def encode_many(observations, details):
    arrays = {k: np.stack([d[k] for d in observations]) for k in INPUT_KEYS}
    policy = np.zeros((len(details), 52), np.float32)
    utility = np.zeros_like(policy)
    for i, d in enumerate(details):
        proposal = d.get('proposal_probabilities', d.get('behavior_probabilities', {}))
        active = [card(c) for c, p in proposal.items() if p > 0]
        policy[i, active] = 1 / len(active)
        for c, e in d['estimates'].items():
            utility[i, card(c)] = e['utility']
    return encode(arrays, policy, utility)


def extract(runs, out, parent3, parent4, positions=16):
    if out.exists():
        raise ValueError('Dataset must be frozen into a new directory')
    out.mkdir(parents=True)
    manifests = [json.loads((p/'manifest.json').read_text()) for p in runs]
    for m in manifests:
        if digest({k:v for k,v in m.items() if k != 'identity'}) != m['identity']:
            raise ValueError('Source manifest changed')
    files = [dict(source=i, path=str(p.resolve())) for i,run in enumerate(runs)
             for p in sorted((run/'episodes').glob('*.json.gz'))]
    atomic_json(out/'snapshot.json', dict(runs=[str(p) for p in runs], manifests=manifests,
                files=files, frozen_epoch=time.time(), positions_per_tail=positions))
    model3, model4 = weights(parent3), weights(parent4)
    model4_sha = sha(parent4)
    buffers = defaultdict(list)
    shards = []
    counts = Counter()
    families = []
    seen_families = set()
    start = time.time()

    def flush(kind, split):
        rows = buffers[kind, split]
        if not rows:
            return
        data = {k:np.stack([r[k] for r in rows]) for k in rows[0]}
        path = out/f'{kind}-{split}-{len(shards):05d}.npz'
        np.savez_compressed(path, **data)
        shards.append(dict(kind=kind, split=split, file=path.name, rows=len(rows), sha256=sha(path)))
        counts[kind+'_'+split+'_rows'] += len(rows)
        rows.clear()

    for number, src in enumerate(files):
        raw = Path(src['path']).read_bytes()
        src['sha256'] = hashlib.sha256(raw).hexdigest()
        r = json.loads(gzip.decompress(raw))
        manifest = manifests[src['source']]
        if r['manifest_identity'] != manifest['identity']:
            raise ValueError('Wrong manifest')
        family = r['family']
        if family in seen_families:
            raise ValueError('Duplicate source family')
        seen_families.add(family)
        split = family_split(family)
        if (r['split'] == 'validation') != (split != 'train'):
            raise ValueError('Existing family split changed')
        current4 = manifest['bots'][r['candidate']]['artifact_sha256'].get('policy') == model4_sha
        outcome_rows, pair_rows = [], []
        family_counts = Counter()
        trajectories = set()
        for room, episode in r['unique_tables'].items():
            if episode.get('schema_version') == 'v4-passed-out-v1':
                family_counts['passed_out_rooms'] += 1
                continue
            board = Board.from_dict(episode['board'])
            if deal_key(board.hands, True) != family or episode['versions'] != r['versions']:
                raise ValueError('Wrong nested deal/version identity')
            forced = {}
            audits = defaultdict(list)
            for event in episode['audits']:
                if event['identical_action']:
                    if event['candidate_card'] != event['reference_card'] or event['gain_imps'] != 0:
                        raise ValueError('Invalid identical move event')
                    continue
                parent = validate_event(episode, event)
                forced[event['reference_table'], event['ply']] = parent
                audits[event['candidate_table'], event['ply']].append(event)
            obs, detail, extra, metadata = [], [], [], []
            for ti, table in enumerate(episode['tables']):
                # Identical trajectories from the same frozen room count once.
                tk = digest([board.to_dict(), episode['seed'],
                             [(a['card'], a.get('estimates'), a.get('proposal_probabilities'))
                              for a in table['actions']]])
                if tk in trajectories:
                    family_counts['duplicate_trajectories'] += 1
                    continue
                trajectories.add(tk)
                eligible = []
                for ply, a in enumerate(table['actions']):
                    if a.get('replayed_prefix'):
                        continue
                    d = forced.get((ti, ply), a)
                    proposal = d.get('proposal_probabilities',d.get('behavior_probabilities',{}))
                    if d.get('estimates') and sum(v>0 for v in proposal.values()) >= 2:
                        eligible.append(ply)
                mandatory = {ply for ply in eligible if (ti, ply) in forced}
                remaining = [ply for ply in eligible if ply not in mandatory]
                rng = np.random.default_rng(int(tk[:16],16))
                take = mandatory | set(rng.choice(remaining, min(max(positions-len(mandatory),0),len(remaining)),replace=False).tolist())
                game = Game(board)
                for ply, action in enumerate(table['actions']):
                    o = game.observation()
                    events = audits.get((ti,ply), [])
                    if ply in take or events:
                        d = forced.get((ti,ply), action)
                        obs.append({k:v for k,v in input_tensors(asdict(o)).items() if k in INPUT_KEYS})
                        detail.append(d)
                        extra.append(public_extra(o,d.get('samples',32),d.get('near_tie',.125),False))
                        decl = o.actor%2 == o.contract.declarer%2
                        final = table['declarer_tricks'] if decl else 13-table['declarer_tricks']
                        already = o.declarer_tricks if decl else len(o.history)//4-o.declarer_tricks
                        metadata.append(dict(take=ply in take, chosen=card(action['card']), y=final-already,
                            events=events, depth=table['depth'], forced=(ti,ply) in forced, actor_decl=decl, ply=ply))
                    if action['seat'] != 'NESW'[o.actor]:
                        raise ValueError('Replay seat mismatch')
                    game.play(card(action['card']))
                if not game.done or game.ns_score()!=table['ns_score'] or game.declarer_tricks!=table['declarer_tricks']:
                    raise ValueError('Continuation failed legal/score replay')
                family_counts['trajectories'] += 1
                family_counts['eligible_new_decisions'] += len(eligible)
            # Bound transient expansion while vectorizing the expensive encoding.
            for offset in range(0,len(obs),256):
                x, cards = encode_many(obs[offset:offset+256], detail[offset:offset+256])
                ext = extra[offset:offset+256]
                x['state'] = np.concatenate([x['state'], np.stack([e[2] for e in ext])],axis=1)
                x['calls'] = np.stack([e[0] for e in ext])
                x['seats'] = np.stack([e[1] for e in ext])
                for j, meta in enumerate(metadata[offset:offset+256]):
                    valid = x['mask'][j]>0
                    chosen = np.flatnonzero(valid & (cards[j]==meta['chosen']))
                    if len(chosen)!=1:
                        raise ValueError('Played/forced move outside original search support')
                    if meta['take']:
                        row={k:v[j] for k,v in x.items()}
                        row['actions']=row['actions'].astype(np.int8)
                        row.update(chosen=np.int8(chosen[0]), y=np.float32(meta['y']), group=family,
                            depth=np.int8(meta['depth']), forced=np.int8(meta['forced']),
                            actor_decl=np.int8(meta['actor_decl']), source=np.int8(src['source']), ply=np.int8(meta['ply']))
                        outcome_rows.append(row)
                        family_counts['forced_outcome_rows' if meta['forced'] else 'ordinary_outcome_rows']+=1
                    for event in meta['events']:
                        indices=[int(np.flatnonzero(valid&(cards[j]==card(event[k])))[0])
                                 for k in ('candidate_card','reference_card')]
                        row={k:v[j] for k,v in x.items() if k not in ('actions','q','mask')}
                        row.update(actions=x['actions'][j,indices].astype(np.int8), q=x['q'][j,indices],
                            y=np.float32(event['gain_imps']), group=family, depth=np.int8(event['depth']),
                            current_policy=np.int8(current4), source=np.int8(src['source']),
                            pair=r['pair'], index=np.int32(r['index']))
                        pair_rows.append(row)
        for row in outcome_rows:
            row['weight']=np.float32(1/len(outcome_rows))
            buffers['outcomes',split].append(row)
        if pair_rows:
            data={k:np.stack([r[k] for r in pair_rows]) for k in pair_rows[0]}
            for label, model in [('gen3',model3),('gen4',model4)]:
                pred=scores(model,data,label)
                for row, contrast in zip(pair_rows,pred[:,0]-pred[:,1]):
                    row[label+'_contrast']=np.float32(contrast)
            buffers['pairs',split].extend(pair_rows)
        counts.update(family_counts)
        families.append(dict(family=family, split=split, source=src['source'], index=r['index'],
                        outcome_rows=len(outcome_rows), pairs=len(pair_rows), **family_counts))
        for kind in ('outcomes','pairs'):
            if len(buffers[kind,split])>=2048:
                flush(kind,split)
        if (number+1)%100==0:
            progress=dict(files=number+1,total=len(files),counts=dict(counts),seconds=time.time()-start)
            atomic_json(out/'progress.json',progress)
            print(json.dumps(progress),flush=True)
    for kind in ('outcomes','pairs'):
        for split in ('train','validation','test'):
            flush(kind,split)
    atomic_json(out/'sources.json',files)
    atomic_json(out/'families.json',families)
    result=dict(schema='arena-individual-outcomes-v1', validated=True, shards=shards,counts=dict(counts),
        families=dict(Counter(f['split'] for f in families)), total_families=len(families),
        source_sha256=sha(out/'sources.json'), snapshot_sha256=sha(out/'snapshot.json'),
        parent_sha256=sha(parent3), comparator_sha256=sha(parent4), seconds=time.time()-start,
        target='Actual remaining acting-partnership tricks of chosen card, including forced cards; no IMP loss',
        weighting='Equal total weight per canonical family; up to 16 newly executed eligible decisions per trajectory, always including the forced move',
        split_rule='Canonical hash modulo 10: 0 test, 5 validation, others train; unchanged original 80/20 holdout',
        continuation='Observed frozen mixed-bot policies; no claim of optimal continuation',
        inputs='Player-visible information and pre-action PIMC estimates only; no hidden cards, future actions, outcomes, identifiers')
    atomic_json(out/'dataset.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='shards'}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,action='append',required=True)
    for key in ('out','gen3','gen4'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--positions',type=int,default=16)
    a=p.parse_args()
    extract(a.run,a.out,a.gen3,a.gen4,a.positions)
