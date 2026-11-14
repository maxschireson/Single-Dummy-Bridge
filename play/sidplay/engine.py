"""Sid inside a worker process: calls, cards, double-dummy claim checks and Sid's own table on a deal.

Every function here runs in a pool process started with `init_worker`; the web process never imports TensorFlow.

The Sid contract
----------------
A bundle names an entry point, `bundle.json["entry"] = "module:callable"` (default `sidplay.engine:ArenaSid`),
importable from the bundle's source checkout. `callable(bundle_dir: Path, meta: dict)` returns an object with

    bid(hand, seat, dealer, vulnerability, calls, style=None) -> str
        hand: 13 card ints (0-51, bridge_harness.core order); seat, dealer: 0-3 for N E S W;
        vulnerability: 'None' | 'NS' | 'EW' | 'Both'; calls: the calls so far ('PASS', 'X', 'XX', '1C' .. '7N').
        style: the seat's bidding style this board (a persona's, bridge_harness/bid_style.py) or None.
        Returns the next call in the same notation.
    play(observation, facing, systems, rng, style=None) -> int
        observation: bridge_harness.core.Observation for the seat that controls the card (its own hand, dummy
        after the lead, the auction, the play so far; nothing hidden). facing: 'human' or 'sid', who the
        opponents are. systems: (NS, EW) declared system ids or None. rng: a seeded random.Random.
        style: the controlling seat's play style this board ({'play': style, 'near': margin}) or None.
        Returns a card in observation.legal.
    The callable may take a keyword `variable_id`: the identifier its other Sids have (personas on), which it then
    meets them by (bridge_harness/persona.py).

The object is built once per process and called for many tables in turn, so it must not keep table state between
calls that its arguments do not determine. The server checks every call and card for legality. ArenaSid below is
the adapter for any bot the arena runtime can build. A future Sid that the runtime cannot build only needs its own
callable in its source.

What a bot sees: only the Observation (play) or one hand and the calls (bidding). The full deal reaches a worker
only for the claim check (the referee, not a player) and for Sid's own table, where every seat is Sid.
"""
import importlib
import json
import os
from pathlib import Path
import random
import sys
import time

DEFAULT_ENTRY = 'sidplay.engine:ArenaSid'
_S = {}


class ArenaSid:
    """A bot exactly as the arena runtime of the bundle's source builds it: its bidder (a BEN-format net, or a Gen 8
    system bidder named by `bidder`), and its card player from `ops/gen5_runtime.player`, or for an 8X (rollout) spec
    (`engine: gen8x`, e.g. SiD (rollout) Stu) from `bridge_harness.x8_player.player`, as scripts/x8_match.py builds it.

    Two player instances: one facing humans (a Gen 8 bot reads unknown opponents' plays at its
    `opponent_play_weight` '*' factor) and one facing Sid. Before each card the table's declared systems are bound
    (`seat_table`), so tables can interleave in one process."""

    def __init__(self, bundle, meta, variable_id=None):
        bundle, spec = Path(bundle), json.loads(json.dumps(meta['spec']))
        if variable_id:         # the other Sids are this engine with personas: a guaranteed contract is still kept, so their
            claims = (spec.get('x8') or {}).get('claims') or {}         # rollouts may be floored there as for its own kind
            if isinstance(claims.get('opponents'), list) and variable_id not in claims['opponents']:
                claims['opponents'].append(variable_id)
        self.spec = spec
        self.style_salt = random.SystemRandom().getrandbits(32)     # a bidding style's random share is not replayable
        try:
            import tensorflow as tf
            tf.config.threading.set_intra_op_parallelism_threads(1)
            tf.config.threading.set_inter_op_parallelism_threads(1)
        except ImportError:
            pass
        if spec.get('bidder'):
            from bridge_harness.system_bidders import make_bidder
            self.bidder = make_bidder(spec['bidder'], Path(meta['source']['path']))
        else:
            from bridge_harness.bidding_ppo import Policy
            self.bidder = Policy.load(bundle / spec['bidding'])
        try:
            from ops.gen5_runtime import player as factory     # every engine the bundle's source knows
        except ImportError:
            from bridge_harness.gen7 import player as factory
        if spec.get('engine') == 'gen8x':
            from bridge_harness.x8_player import player as factory
        self.players = {}
        for facing in ('human', 'sid'):
            p = factory(spec, str(bundle))
            if hasattr(p, 'meet'):         # the other Sids by their identifier when they are variable (never by persona)
                p.meet('human' if facing == 'human' else variable_id or meta['bot'])
            self.players[facing] = p

    def bid(self, hand, seat, dealer, vulnerability, calls, style=None):
        import numpy as np
        from bridge_harness.bidding_env import CALLS, BidObservation, encode, legal_mask, pack_inputs
        mask = legal_mask(dealer, list(calls))
        if hasattr(self.bidder, 'predict'):
            x = encode(BidObservation(tuple(hand), seat, dealer, vulnerability, tuple(calls)))
            xs, lengths = pack_inputs([x])
            raw, _ = self.bidder.predict(xs, lengths)
            style = style or self.spec.get('bid_style')
            if style:           # a bidding style (a persona's this board, or the spec's): bridge_harness/bid_style.py
                from bridge_harness import bid_style
                u = random.Random(hash((tuple(sorted(hand)), seat, dealer, len(calls), 7919)) ^ self.style_salt)
                return CALLS[bid_style.choose(raw[0], mask, tuple(hand), style, u.random(), u.random())]
            return CALLS[int(np.argmax(np.where(mask, raw[0], -np.inf)))]
        from bridge_harness.bidding_env import CALL_ID
        from bridge_harness.core import normalize_bid
        action = int(self.bidder.call(tuple(hand), seat, dealer, ('None', 'NS', 'EW', 'Both').index(vulnerability),
                                      [CALL_ID[normalize_bid(c)] for c in calls]))
        return CALLS[action] if mask[action] else 'PASS'

    def play(self, observation, facing, systems, rng, style=None):
        p = self.players[facing]
        if hasattr(p, 'seat_table'):
            p.seat_table(systems)
        if style is None:
            return p.choose(observation, rng).card
        p.table_styles = {observation.controller: style}      # the persona of the seat deciding, for this card only
        try:
            return p.choose(observation, rng).card
        finally:
            p.table_styles = {}


def init_worker(bundle_dir, nice=0, variable_id=None):
    if nice:
        os.nice(nice)
    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
    for var in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ.setdefault(var, '1')           # one core a worker on a shared box
    # The claim solver an 8X bot asks (x8_claims.py): the vendored sure-trick binary unless the environment names one.
    os.environ.setdefault('SURE_BIN', str(Path(__file__).resolve().parents[1] / 'native' / 'sure_cpp'))
    os.environ['BRIDGE_DDS_CACHE'] = ''          # no persistent position cache: nothing to grow or lock
    bundle = Path(bundle_dir)
    meta = json.loads((bundle / 'bundle.json').read_text())
    source = meta['source']['path']
    if source not in sys.path:
        sys.path.insert(0, source)
    module, name = (meta.get('entry') or DEFAULT_ENTRY).split(':')
    make = getattr(importlib.import_module(module), name)
    _S.update(meta=meta, sid=make(bundle, meta, variable_id=variable_id) if variable_id else make(bundle, meta))


def info():
    import resource
    return dict(pid=os.getpid(), bot=_S['meta']['bot'], rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024)


def _legal_call(dealer, calls, call):
    from bridge_harness.core import auction_contract, normalize_bid
    call = normalize_bid(call)
    try:
        auction_contract(dealer, (*calls, call))
    except ValueError as e:
        if str(e) != 'Incomplete auction':
            raise RuntimeError(f'Bot made an illegal call {call!r}') from None
    return call


def bid(hand, seat, dealer, vulnerability, calls, style=None):
    started = time.perf_counter()
    sid = _S['sid']
    made = sid.bid(tuple(hand), seat, dealer, vulnerability, list(calls), style) if style else \
        sid.bid(tuple(hand), seat, dealer, vulnerability, list(calls))
    call = _legal_call(dealer, calls, made)
    return call, time.perf_counter() - started


def play(observation, facing, systems, seed, style=None):
    started = time.perf_counter()
    sid = _S['sid']
    card = sid.play(observation, facing, systems, random.Random(seed), style) if style else \
        sid.play(observation, facing, systems, random.Random(seed))
    if card not in observation.legal:
        raise RuntimeError('Bot chose an illegal card')
    return card, time.perf_counter() - started


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


def sid_table(hands, dealer, vulnerability, board_id, seed, systems, personas=None):
    """Sid at all four seats on this deal: the auction, then the play. Returns the record. personas: {seat: persona}
    for the seats that had one at the person's table (the same Sids); the seat without one plays plain Sid."""
    from sidplay import personas as P
    from bridge_harness.core import SEATS, Board, Game, auction_contract, symbol
    started = time.perf_counter()
    calls = []
    while True:
        seat = (dealer + len(calls)) % 4
        calls.append(bid(hands[seat], seat, dealer, vulnerability, calls, P.bid_style(personas, seat))[0])
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
    rng = random.Random(seed)
    while not game.done:
        o = game.observation()
        game.play(play(o, 'sid', systems, rng.getrandbits(64), P.play_style(personas, o.controller))[0])
    return dict(calls=calls, contract=contract.text(), declarer=SEATS[contract.declarer], tricks=game.declarer_tricks,
                ns_score=game.ns_score(), play=[[SEATS[s], symbol(c)] for s, c in game.history],
                seconds=time.perf_counter() - started)
