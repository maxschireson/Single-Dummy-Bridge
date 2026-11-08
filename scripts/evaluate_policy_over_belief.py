#!/usr/bin/env python3
"""Frozen policy increment over frozen belief-informed PIMC, on fresh auctions."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bridge_harness.bidding_sampling import AuctionWeights, WeightedSampler
from bridge_harness.core import Board, Game, SEATS, auction_contract, card, imps, symbol
from bridge_harness.corpus import load, save
from bridge_harness.players import PIMCPlayer, Decision
from bridge_harness.policy_selector import SelectorPlayer, SelectorWeights
from bridge_harness.report import summarize, trick_difference
from bridge_harness.runner import decision_rng, play_table, replay
from bridge_harness.training import digest

CANDIDATE = 'belief-policy32'
BASELINE = 'belief32'
ASSIGNMENTS = [[CANDIDATE, BASELINE, CANDIDATE, BASELINE],
               [BASELINE, CANDIDATE, BASELINE, CANDIDATE]]
BELIEF_HASH = 'c070981c21cc79eed2205b5dbe6693e5804641a05d7ce32948df10bf15a1e96a'
POLICY_HASH = '02b6885e8f07da473970052d7f9ea9dc2a10fa34505ad60186e4a14d02218c60'
SETTINGS = dict(mode='partnership', candidate=CANDIDATE, baseline=BASELINE,
                samples=32, objective='tricks', batch=True, near_tie=.125,
                strength=1., seed=20261502, belief_sha256=BELIEF_HASH,
                policy_sha256=POLICY_HASH, rng_namespace='belief32-shared')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CoupledBeliefPlayer:
    """Both players use the same frozen belief and common-world random stream."""
    def __init__(self, player, belief, board_id, seed):
        self.player, self.belief = player, belief
        self.board_id, self.seed = board_id, seed
        self.worlds = []

        def factory(observation):
            sampler = WeightedSampler(observation, belief.logits(observation), 1.)
            owner = self

            class TracedSampler:
                def draw(self, rng):
                    world = sampler.draw(rng)
                    owner.worlds.append(world)
                    return world
            return TracedSampler()

        self.player.sampler_factory = factory

    def choose(self, observation, ignored):
        self.worlds = []
        rng = decision_rng(self.seed, self.board_id, SETTINGS['rng_namespace'], observation)
        result = self.player.choose(observation, rng)
        assert len(self.worlds) == (0 if result.details.get('forced') else 32)
        details = dict(result.details, belief_sha256=BELIEF_HASH,
                       sampler='auction-weighted-dp', strength=1.,
                       sampled_worlds_sha256=hashlib.sha256(
                           json.dumps(self.worlds, separators=(',', ':')).encode()).hexdigest())
        return Decision(result.card, details)

    def close(self):
        self.player.close()


def make_players(belief_path, policy_path, board_id, seed):
    belief = AuctionWeights(belief_path)
    return {
        CANDIDATE: CoupledBeliefPlayer(SelectorPlayer(policy_path), belief, board_id, seed),
        BASELINE: CoupledBeliefPlayer(PIMCPlayer(32, 'tricks', True, .125), belief, board_id, seed),
    }


def pair(job):
    data, belief_path, policy_path = job
    board = Board.from_dict(data)
    players = make_players(belief_path, policy_path, board.id, SETTINGS['seed'])
    record = dict(schema_version=1, board=data, config=SETTINGS,
                  assignments=ASSIGNMENTS, tables=[], status='error')
    try:
        for assignment in ASSIGNMENTS:
            record['tables'].append(play_table(board, assignment, players, SETTINGS['seed']))
        if all(t['status'] == 'ok' for t in record['tables']):
            a, b = record['tables']
            record.update(status='ok', score_difference=a['ns_score'] - b['ns_score'])
            record['imps'] = imps(record['score_difference'])
            record['first_difference'] = next((i for i, (x, y) in enumerate(zip(a['actions'], b['actions']))
                                               if x['card'] != y['card']), None)
            replay(record)
        return record
    finally:
        for player in players.values():
            player.close()


def prepare(root, count):
    assert sha(root/'belief_weights.npz') == BELIEF_HASH
    assert sha(root/'policy_weights.npz') == POLICY_HASH
    manifest = json.loads((root/'auctions/manifest.json').read_text())
    boards = sorted(load(root/'auctions/frozen.jsonl'), key=lambda b: int(b.id.rsplit('-', 1)[1]))
    assert manifest['seed'] == 20261501 and len(boards) == 1024
    assert manifest['search'] is False and manifest['dds_calls'] == 0
    excluded = set(json.loads((root/'exclusions.json').read_text())['deal_ids'])
    ids = [digest(b.hands) for b in boards]
    assert len(set(ids)) == 1024 and not set(ids).intersection(excluded)
    for b in boards:
        assert auction_contract(b.dealer, b.auction) == b.contract
        assert b.opening_lead is None and b.auction_source == 'BEN-neural-only-batched'
    selected = [b for b in boards if b.contract is not None][:count]
    assert len(selected) == count
    protocol = dict(question='Does the frozen policy selector add to the frozen belief sampler?',
        count=count, deal_seed=20261501, generated_deals=1024,
        generated_passed_out=sum(b.contract is None for b in boards),
        selection='first 1000 non-passed-out deals in generation order; fixed before card play',
        primary='candidate-oriented paired tricks per original deal', secondary='paired IMPs per original deal',
        uncertainty='95% original-deal bootstrap; fixed 1000-deal horizon; no interim outcome-based stopping',
        settings=SETTINGS, play_deal_ids=[digest(b.hands) for b in selected],
        generated_deal_ids=ids, exclusions_sha256=sha(root/'exclusions.json'),
        auction_manifest_sha256=sha(root/'auctions/manifest.json'),
        source_commit=((ROOT/'SOURCE_COMMIT').read_text().strip() if (ROOT/'SOURCE_COMMIT').exists()
                       else subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()),
        evaluator_sha256=sha(__file__),
        scope='no retraining or model selection; both sides get belief; only candidate gets policy',
        training='evaluation-only fresh corpus, excluded from future training',
        created_unix=time.time())
    with (root/'protocol.json').open('x') as f:
        json.dump(protocol, f, indent=2)
    save(selected, root/'play-corpus.jsonl')
    print(json.dumps({k: protocol[k] for k in ('count', 'generated_deals', 'generated_passed_out')}), flush=True)


def read_run(root):
    protocol = json.loads((root/'protocol.json').read_text())
    assert protocol['settings'] == SETTINGS
    assert sha(root/'belief_weights.npz') == BELIEF_HASH
    assert sha(root/'policy_weights.npz') == POLICY_HASH
    assert sha(root/'exclusions.json') == protocol['exclusions_sha256']
    boards = load(root/'play-corpus.jsonl')
    assert [digest(b.hands) for b in boards] == protocol['play_deal_ids']
    return protocol, boards


def play(root, workers):
    protocol, boards = read_run(root)
    records, jobs = [], []
    (root/'episodes').mkdir(exist_ok=True)
    (root/'failures').mkdir(exist_ok=True)
    for b in boards:
        path = root/'episodes'/f'{digest(b.hands)}.json.gz'
        if path.exists():
            with gzip.open(path, 'rt') as f:
                r = json.load(f)
            assert r['status'] == 'ok' and r['config'] == SETTINGS and r['board'] == b.to_dict()
            replay(r)
            records.append(r)
        else:
            jobs.append((b.to_dict(), str(root/'belief_weights.npz'), str(root/'policy_weights.npz')))
    started = time.perf_counter()
    with (root/'invocations.jsonl').open('a') as f:
        f.write(json.dumps(dict(started_unix=time.time(), workers=workers, resumed_pairs=len(records),
                               evaluator_sha256=sha(__file__)))+'\n')
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(pair, job) for job in jobs]):
            r = future.result()
            did = digest(Board.from_dict(r['board']).hands)
            path = root/('episodes' if r['status'] == 'ok' else 'failures')/f'{did}.json.gz'
            if path.exists():
                raise ValueError('Refusing to overwrite an attempt')
            temp = path.with_suffix('.tmp')
            with gzip.open(temp, 'wt') as f:
                json.dump(r, f)
            temp.replace(path)
            records.append(r)
            if len(records) % 25 == 0:
                print(json.dumps(dict(pairs=len(records), seconds=time.perf_counter()-started)), flush=True)
    result = summarize(sorted(records, key=lambda r: digest(Board.from_dict(r['board']).hands)))
    result['wall_seconds_this_invocation'] = time.perf_counter()-started
    result['expected_pairs'] = protocol['count']
    (root/'play-summary.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)


def audit(root):
    protocol, boards = read_run(root)
    selector = SelectorWeights(root/'policy_weights.npz')
    excluded = set(json.loads((root/'exclusions.json').read_text())['deal_ids'])
    counts = dict(independent_deals=0, complete_games=0, plies=0, nonforced=0,
                  policy_decisions=0, policy_below_pimc_best=0, common_positions=0,
                  selector_changes_at_first_divergence=0)
    records = []
    for b in boards:
        did = digest(b.hands)
        assert did not in excluded
        with gzip.open(root/'episodes'/f'{did}.json.gz', 'rt') as f:
            r = json.load(f)
        assert r['status'] == 'ok' and r['board'] == b.to_dict()
        assert r['config'] == SETTINGS and r['assignments'] == ASSIGNMENTS
        assert all(t['complete'] and t['plies'] == 52 for t in replay(r))
        assert r['score_difference'] == r['tables'][0]['ns_score']-r['tables'][1]['ns_score']
        assert r['imps'] == imps(r['score_difference'])
        history_estimates = {}
        for index, table in enumerate(r['tables']):
            game = Game(b)
            for a in table['actions']:
                o = game.observation()
                assert a['player'] == ASSIGNMENTS[index][o.controller]
                assert a['seat'] == SEATS[o.actor] and a['controller'] == SEATS[o.controller]
                assert a['belief_sha256'] == BELIEF_HASH and a['sampler'] == 'auction-weighted-dp'
                assert a['strength'] == 1.
                if len(o.legal) == 1:
                    assert a['forced'] and a['samples'] == a['dds_calls'] == 0
                else:
                    counts['nonforced'] += 1
                    assert a['samples'] == a['dds_calls'] == 32 and a['batch'] is True
                    assert a['near_tie'] == .125 and a['objective'] == 'tricks'
                    assert not a.get('fixed_opening_lead') and not a.get('replayed_prefix')
                    assert set(a['estimates']) == {symbol(c) for c in o.legal}
                    support = a.get('proposal_probabilities', a['behavior_probabilities'])
                    eligible = [c for c,v in a['estimates'].items() if v['gap_to_best'] <= .125+1e-9]
                    assert {c for c,p in support.items() if p > 0} == set(eligible)
                    assert all(abs(support[c]-1/len(eligible)) < 1e-8 for c in eligible)
                    assert a['card'] in eligible and a['selected_pimc_gap'] <= .125+1e-9
                    key = (o.controller, o.history)
                    signature = (a['sampled_worlds_sha256'], a['estimates'])
                    if key in history_estimates:
                        assert signature == history_estimates[key]
                        counts['common_positions'] += 1
                    else:
                        history_estimates[key] = signature
                    if a.get('selector'):
                        assert a['player'] == CANDIDATE and len(eligible) > 1
                        import random
                        _, predictions = selector.choose(o, dict(a, behavior_probabilities=support), random.Random(0))
                        logged = {card(c):v for c,v in a['selector_predictions'].items()}
                        assert predictions == logged
                        assert max(predictions.values())-predictions[card(a['card'])] <= 1e-7
                        counts['policy_decisions'] += 1
                        counts['policy_below_pimc_best'] += a['selected_pimc_gap'] > 0
                    else:
                        assert a['player'] == BASELINE or len(eligible) == 1
                    assert a['behavior_probabilities'][a['card']] > 0
                    assert abs(sum(a['behavior_probabilities'].values())-1.) < 1e-8
                game.play(card(a['card']))
                counts['plies'] += 1
        first = next((i for i,(x,y) in enumerate(zip(r['tables'][0]['actions'],r['tables'][1]['actions']))
                      if x['card'] != y['card']), None)
        assert first == r['first_difference']
        if first is not None:
            actions = [t['actions'][first] for t in r['tables']]
            assert any(a.get('selector') for a in actions)
            assert actions[0]['sampled_worlds_sha256'] == actions[1]['sampled_worlds_sha256']
            counts['selector_changes_at_first_divergence'] += 1
        counts['independent_deals'] += 1
        counts['complete_games'] += 2
        records.append(r)
    assert counts['independent_deals'] == protocol['count'] == len(set(protocol['play_deal_ids']))
    counts['dds_world_solves'] = 32*counts['nonforced']
    counts['failed_attempts'] = len(list((root/'failures').glob('*.json.gz')))
    counts['excluded_original_deals'] = len(excluded)
    counts['zero_overlap_with_exclusions'] = True
    counts['passed_out_source_deals'] = protocol['generated_passed_out']
    summary = summarize(sorted(records, key=lambda r:digest(Board.from_dict(r['board']).hands)))
    old = json.loads((root/'play-summary.json').read_text())
    for key in ('completed_pairs','mean_imps','mean_tricks','tricks_cluster_bootstrap_95_interval','cluster_bootstrap_95_interval'):
        assert old[key] == summary[key]
    (root/'audit.json').write_text(json.dumps(counts, indent=2))
    print(json.dumps(counts, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--mode', choices=('prepare', 'play', 'audit'), required=True)
    parser.add_argument('--count', type=int, default=1000)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    root = args.run.resolve()
    if args.mode == 'prepare': prepare(root, args.count)
    elif args.mode == 'play': play(root, args.workers)
    else: audit(root)


if __name__ == '__main__':
    main()
