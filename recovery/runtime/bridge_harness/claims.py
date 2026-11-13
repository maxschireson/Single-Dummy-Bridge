"""The claim finder (single-dummy sure tricks) for players: what the declaring side can guarantee from its own view.

The solver is `sure_cpp`, built from experiments/sure_tricks/sure.cpp of research/sure-trick-table-20261112
(`g++ -O2 -march=native -std=c++17 -o sure_cpp sure.cpp`); its path comes from SURE_BIN. Its game: the declaring
side's two hands are known, the defenders' cards are one pool whose split is settled only as cards are played
(hand sizes and show-outs respected), so a card's value is the tricks it guarantees against every split and every
defence. The solver's North-South declare; a deal with East or West declaring is turned a quarter.

One solver process per Python process, kept open; its transposition table stays valid across positions (`--keep`).
"""
import json
import os
import subprocess
import threading

SUITMASK = [0x1FFF << (13 * s) for s in range(4)]


def _rot(seat, side):
    return seat if side == 0 else (seat + 3) % 4


def _mask(cards):
    m = 0
    for c in cards:
        m |= 1 << int(c)
    return m


def position(o):
    """sure_cpp's input for an Observation of the declaring side (declarer or dummy to play, dummy visible)."""
    c = o.contract
    side = c.declarer % 2
    decl, dummy = c.declarer, c.dummy
    played = {x for _, x in o.history}
    mine = set(o.known_hands[decl]) | set(o.known_hands[dummy])
    pool = [x for x in range(52) if x not in played and x not in mine]
    counts, voids = {}, {}
    for s in range(4):
        if s % 2 != side:
            counts[_rot(s, side)] = 13 - sum(1 for seat, _ in o.history if seat == s)
            voids[_rot(s, side)] = 0
    led = None
    for k, (seat, x) in enumerate(o.history):
        if k % 4 == 0:
            led = x // 13
        elif x // 13 != led and seat % 2 != side:
            voids[_rot(seat, side)] |= 1 << led
    hands = {_rot(decl, side): o.known_hands[decl], _rot(dummy, side): o.known_hands[dummy]}
    trick = ' '.join(str(int(x)) for _, x in o.trick)
    return ('%d %d %x %x %x %d %d %d %d %s' % (c.trump, _rot(o.leader, side), _mask(hands[0]), _mask(hands[2]), _mask(pool),
                                              counts[1], counts[3], voids[1], voids[3], trick)).strip()


class Claims:
    """Per-card guarantees for the declaring side. `values(o)`: {card: tricks it guarantees from now on, the current
    trick included}; cards that touch in the hand on play get the value of the solver's representative."""

    def __init__(self, binary=None):
        self.binary = binary or os.environ.get('SURE_BIN', 'sure_cpp')
        self.proc, self.lock = None, threading.Lock()
        self.calls, self.seconds = 0, 0.

    def _ask(self, text):
        with self.lock:
            if self.proc is None or self.proc.poll() is not None:
                self.proc = subprocess.Popen([self.binary, '--keep'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
            self.proc.stdin.write(text + '\n')
            self.proc.stdin.flush()
            out = json.loads(self.proc.stdout.readline())
        self.calls += 1
        self.seconds += out.get('seconds', 0.)
        return out

    def values(self, o):
        got = self._ask(position(o))
        cards = {int(k): v for k, v in got['cards'].items()}
        return {x: cards[self._rep(o, x, cards)] for x in o.legal}

    def _rep(self, o, x, cards):
        if x in cards:
            return x
        hand = set(o.known_hands[o.actor])
        played = {y for _, y in o.history} - {y for _, y in o.trick}     # cards of the current trick still count as live
        for y in cards:
            if y // 13 != x // 13 or y not in hand:
                continue
            lo, hi = sorted((x % 13, y % 13))
            if all(z in hand or z in played for z in range(13 * (x // 13) + lo + 1, 13 * (x // 13) + hi)):
                return y
        raise RuntimeError(f'No representative for card {x} among {sorted(cards)}')

    def makes(self, o, need):
        """{card: 1 if it guarantees `need` more tricks (the current trick included), else 0}: the finder's cheaper
        question, about 25 times faster than values(o) at trick 4 and 10 times at trick 5."""
        got = self._ask(f'N{need} ' + position(o))
        cards = {int(k): v for k, v in got['cards'].items()}
        return {x: int(cards[self._rep(o, x, cards)]) for x in o.legal}

    def verdict(self, o, exact=True):
        """(state, values): 'made' (the contract's tricks are already in), 'lost' (fewer tricks are left than it
        needs), 'guaranteed' (some card guarantees it), 'open' (no card does); values as values(o). With exact False
        only the contract is asked about: values are then makes(o, need), and empty when it is made or lost."""
        c = o.contract
        need = c.level + 6 - o.declarer_tricks
        left = len(o.known_hands[o.actor])
        if not exact:
            if need <= 0 or need > left:
                return ('made' if need <= 0 else 'lost'), {}
            v = self.makes(o, need)
            return ('guaranteed' if max(v.values()) else 'open'), v
        v = self.values(o)
        if need <= 0:
            return 'made', v
        if need > left:
            return 'lost', v
        return ('guaranteed' if max(v.values()) >= need else 'open'), v

    def close(self):
        if self.proc is not None:
            self.proc.stdin.close()
            self.proc.wait()
            self.proc = None


_SHARED = None


def shared():
    global _SHARED
    if _SHARED is None:
        _SHARED = Claims()
    return _SHARED
