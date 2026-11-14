"""A stand-in for Sid with no models: for tests and for working on the interface without TensorFlow.

Same functions as engine.py. Bids: opens 1NT with 15-17 balanced or one of a suit with 12+, otherwise passes.
Cards: wins cheaply when it can, otherwise plays its lowest card. Claims: the referee accepts any claim up to
`FAKE_DD` tricks (None = all remaining).
"""
import os
import random
import time

from bridge_harness.core import SEATS, Board, Game, auction_contract, symbol, winner

FAKE_DD = None
SEEN = dict(bid_styles=[], play_styles=[], sid_personas=[])     # styles the server passed (tests; the fake bot ignores them)
DELAY = float(os.environ.get('SIDPLAY_FAKE_DELAY', '0'))


def init_worker(bundle_dir=None, nice=0, variable_id=None):
    pass


def info():
    return dict(pid=os.getpid(), bot='fake', rss_mb=0)


def _hcp(hand):
    return sum(max(0, c % 13 - 8) for c in hand)


def bid(hand, seat, dealer, vulnerability, calls, style=None):
    time.sleep(DELAY)
    SEEN['bid_styles'].append((seat, style))
    if any(c != 'PASS' for c in calls):
        return 'PASS', 0.
    hcp = _hcp(hand)
    lengths = [sum(1 for c in hand if c // 13 == s) for s in range(4)]
    if 15 <= hcp <= 17 and sorted(lengths) in ([3, 3, 3, 4], [2, 3, 4, 4], [2, 3, 3, 5]):
        return '1N', 0.
    if hcp >= 12:
        s = max(range(4), key=lambda s: (lengths[s], -s))
        return '1' + 'SHDC'[s], 0.
    return 'PASS', 0.


def play(observation, kind, systems, seed, style=None):
    time.sleep(DELAY)
    SEEN['play_styles'].append((observation.controller, style))
    o = observation
    cheap = lambda c: (c % 13, c // 13)
    if o.trick:
        winning = [c for c in o.legal if winner(o.trick + ((o.actor, c),), o.contract.trump) == o.actor]
        if winning and winner(o.trick, o.contract.trump) % 2 != o.actor % 2:
            return min(winning, key=cheap), 0.
        return min(o.legal, key=cheap), 0.
    return max(o.legal, key=lambda c: (c % 13, -(c // 13))), 0.


def side_tricks(hands, trump, leader, trick, side):
    remaining = (sum(len(h) for h in hands) + len(trick)) // 4
    return remaining if FAKE_DD is None else min(FAKE_DD, remaining)


def sid_table(hands, dealer, vulnerability, board_id, seed, systems, personas=None):
    from sidplay import personas as P           # styles passed as engine.sid_table passes them
    SEEN['sid_personas'].append(personas)
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
        return dict(calls=calls, contract=None, declarer=None, tricks=None, ns_score=0, play=[], seconds=0.)
    game = Game(Board(str(board_id), tuple(tuple(h) for h in hands), contract, dealer, vulnerability, tuple(calls)))
    while not game.done:
        o = game.observation()
        game.play(play(o, 'sid', systems, 0, P.play_style(personas, o.controller))[0])
    return dict(calls=calls, contract=contract.text(), declarer=SEATS[contract.declarer], tricks=game.declarer_tricks,
                ns_score=game.ns_score(), play=[[SEATS[s], symbol(c)] for s, c in game.history], seconds=0.)
