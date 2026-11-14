"""Winning-line logic for the 8X bot: what the declaring side can guarantee from its own view, asked at positions
the bot only imagines.

The solver is `sure_cpp` (experiments/sure_tricks/sure.cpp on research/sure-trick-table-20261112; see claims.py for
its game and for how a deal with East-West declaring is turned). claims.py asks it about the position in hand when
the declaring side is to play. Here the same question is put at three kinds of position:

  root        the declaring side to play, as claims.py: which cards guarantee the contract (`Finder.root`)
  hand-over   a defender to play: for a candidate card and a layout of the hidden hands, the position declarer
              would then face, from declarer's view in that layout. Does declarer hold a guaranteed line there?
              (`Finder.handovers`). A defender cannot know; over the layouts it believes in, the share in which a
              card hands declarer a guarantee is that card's hand-over odds.
  boundary    the start of a trick inside a rollout: how many of the tricks left the declaring side can guarantee
              from its view in that row (`Finder.boundaries`)

"Guaranteed" is against every split of the cards declarer cannot see and every defence, given hand sizes and
show-outs, so it holds in the layout in question too.

Two solver processes per Python process, kept open (their transposition tables stay valid across positions): one
answers per card ("does this card guarantee N more tricks"), one gives a position's value at the start of a trick.
A question that outlasts its time allowance is abandoned: the process is replaced and the answer is "not known".
"""
import atexit
import json
import os
import select
import subprocess
import time

import numpy as np

from .core import winner

BIT = np.uint64(1) << np.arange(52, dtype=np.uint64)
SUIT_BIT = (np.uint64(1) << np.arange(4, dtype=np.uint64)).astype(np.int64)


def rot(seat, side):
    """The solver's seat for a real seat: its North-South are the declaring side."""
    return seat if side == 0 else (seat + 3) % 4


def unrot(seat, side):
    return seat if side == 0 else (seat + 1) % 4


def mask(cards):
    m = 0
    for c in cards:
        m |= 1 << int(c)
    return m


def line(trump, leader, north, south, pool, count_e, count_w, void_e, void_w, trick=(), need=None):
    """One solver input line; with `need`, the per-card question "does this card guarantee `need` more tricks"."""
    text = '%d %d %x %x %x %d %d %d %d' % (trump, leader, north, south, pool, count_e, count_w, void_e, void_w)
    if trick:
        text += ' ' + ' '.join(str(int(x)) for x in trick)
    return text if need is None else 'N%d %s' % (need, text)


def show_outs(o):
    """{seat: suits it has shown out of, as bits} from the play so far."""
    voids = {s: 0 for s in range(4)}
    led = None
    for k, (seat, x) in enumerate(o.history):
        if k % 4 == 0:
            led = x // 13
        elif x // 13 != led:
            voids[seat] |= 1 << led
    return voids


def root_line(o, need=None):
    """(state, line): the declaring side to play with dummy down. state is 'made' (the tricks asked for are in),
    'lost' (too few tricks are left), or 'ask' with the line that asks which cards guarantee them. `need` is the
    tricks still wanted from now on; by default what the contract still needs."""
    c = o.contract
    need = c.level + 6 - o.declarer_tricks if need is None else need
    left = len(o.known_hands[o.actor])
    if need <= 0:
        return 'made', None
    if need > left:
        return 'lost', None
    side = c.declarer % 2
    played = {x for _, x in o.history}
    mine = set(o.known_hands[c.declarer]) | set(o.known_hands[c.dummy])
    pool = [x for x in range(52) if x not in played and x not in mine]
    voids = show_outs(o)
    hands = {rot(c.declarer, side): o.known_hands[c.declarer], rot(c.dummy, side): o.known_hands[c.dummy]}
    count = {rot(s, side): 13 - sum(1 for seat, _ in o.history if seat == s) for s in range(4) if s % 2 != side}
    void = {rot(s, side): voids[s] for s in range(4) if s % 2 != side}
    return 'ask', line(c.trump, rot(o.leader, side), mask(hands[0]), mask(hands[2]), mask(pool), count[1], count[3], void[1], void[3],
                       [x for _, x in o.trick], need)


def after_card(o, world, x):
    """(state, line, declaring side plays next): the position once the defender to play has played `x`, as declarer
    sees it in the layout `world` (world[seat] = the cards a seat holds now). state as root_line."""
    c = o.contract
    side = c.declarer % 2
    me = o.actor
    if me % 2 == side:
        raise ValueError('after_card is for a defender\'s card')
    partner = (me + 2) % 4
    trick = list(o.trick) + [(me, x)]
    won, leader, done = o.declarer_tricks, o.leader, len(o.history) // 4
    voids = show_outs(o)
    if o.trick and x // 13 != o.trick[0][1] // 13:
        voids[me] |= 1 << (o.trick[0][1] // 13)
    if len(trick) == 4:
        leader = winner(trick, c.trump)
        won += leader % 2 == side
        trick = []
        done += 1
    need = c.level + 6 - won
    if need <= 0:
        return 'made', None, None
    if need > 13 - done:
        return 'lost', None, None
    mine = [y for y in world[me] if y != x]
    hands = {rot(c.declarer, side): world[c.declarer], rot(c.dummy, side): world[c.dummy]}
    count = {rot(me, side): len(mine), rot(partner, side): len(world[partner])}
    void = {rot(me, side): voids[me], rot(partner, side): voids[partner]}
    text = line(c.trump, rot(leader, side), mask(hands[0]), mask(hands[2]), mask(mine) | mask(world[partner]), count[1], count[3],
                void[1], void[3], [y for _, y in trick], need)
    return 'ask', text, ((leader + len(trick)) % 4) % 2 == side


def holds(answer, declaring_next):
    """Per-card answers at a position -> does the declaring side hold a guaranteed line there. With the declaring
    side to play, some card must guarantee it; with a defender to play, every card that defender could hold must
    leave it guaranteed."""
    cards = answer.get('cards') or {}
    if not cards:
        return False
    return any(cards.values()) if declaring_next else all(cards.values())


def boundary_lines(rows, index=None):
    """For rows at the start of a trick: (left, lines). A line is the position's value question for one of the rows
    `index` (default every row): how many of the `left` tricks to come the declaring side can guarantee."""
    if rows.on_table:
        raise ValueError('Boundaries are the start of a trick')
    side = rows.declarer % 2
    left = 13 - rows.played // 4
    index = np.arange(rows.n) if index is None else np.asarray(index, np.int64)
    if left <= 0 or not len(index):
        return left, []
    holder = rows.holder[index]
    m = [(holder == unrot(r, side)).astype(np.uint64) @ BIT for r in range(4)]
    count = [(holder == unrot(r, side)).sum(axis=1) for r in (1, 3)]
    void = [rows.void[index][:, unrot(r, side), :].astype(np.int64) @ SUIT_BIT for r in (1, 3)]
    leader = (rows.leader[index].astype(np.int64) + (0 if side == 0 else 3)) % 4
    pool = m[1] | m[3]
    return left, [line(rows.trump, int(leader[i]), int(m[0][i]), int(m[2][i]), int(pool[i]), int(count[0][i]), int(count[1][i]),
                       int(void[0][i]), int(void[1][i])) for i in range(len(index))]


class Solver:
    """One sure_cpp process and a memory of what it has answered."""

    def __init__(self, binary, flags=('--keep',), remember=200000):
        self.command = [binary, *flags]
        self.proc, self.buffer = None, b''
        self.memory, self.remember = {}, remember
        self.calls = self.timeouts = self.hits = 0
        self.seconds = 0.

    def _start(self):
        self.proc = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
        self.buffer = b''

    def _stop(self):
        if self.proc is not None:
            try:
                self.proc.kill()
                self.proc.wait()
            except OSError:
                pass
            for pipe in (self.proc.stdin, self.proc.stdout):
                try:
                    pipe.close()
                except OSError:
                    pass
            self.proc = None

    def close(self):
        self._stop()

    def _read_line(self, deadline):
        """One line of the solver's answer, or None once `deadline` (a perf_counter time) has passed."""
        fd = self.proc.stdout.fileno()
        while b'\n' not in self.buffer:
            wait = deadline - time.perf_counter()
            if wait <= 0 or not select.select([fd], [], [], wait)[0]:
                return None
            chunk = os.read(fd, 1 << 16)
            if not chunk:
                raise RuntimeError('The claim solver ended unexpectedly: ' + ' '.join(self.command))
            self.buffer += chunk
        text, self.buffer = self.buffer.split(b'\n', 1)
        return text

    def ask(self, texts, allowance=2., each=1.):
        """Answers (parsed JSON) for the lines `texts`, in order; None where the time ran out. `allowance` is the
        time for all of them together, `each` the most one question may take."""
        out = [None] * len(texts)
        todo = {}
        for i, t in enumerate(texts):
            if t in self.memory:
                out[i] = self.memory[t]
                self.hits += 1
            else:
                todo.setdefault(t, []).append(i)
        if not todo:
            return out
        started = time.perf_counter()
        end = started + allowance
        pending = list(todo)
        for at in range(0, len(pending), 64):               # small batches: neither pipe can fill
            part = pending[at:at + 64]
            if time.perf_counter() >= end:
                break
            if self.proc is None or self.proc.poll() is not None:
                self._start()
            self.proc.stdin.write(('\n'.join(part) + '\n').encode())
            failed = False
            for t in part:
                got = self._read_line(min(end, time.perf_counter() + each))
                if got is None:
                    failed = True
                    break
                answer = json.loads(got)
                if 'cards' in answer:
                    answer = dict(cards={int(k): int(v) for k, v in answer['cards'].items()}, left=answer.get('left'))
                else:
                    answer = dict(value=int(answer['value']), left=answer.get('left'))
                self.calls += 1
                if len(self.memory) >= self.remember:
                    self.memory.clear()
                self.memory[t] = answer
                for i in todo[t]:
                    out[i] = answer
            if failed:                                      # the question in hand is abandoned with the process
                self.timeouts += 1
                self._stop()
        self.seconds += time.perf_counter() - started
        return out


class Finder:
    """The three questions of this module, over two solver processes."""

    def __init__(self, binary=None, each=1.):
        self.binary = binary or os.environ.get('SURE_BIN', 'sure_cpp')
        if not (os.path.isfile(self.binary) and os.access(self.binary, os.X_OK)):
            raise RuntimeError(f'The claim solver was not found at {self.binary!r}: build experiments/sure_tricks/sure.cpp '
                               '(research/sure-trick-table-20261112) and set SURE_BIN')
        self.cards = Solver(self.binary, ('--keep',))
        self.values = Solver(self.binary, ('--keep', '--value'))
        self.each = each
        atexit.register(self.close)

    def close(self):
        self.cards.close()
        self.values.close()

    def stats(self):
        return dict(calls=self.cards.calls + self.values.calls, seconds=round(self.cards.seconds + self.values.seconds, 4),
                    timeouts=self.cards.timeouts + self.values.timeouts, remembered=self.cards.hits + self.values.hits)

    # ---- the declaring side to play -------------------------------------------------------
    def root(self, o, need=None):
        """(state, {legal card: guarantees the contract}): state is 'made', 'lost', 'guaranteed' (some card guarantees
        it), 'open' (none does) or 'unknown' (no answer in time). The mapping is empty unless 'guaranteed'/'open'.
        With `need`, the question is that many more tricks instead of the contract (need = cards left: a claim)."""
        state, text = root_line(o, need)
        if state != 'ask':
            return state, {}
        answer = self.cards.ask([text], allowance=self.each, each=self.each)[0]
        if answer is None:
            return 'unknown', {}
        cards = answer['cards']
        sure = {x: bool(cards[self._rep(o, x, cards)]) for x in o.legal}
        return ('guaranteed' if any(sure.values()) else 'open'), sure

    @staticmethod
    def _rep(o, x, cards):
        """The solver answers for one card of each run of touching cards; this is the answered card of x's run."""
        if x in cards:
            return x
        hand = set(o.known_hands[o.actor])
        gone = {y for _, y in o.history} - {y for _, y in o.trick}        # cards of the current trick still count as live
        for y in cards:
            if y // 13 != x // 13 or y not in hand:
                continue
            lo, hi = sorted((x, y))
            if all(z in hand or z in gone for z in range(lo + 1, hi)):
                return y
        raise RuntimeError(f'No representative for card {x} among {sorted(cards)}')

    # ---- a defender to play ---------------------------------------------------------------
    def handovers(self, o, worlds, cards, allowance=.5, order=None):
        """[layout, card] 1 where declarer holds a guaranteed line once the defender has played the card in that
        layout, 0 where not, -1 where it was not asked in the time allowed. Layouts are asked in `order` (default as
        given), every card of a layout before the next layout."""
        out = np.full((len(worlds), len(cards)), -1, np.int8)
        ask, where = [], []
        for i in (range(len(worlds)) if order is None else order):
            for j, x in enumerate(cards):
                state, text, declaring_next = after_card(o, worlds[i], x)
                if state == 'made':
                    out[i, j] = 1
                elif state == 'lost':
                    out[i, j] = 0
                else:
                    ask.append(text)
                    where.append((i, j, declaring_next))
        if ask:
            for (i, j, declaring_next), answer in zip(where, self.cards.ask(ask, allowance=allowance, each=self.each)):
                if answer is not None:
                    out[i, j] = holds(answer, declaring_next)
            done = (out >= 0).all(axis=1)                    # a layout counts only if every card was answered in it
            out[~done] = -1
        return out

    # ---- the start of a trick inside a rollout --------------------------------------------
    def boundaries(self, rows, index=None, allowance=.5):
        """(sure, left): for each of the rows `index` (default every row), the tricks of the `left` remaining that the
        declaring side can guarantee from its own view in that row; -1 where not known."""
        left, lines = boundary_lines(rows, index)
        sure = np.full(len(lines), -1, np.int16)
        for i, answer in enumerate(self.values.ask(lines, allowance=allowance, each=self.each)):
            if answer is not None:
                sure[i] = answer['value']
        return sure, left


_SHARED = {}


def shared(binary=None):
    key = binary or os.environ.get('SURE_BIN', 'sure_cpp')
    if key not in _SHARED:
        _SHARED[key] = Finder(key)
    return _SHARED[key]
