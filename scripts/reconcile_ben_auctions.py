#!/usr/bin/env python3
"""Reuse auction-blind tricks-PIMC trajectories only with identical strain/declarer.

Original games are immutable. Reconstructed examples have the new public auction,
contract and recalculated duplicate-score targets. Recorded PIMC estimates remain
auction-blind behavior data, not estimates from an auction-conditioned policy.
"""
import argparse
from collections import Counter
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.core import Board, Game, card
from bridge_harness.training import digest, examples_from_record, split_for
from bridge_harness.runner import replay
from bridge_harness.selfplay import atomic_json


def classification(record, board):
    old = Board.from_dict(record['board'])
    if (old.hands, old.dealer, old.vulnerability, old.family) != (board.hands, board.dealer, board.vulnerability, board.family):
        raise ValueError('Original deal/context changed')
    if board.contract is None:
        return 'passed_out'
    if old.contract is None or (old.contract.strain, old.contract.declarer) != (board.contract.strain, board.contract.declarer):
        return 'replay_required'
    cfg = record['config']
    if record['status'] != 'ok' or cfg.get('mode') != 'selfplay' or cfg.get('candidate') != 'pimc' or cfg.get('objective') != 'tricks':
        return 'replay_required'
    if old.opening_lead != board.opening_lead:
        return 'replay_required'
    return 'exact_contract' if old.contract == board.contract else 'same_strain_declarer'


def relabel(episode, board):
    kind = classification(episode['record'], board)
    if kind not in ('exact_contract', 'same_strain_declarer'):
        raise ValueError('Cannot reuse this trajectory')
    replay(episode['record'])
    record = copy.deepcopy(episode['record'])
    record['board'] = board.to_dict()
    record['retrofit'] = dict(source_episode_id=episode['episode_id'],
        source_record_sha256=digest(episode['record']), original_board=episode['record']['board'],
        rule=kind, behavior='original auction-blind PIMC maximizing tricks',
        seconds_note='Recorded action/table times are original, not retrofit elapsed time')
    for table in record['tables']:
        game = Game(board)
        for action in table['actions']:
            game.play(card(action['card']))
        assert game.done and game.declarer_tricks == table['declarer_tricks']
        table['ns_score'] = game.ns_score()
    replay(record)
    eid = digest([episode['episode_id'], board.to_dict(), 'auction-retrofit-v1'])[:24]
    examples = examples_from_record(record, eid)
    for row in examples:
        row['metadata']['retrofit_source_episode_id'] = episode['episode_id']
        row['metadata']['behavior_uses_auction'] = False
    assert {r['metadata']['split'] for r in examples} == {split_for(Board.from_dict(episode['record']['board']))}
    return dict(schema_version=episode['schema_version'], episode_id=eid,
                episode=episode['episode'], record=record, examples=examples)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-index', type=Path, required=True)
    p.add_argument('--auctions', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    index = json.loads(args.source_index.read_text())
    if args.out.exists(): raise ValueError('Refuse overwrite')
    args.out.mkdir(parents=True)
    counts = Counter(); splits = {}; seen = set(); matches = []
    with (args.out/'replay-required.jsonl').open('x') as pending:
        for line in (args.auctions/'frozen.jsonl').read_text().splitlines():
            board = Board.from_dict(json.loads(line)); h = digest(board.hands)
            if h in seen: raise ValueError('Repeated auction deal')
            seen.add(h)
            path = Path(index[h])
            with gzip.open(path, 'rt') as f: e = json.load(f)
            kind = classification(e['record'], board)
            counts[kind] += 1
            splits.setdefault(split_for(board), Counter())[kind] += 1
            old = Board.from_dict(e['record']['board'])
            counts['same_strain_any_declarer'] += bool(board.contract and old.contract and board.contract.strain == old.contract.strain)
            if kind == 'replay_required': pending.write(json.dumps(board.to_dict())+'\n')
            elif kind != 'passed_out':
                new = relabel(e, board)
                new['record']['retrofit']['source_file_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                atomic_json(args.out/'episodes'/(new['episode_id']+'.json.gz'), new, compressed=True)
                matches.append(dict(deal_id=h, source=str(path), episode_id=new['episode_id'], rule=kind))
    if seen != set(index): raise ValueError('Missing original deals')
    summary = dict(deals=len(seen), counts=dict(counts), reusable=len(matches),
        reused_rows=len(matches)*52, splits=splits, passed_out_policy='auction-only; do not fabricate card play',
        selection_warning='Matched subset is selected by contract agreement, not representative of all BEN auctions',
        source_index_sha256=hashlib.sha256(args.source_index.read_bytes()).hexdigest(),
        auction_manifest=json.loads((args.auctions/'manifest.json').read_text()))
    atomic_json(args.out/'summary.json', summary)
    atomic_json(args.out/'matches.json', matches)
    print(json.dumps({k:v for k,v in summary.items() if k!='auction_manifest'}, indent=2))


if __name__ == '__main__': main()
