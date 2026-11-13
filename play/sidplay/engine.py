"""Sid inside a worker process: calls, cards, double-dummy claim checks and Sid's own table on a deal.

Every function here runs in a pool process started with `init_worker`. The web process never imports
TensorFlow. A bot only ever receives what bridge_harness.core.Game.observation() gives the seat that
controls the card (its own hand, dummy after the lead, the auction and the play); the bidder gets one
seat's hand and the calls. The full deal crosses into a worker only for the claim check (the referee,
not a player) and for Sid's own table, where every seat is Sid.

Players are built once per process and reused. Two instances: one that faces humans (the bot's
`opponent_play_weight` setting for an unknown opponent applies) and one that faces Sid. Before each
decision the table's declared systems are bound (`seat_table`), so tables can interleave in a process.
"""
import json
import os
from pathlib import Path
import random
import sys
import time

_S = {}


def init_worker(bundle_dir, nice=0):
    if nice:
        os.nice(nice)
    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
    os.environ['BRIDGE_DDS_CACHE'] = ''          # no persistent position cache: nothing to grow or lock
    bundle = Path(bundle_dir)
    meta = json.loads((bundle / 'bundle.json').read_text())
    source = meta['source']['path']
    if source not in sys.path:
        sys.path.insert(0, source)
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(1)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    from bridge_harness.bidding_ppo import Policy
    spec = meta['spec']
    try:
        from ops.gen5_runtime import player as factory      # knows every engine the bundle's source knows
    except ImportError:
        from bridge_harness.gen7 import player as factory
    players = {}
    for kind in ('human', 'bot'):
        p = factory(spec, str(bundle))
        if hasattr(p, 'meet'):
            p.meet('human' if kind == 'human' else meta['bot'])
        players[kind] = p
    _S.update(meta=meta, bidder=Policy.load(bundle / spec['bidding']), players=players, pid=os.getpid())


def info():
    import resource
    return dict(pid=os.getpid(), bot=_S['meta']['bot'], rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024)


def bid(hand, seat, dealer, vulnerability, calls):
    import numpy as np
    from bridge_harness.bidding_env import CALLS, BidObservation, encode, legal_mask, pack_inputs
    started = time.perf_counter()
    x = encode(BidObservation(tuple(hand), seat, dealer, vulnerability, tuple(calls)))
    mask = legal_mask(dealer, list(calls))
    xs, lengths = pack_inputs([x])
    raw, _ = _S['bidder'].predict(xs, lengths)
    action = int(np.argmax(np.where(mask, raw[0], -np.inf)))
    return CALLS[action], time.perf_counter() - started


def play(observation, kind, systems, seed):
    p = _S['players'][kind]
    if hasattr(p, 'seat_table'):
        p.seat_table(systems)
    started = time.perf_counter()
    decision = p.choose(observation, random.Random(seed))
    if decision.card not in observation.legal:
        raise RuntimeError('Bot chose an illegal card')
    return decision.card, time.perf_counter() - started


def side_tricks(hands, trump, leader, trick, side):
    """Double-dummy tricks `side` (0 = NS, 1 = EW) takes from here on, the current trick included."""
    from bridge_harness.dds import DDS
    if 'dds' not in _S:
        _S['dds'] = DDS(cache_path='')
    values, _ = _S['dds'].solve([tuple(h) for h in hands], trump, leader, [tuple(t) for t in trick])
    remaining = (sum(len(h) for h in hands) + len(trick)) // 4
    on_move = (leader + len(trick)) % 4
    best = max(values.values())
    return best if on_move % 2 == side else remaining - best


def sid_table(hands, dealer, vulnerability, board_id, seed, systems):
    """Sid at all four seats on this deal: the auction, then the play. Returns the record."""
    from bridge_harness.core import SEATS, Board, Game, auction_contract, symbol
    started = time.perf_counter()
    calls = []
    while True:
        call, _ = bid(hands[(dealer + len(calls)) % 4], (dealer + len(calls)) % 4, dealer, vulnerability, calls)
        calls.append(call)
        try:
            contract = auction_contract(dealer, calls)
            break
        except ValueError as e:
            if str(e) != 'Incomplete auction':
                raise
    if contract is None:
        return dict(calls=calls, contract=None, declarer=None, tricks=None, ns_score=0, play=[],
                    seconds=time.perf_counter() - started)
    board = Board(str(board_id), tuple(tuple(h) for h in hands), contract, dealer, vulnerability, tuple(calls),
                  auction_source='sid')
    game = Game(board)
    p = _S['players']['bot']
    if hasattr(p, 'seat_table'):
        p.seat_table(systems)
    rng = random.Random(seed)
    while not game.done:
        o = game.observation()
        game.play(p.choose(o, random.Random(rng.getrandbits(64))).card)
    return dict(calls=calls, contract=contract.text(), declarer=SEATS[contract.declarer], tricks=game.declarer_tricks,
                ns_score=game.ns_score(), play=[[SEATS[s], symbol(c)] for s, c in game.history],
                seconds=time.perf_counter() - started)
