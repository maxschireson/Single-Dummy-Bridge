"""Bridge rules the server needs, on top of bridge_harness.core (which the bundle's source provides)."""
import secrets

from bridge_harness.core import (SEATS, SUITS, Board, Contract, Game, auction_contract, imps, normalize_bid, score,  # noqa: F401
                                 symbol, card, vulnerable, winner)

CALL_ORDER = ('PASS', 'X', 'XX') + tuple(f'{level}{strain}' for level in range(1, 8) for strain in 'CDHSN')
# Standard 16-board cycle: dealer rotates N E S W, vulnerability by board number.
VUL_CYCLE = ('None', 'NS', 'EW', 'Both', 'NS', 'EW', 'Both', 'None',
             'EW', 'Both', 'None', 'NS', 'Both', 'None', 'NS', 'EW')


def board_meta(number):
    """(dealer seat, vulnerability) of board `number` (1-based) in the standard cycle."""
    return (number - 1) % 4, VUL_CYCLE[(number - 1) % 16]


def new_deal(rng=None):
    rng = rng or secrets.SystemRandom()
    cards = list(range(52))
    rng.shuffle(cards)
    return tuple(tuple(sorted(cards[13 * s:13 * s + 13])) for s in range(4))


def auction_state(dealer, calls):
    """'open' (more calls to come), or the final Contract / None when the auction has ended. Raises on an illegal sequence."""
    try:
        return auction_contract(dealer, calls)
    except ValueError as e:
        if str(e) == 'Incomplete auction':
            return 'open'
        raise


def legal_calls(dealer, calls):
    """Calls the next player may make, in CALL_ORDER."""
    if auction_state(dealer, calls) != 'open':
        return []
    out = []
    for c in CALL_ORDER:
        try:
            auction_contract(dealer, (*calls, c))
        except ValueError as e:
            if str(e) != 'Incomplete auction':
                continue
        out.append(c)
    return out


def parse_call(text):
    c = normalize_bid(str(text))
    if c not in CALL_ORDER:
        raise ValueError('Unknown call')
    return c


def result_text(contract, tricks):
    if contract is None:
        return 'Passed out'
    over = tricks - contract.level - 6
    return '=' if over == 0 else f'{over:+d}'


def contract_text(contract):
    return 'Pass' if contract is None else contract.text().replace('N', 'NT') if 'N' == contract.strain else contract.text()


def remaining_hands(game):
    """Cards still held, by seat (the current trick's cards are already removed)."""
    return tuple(tuple(sorted(h)) for h in game.hands)
