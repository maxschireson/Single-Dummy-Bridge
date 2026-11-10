"""Audit a pinned compact full-play export and extend the exact-auction pool."""
import argparse
from collections import Counter
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.bidding_refresh import (board_key, clean_actors, digest, play_split, sha)
from bridge_harness.bidding_env import deal_key
from bridge_harness.bidding_loop import atomic_json
from bridge_harness.core import Board, auction_contract
from bridge_harness.runner import replay


def verify_blob(path, expected):
    raw = path.read_bytes()
    for content in (raw, raw[:-1] if raw.endswith(b'\n') else raw):
        actual = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
        if actual == expected:
            return json.loads(content)
    raise ValueError('Git blob integrity failure: ' + str(path))


def collect_ids(value, result):
    if isinstance(value, str) and len(value) == 64:
        result.add(value)
    elif isinstance(value, dict):
        for k, v in value.items():
            collect_ids(k, result)
            collect_ids(v, result)
    elif isinstance(value, list):
        for v in value:
            collect_ids(v, result)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('input', 'base', 'out'):
        p.add_argument('--' + key, type=Path, required=True)
    p.add_argument('--reserved', type=Path, action='append', default=[])
    p.add_argument('--raw-audit', type=Path)
    a = p.parse_args()
    snap = json.loads((a.input/'snapshot.json').read_text())
    tree = {e['path']: e for e in snap['tree'] if e['type'] == 'blob'}
    manifest = verify_blob(a.input/'manifest.json', tree['recovery/manifest.json']['sha'])
    if digest({k:v for k,v in manifest.items() if k != 'identity'}) != manifest['identity']:
        raise ValueError('Arena identity mismatch')
    summary = json.loads((a.base/'summary.json').read_text())
    if sha(a.base/'dataset.json') != summary['dataset_sha256']:
        raise ValueError('Prior dataset changed')
    base = json.loads((a.base/'dataset.json').read_text())
    reserved = set()
    for path in a.reserved:
        collect_ids(json.loads(path.read_text()), reserved)
    counts = Counter()
    # Existing held-out rows stay held out; explicitly reserved training rows are removed.
    rows = [r for r in base if not (r['split'] == 'train' and r['family'] in reserved)]
    counts['historical_reserved_training_rows_removed'] = len(base) - len(rows)
    old_families = {r['family'] for r in base}
    old_train = {r['family'] for r in base if r['split'] == 'train'}
    old_split = {r['family']:r['split'] for r in base}
    byboard = {board_key(Board.from_dict(r['board'])):r for r in rows if r['source']=='play'}
    seen = set()
    new_families = set()
    source_rows = []
    new_test = []
    record_ids = set()
    raw_receipts = {}
    if a.raw_audit:
        raw_receipts = {r['index']:r for r in json.loads((a.raw_audit/'download-verified-receipts.json').read_text())}
    for path in sorted(a.input.glob('arena/replays/data/*/boards-*.json')):
        relative = str(path.relative_to(a.input))
        records = verify_blob(path, tree[relative]['sha'])
        for record in records.values():
            index = record['index']
            if index in record_ids:
                raise ValueError('Repeated episode index')
            record_ids.add(index)
            board = Board.from_dict(record['board'])
            family = deal_key(board.hands, True)
            if family != record['family']:
                raise ValueError('Canonical family mismatch')
            split = play_split(family)
            if family in old_split and old_split[family] != split:
                if family in old_train:
                    counts['incoming_pretrained_holdout_removed'] += 1
                    continue
                raise ValueError('Historical family partition changed')
            if family in reserved:
                counts['incoming_reserved_families_removed'] += 1
                continue
            raw_signatures = None
            if index in raw_receipts:
                raw_path = a.raw_audit/'episodes'/f'{index:06d}.json.gz'
                if sha(raw_path) != record['episode_sha256'] or sha(raw_path) != raw_receipts[index]['episode_sha256']:
                    raise ValueError('Raw receipt mismatch')
                raw = json.loads(gzip.decompress(raw_path.read_bytes()))
                if raw['family'] != family or raw['manifest_identity'] != manifest['identity']:
                    raise ValueError('Raw identity mismatch')
                mapping = {'candidate':raw['candidate'], 'opponent':raw['opponent']}
                raw_signatures = set()
                for game in raw['unique_tables'].values():
                    b = Board.from_dict(game['board']); t = game['tables'][0]
                    raw_signatures.add(digest([board_key(b), b.auction,
                        [mapping[x] for x in game['assignments']],
                        [(x['seat'],x['card']) for x in t['actions']],t.get('declarer_tricks')]))
                counts['raw_episodes_cross_checked'] += 1
            row = None
            episode_seen = set()
            for condition in record['conditions'].values():
                for t in condition['tables']:
                    actors = {name:name for name in t['assignments']}
                    if not clean_actors(manifest, actors):
                        counts['excluded_policy_games'] += 1
                        continue
                    bd = dict(record['board'], auction=t['auction'], contract=t['contract'],
                              declarer=t['declarer'], opening_lead=None)
                    b = Board.from_dict(bd)
                    expected = auction_contract(b.dealer, b.auction)
                    if expected != b.contract:
                        raise ValueError('Auction/contract mismatch')
                    actions = [dict(ply=i,seat=c[0],card=c[1:]) for i,c in enumerate(t['plays'])]
                    if b.contract is None and (actions or t['ns_score'] != 0 or t['declarer_tricks'] not in (None, 0)):
                        raise ValueError('Invalid passed-out table')
                    table = dict(status='ok',actions=actions,ns_score=t['ns_score'],
                                 declarer_tricks=t['declarer_tricks'] if b.contract else 0)
                    try:
                        replay(dict(board=bd,tables=[table]))
                    except ValueError as exc:
                        raise ValueError(f'Index {index}, contract {t["contract"]}, declarer {t["declarer"]}, tricks {t["declarer_tricks"]}, plays {len(actions)}, score {t["ns_score"]}: {exc}') from exc
                    signature = digest([board_key(b),b.auction,t['assignments'],
                                        [(x['seat'],x['card']) for x in actions],t['declarer_tricks']])
                    if raw_signatures is not None and signature not in raw_signatures:
                        raise ValueError('Compact root play differs from raw episode')
                    if signature in episode_seen or signature in seen:
                        counts['duplicate_games_removed'] += 1
                        continue
                    episode_seen.add(signature); seen.add(signature)
                    counts['legally_replayed_unique_games'] += 1
                    key = board_key(b)
                    row = byboard.setdefault(key,dict(board=bd,family=family,split=split,source='play',
                                                     outcomes={},auction_outcomes={},games=0))
                    row['games'] += 1
                    if b.contract:
                        slot = row['auction_outcomes'].setdefault(digest(list(b.auction)),
                            dict(calls=list(b.auction),contract=b.contract.text(),declarer=b.contract.declarer,tricks=[]))
                        slot['tricks'].append(t['declarer_tricks'])
                        row['outcomes'].setdefault(f'{b.contract.trump}/{b.contract.declarer}',[]).append(t['declarer_tricks'])
                    source_rows.append(dict(index=index,family=family,trajectory=signature,split=split,
                        shard=relative,git_blob_sha=tree[relative]['sha'],episode_sha256=record['episode_sha256'],
                        actor_policy_hashes={name:manifest['bots'][name].get('artifact_sha256',{}).get('policy') for name in actors}))
            if row is not None and family not in old_families:
                new_families.add(family)
    if len(record_ids) != len([p for p in tree if p.startswith('recovery/episodes/')]):
        raise ValueError('Compact export has incomplete episode coverage')
    # Keep each oriented board once, and never give it a second DDS sampling ticket.
    play = sorted(byboard.values(),key=lambda r:(r['family'],board_key(Board.from_dict(r['board']))))
    pf = {r['family'] for r in play}
    dds = [r for r in rows if r['source']=='dds' and r['family'] not in pf]
    combined = play + dds
    assignments = {}
    for row in combined:
        if assignments.setdefault(row['family'],row['split']) != row['split']:
            raise ValueError('Family crosses partitions')
    a.out.mkdir(parents=True,exist_ok=True)
    new_test = [r for r in play if r['split']=='test' and r['family'] in new_families]
    # Historical tests were already inspected. Only new families are confirmation.
    fit_data = [dict(r,split='historical_test') if r['split']=='test' and r['family'] not in new_families else r for r in combined]
    atomic_json(a.out/'dataset.json',fit_data)
    atomic_json(a.out/'sources.json',source_rows)
    atomic_json(a.out/'fresh-confirmation-families.json',[r['family'] for r in new_test])
    report = dict(schema='gen6-bidding-data-v1',feed_commit=snap['commit'],feed_branch=snap['branch'],
        compact_full_play_export=True,source_records=len(record_ids),audit=dict(counts),
        base_dataset_sha256=sha(a.base/'dataset.json'),dataset_sha256=sha(a.out/'dataset.json'),
        old_play_families=len({r['family'] for r in base if r['source']=='play'}),
        new_families=len(new_families),new_counts=dict(Counter(r['split'] for r in play if r['family'] in new_families)),
        counts=dict(Counter(r['source']+'/'+r['split'] for r in fit_data)),
        exact_auctions=sum(len(r['auction_outcomes']) for r in play),
        reserved_hashes={str(p):sha(p) for p in a.reserved},
        test_evaluated=False,prior_tests_descriptive_only=True,
        reward_note='Exact full auction only. Unseen auctions use unchanged frozen Gen3/32 fallback. Root games only, as in prior bidding recipe; no counterfactual branches treated as root play.')
    atomic_json(a.out/'summary.json',report)
    print(json.dumps(report,indent=2),flush=True)


if __name__ == '__main__':
    main()
