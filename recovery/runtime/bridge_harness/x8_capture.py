"""What an 8X decision writes into the record, and how to read it back.

The note sits under `x8` in the action's details. Everything in it comes from the bot's own view: the layouts are
its samples of the hidden hands, never the deal.

  always      the candidate cards with the net's prior, the value used, the rollout mean, how many layouts each got,
              the hand-over odds and the claim verdict
  level 1     `forks`: inside-rollout pairs (x8_rollout.Fork), each with its own layout, so a pair can be rebuilt
              without anything else from the note
  level 2     `cap`: the layouts played out (up to a limit), their weights and the per-layout results

Cards in a line are one letter each (A-Z for cards 0-25, a-z for 26-51; card = 13 x suit + rank, suits S H D C,
ranks 2..A). A layout is a hex number over the unseen cards in ascending order: bit k set = the k-th unseen card is
held by the second of the two hidden seats (in seat order N E S W). At the opening lead three hands are hidden and the
number is read in base 3 instead: digit k (the k-th unseen card's, lowest first) is the place of its holder among the
three hidden seats in seat order. Which reading applies follows from the decision the note belongs to.
"""
import base64

import numpy as np

from .core import Board, Game

LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
NUMBER = {ch: i for i, ch in enumerate(LETTERS)}


def cards_text(cards):
    return ''.join(LETTERS[int(c)] for c in cards)


def text_cards(text):
    return [NUMBER[ch] for ch in text]


def hidden_of(o):
    """(the hidden seats, the unseen cards in ascending order): two seats at a decision with dummy down, three at the
    opening lead."""
    hidden = [s for s in range(4) if o.known_hands[s] is None]
    if len(hidden) not in (2, 3):
        raise ValueError('A layout code needs two hidden hands, or three at the opening lead')
    gone = {c for _, c in o.history} | {c for h in o.known_hands if h is not None for c in h}
    return hidden, [c for c in range(52) if c not in gone]


def layout_code(o, world):
    hidden, unseen = hidden_of(o)
    if len(hidden) == 2:
        second = set(world[hidden[1]])
        return '%x' % sum(1 << k for k, c in enumerate(unseen) if c in second)
    place = {c: j for j, s in enumerate(hidden) for c in world[s]}
    return '%x' % sum(place[c] * 3 ** k for k, c in enumerate(unseen))


def layout_world(o, code):
    """The four hands as they stand at the decision `o`, for a layout code."""
    hidden, unseen = hidden_of(o)
    bits = int(code, 16)
    hands = list(o.known_hands)
    if len(hidden) == 2:
        hands[hidden[0]] = tuple(c for k, c in enumerate(unseen) if not bits >> k & 1)
        hands[hidden[1]] = tuple(c for k, c in enumerate(unseen) if bits >> k & 1)
        return tuple(hands)
    digit = [bits // 3 ** k % 3 for k in range(len(unseen))]
    for j, s in enumerate(hidden):
        hands[s] = tuple(c for k, c in enumerate(unseen) if digit[k] == j)
    return tuple(hands)


def pack(array, dtype):
    return base64.b64encode(np.ascontiguousarray(array, dtype).tobytes()).decode()


def unpack(text, dtype, shape=None):
    a = np.frombuffer(base64.b64decode(text), dtype)
    return a if shape is None else a.reshape(shape)


def fork_row(o, world, fork):
    """A fork as it is written: [layout code, root card, line to the fork, seat, card chosen, card forced, the net's
    probability of each, declarer's tricks after each]."""
    return [layout_code(o, world), LETTERS[fork.first], cards_text(fork.prefix), fork.seat, LETTERS[fork.main], LETTERS[fork.other],
            round(fork.p_main, 4), round(fork.p_other, 4), fork.main_tricks, fork.other_tricks]


def imagined_board(o, world):
    """A board on which the play so far happened and the hidden hands lie as in `world`."""
    hands = tuple(tuple(sorted(set(world[s]) | {x for seat, x in o.history if seat == s})) for s in range(4))
    return Board('x8', hands, o.contract, o.dealer, o.vulnerability, o.auction)


def fork_view(o, row):
    """Rebuild a recorded fork: (the Observation of the seat to play at the fork, the card the rollout chose there,
    the card forced, declarer's tricks after each, the net's probability of each). `o` is the Observation of the
    decision the note belongs to. The Observation returned is that seat's own view in the imagined layout: its
    hand, dummy, the auction, and the play including the rollout's cards so far."""
    code, first, prefix, seat, main, other, p_main, p_other, main_tricks, other_tricks = row
    game = Game(imagined_board(o, layout_world(o, code)))
    for _, x in o.history:
        game.play(x)
    for x in [NUMBER[first], *text_cards(prefix)]:
        game.play(x)
    view = game.observation()
    if view.actor != seat:
        raise ValueError('The recorded fork does not replay to its seat')
    return view, NUMBER[main], NUMBER[other], main_tricks, other_tricks, p_main, p_other


def capture_block(o, worlds, weights, tricks, floor, limit):
    """Level 2: up to `limit` layouts (the heaviest), their weights and what each card took in each."""
    order = np.argsort(-np.asarray(weights), kind='stable')[:limit]
    return dict(layouts=[layout_code(o, worlds[i]) for i in order], w=pack(np.asarray(weights)[order], np.float32),
                t=pack(np.asarray(tricks)[order], np.int8), f=pack(np.asarray(floor)[order], np.uint8), shape=[len(order), int(np.asarray(tricks).shape[1])])


def read_capture(o, cap):
    """(worlds, weights, [layout, card] declarer's tricks (-1 = not played), [layout, card] floored) from a level 2 block."""
    shape = tuple(cap['shape'])
    return ([layout_world(o, code) for code in cap['layouts']], unpack(cap['w'], np.float32), unpack(cap['t'], np.int8, shape),
            unpack(cap['f'], np.uint8, shape).astype(bool))
