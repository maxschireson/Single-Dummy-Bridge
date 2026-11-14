"""After the hand: where tricks were lost (double dummy), what was guaranteed (single dummy), and why.

Runs in a worker process (DDS and sure_cpp), never in the web process. Three engines:

- **Double dummy** (DDS, from the bundle's source checkout): the value of every legal card at every card of the play,
  so each card's cost in tricks to the side that played it, with all four hands known.
- **Sure tricks** (`sure_cpp`, the pooled-defender search of `experiments/sure_tricks`, vendored in `play/native`):
  what the declaring side can guarantee against every split of the cards it cannot see, given hand sizes and the suits
  each defender has shown out of. Nothing is sampled and the auction is not used. For the declaring side: whether a line
  guaranteed N tricks, and whether the card played kept it. For a defender: what declarer could guarantee after each card
  the defender could have played.
- **One-card exchanges**: for a double-dummy loss, which exchanges of two cards between the hands the player could not
  see (each exchange consistent with every show-out so far) would have made the card played right. That separates a
  guess that went wrong ("right if West had held the queen") from a card that loses in every layout near the real one.

`analyse(...)` returns plain JSON. The page renders it; the sentences in `text` fields are written here so the tests can
check them.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
import os
from pathlib import Path
import select
import subprocess
import sys
import threading
import time

SUITS = 'SHDC'
RANKS = '23456789TJQKA'
SEAT_NAME = ('North', 'East', 'South', 'West')
SYM = {'S': '♠', 'H': '♥', 'D': '♦', 'C': '♣'}
VERSION = 1

DEFAULTS = dict(
    sure_cards=10,          # exact guaranteed tricks at decisions with at most this many cards left in the mover's hand
    sure_need_cards=13,     # above that, up to this many cards: only "does this card guarantee the contract"
    sure_line_seconds=4.0,  # one exact-value question; past it the decision is marked not analysed
    sure_need_seconds=1.5,  # one contract question
    sure_budget=40.0,       # sure-trick seconds for the whole board (decisions are taken cheapest first)
    swap_budget=20.0,       # one-card exchange seconds for the whole board
    swap_worlds=400,        # most exchanges tried for one card
    auction_cards=8,        # chances of making by the auction (cell game) at decisions with at most this many cards left
    auction_budget=25.0,    # seconds of those for the whole board (decisions taken cheapest first)
    auction_ratio=0.05,     # an exchange is one the auction allows if it leaves the layout at least this likely
)


def sym(c):
    r = RANKS[c % 13]
    return SYM[SUITS[c // 13]] + ('10' if r == 'T' else r)


def code(c):
    return SUITS[c // 13] + RANKS[c % 13]


def cards_text(cards, limit=4):
    cards = sorted(cards, key=lambda c: (c // 13, -(c % 13)))
    out = ', '.join(sym(c) for c in cards[:limit])
    return out + (' and others' if len(cards) > limit else '')


def winner(trick, trump):
    led = trick[0][1] // 13
    return max(trick, key=lambda sc: (2 if sc[1] // 13 == trump else 1 if sc[1] // 13 == led else 0, sc[1] % 13))[0]


# ---- replaying the play ---------------------------------------------------------------------
class State:
    """The position before a card: cards still held, the trick so far, who led it, tricks won, suits shown out of."""

    def __init__(self, hands, trump, declarer):
        self.hands = [set(h) for h in hands]
        self.trump, self.declarer = trump, declarer
        self.trick = []
        self.leader = (declarer + 1) % 4
        self.decl_won = 0
        self.done_tricks = 0
        self.voids = [set() for _ in range(4)]
        self.played = [set() for _ in range(4)]     # every card each seat has played, the current trick included

    @property
    def mover(self):
        return (self.leader + len(self.trick)) % 4

    @property
    def remaining(self):
        """Tricks still to be decided, the current one included."""
        return 13 - self.done_tricks

    def legal(self):
        hand = self.hands[self.mover]
        if self.trick:
            follow = [c for c in hand if c // 13 == self.trick[0][1] // 13]
            if follow:
                return sorted(follow)
        return sorted(hand)

    def play(self, c):
        s = self.mover
        if c not in self.legal():
            raise ValueError(f'{code(c)} is not legal for {SEAT_NAME[s]}')
        if self.trick and c // 13 != self.trick[0][1] // 13:
            self.voids[s].add(self.trick[0][1] // 13)
        self.hands[s].remove(c)
        self.played[s].add(c)
        self.trick.append((s, c))
        won = None
        if len(self.trick) == 4:
            w = winner(self.trick, self.trump)
            won = w % 2 == self.declarer % 2
            self.decl_won += won
            self.done_tricks += 1
            self.leader = w
            self.trick = []
        return won

    def copy(self):
        return deepcopy(self)

    def dd_hands(self):
        return [tuple(sorted(h)) for h in self.hands]


# ---- sure_cpp ---------------------------------------------------------------------------------
def default_binary():
    return os.environ.get('SIDPLAY_SURE_BIN') or str(Path(__file__).resolve().parents[1] / 'native' / 'sure_cpp')


class Sure:
    """One sure_cpp process for one board (`--keep`: values stay valid across positions, so later questions reuse
    earlier work). A question that runs past its time limit kills the process; the next question starts a new one."""

    def __init__(self, binary=None):
        self.binary = binary or default_binary()
        self.proc = None
        self.questions = self.timeouts = 0
        self.seconds = 0.

    def available(self):
        return Path(self.binary).is_file() and os.access(self.binary, os.X_OK)

    def _start(self):
        self.proc = subprocess.Popen([self.binary, '--keep', '--front', '4'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, bufsize=1)

    def ask(self, line, seconds, need=None):
        """By card: tricks the declaring side can guarantee from here (the current trick included), or with `need`,
        1 if the card guarantees that many and 0 if not. None if the question ran past `seconds`."""
        if seconds <= 0:
            return None
        if self.proc is None or self.proc.poll() is not None:
            self._start()
        self.questions += 1
        started = time.perf_counter()
        self.proc.stdin.write(('N%d ' % need if need is not None else '') + line + '\n')
        self.proc.stdin.flush()
        ready, _, _ = select.select([self.proc.stdout], [], [], seconds)
        out = self.proc.stdout.readline() if ready else ''
        self.seconds += time.perf_counter() - started
        if not out:
            self.timeouts += 1
            self.close()
            return None
        return {int(k): v for k, v in json.loads(out)['cards'].items()}

    def close(self):
        if self.proc is not None:
            try:
                self.proc.kill()
                self.proc.wait(timeout=5)
            except Exception:
                pass
            self.proc = None


def _mask(cards):
    m = 0
    for c in cards:
        m |= 1 << c
    return m


def sure_line(st):
    """sure_cpp input for this position from the declaring side's view, rotated so that it sits North-South."""
    r = st.declarer % 2
    real = lambda frame_seat: (frame_seat + r) % 4
    voids = lambda s: sum(1 << x for x in st.voids[s])
    hn, hs, he, hw = (st.hands[real(i)] for i in (0, 2, 1, 3))
    trick = ' '.join(str(c) for _, c in st.trick)
    return ('%d %d %x %x %x %d %d %d %d %s' % (st.trump, (st.leader - r) % 4, _mask(hn), _mask(hs), _mask(he | hw),
                                              len(he), len(hw), voids(real(1)), voids(real(3)), trick)).strip()


def _decl_runs(st, card):
    """Cards of the mover's hand that are equivalent to `card` for the declaring side: same suit, no live card of any
    other hand and no card of the current trick ranked between them (sure_cpp reports one card of each such run)."""
    s, suit = st.mover, card // 13
    others = set().union(*(st.hands[x] for x in range(4) if x != s)) | {c for _, c in st.trick}
    lo = hi = card
    while lo - 1 >= 13 * suit and lo - 1 not in others:
        lo -= 1
    while hi + 1 < 13 * (suit + 1) and hi + 1 not in others:
        hi += 1
    return {c for c in st.hands[s] if lo <= c <= hi}


class Clock:
    """The sure-trick time budget for a board, and the limit for one question."""

    def __init__(self, budget):
        self.deadline = time.perf_counter() + budget

    def give(self, limit):
        return min(limit, self.deadline - time.perf_counter())


def decl_eval(sure, st, need, mode, clock, limit):
    """The declaring side is to move. mode 'tricks': {card: total tricks guaranteed, won so far included};
    mode 'contract': {card: True if it guarantees the contract}. None on timeout."""
    k = need - st.decl_won
    if mode == 'contract' and (k <= 0 or k > st.remaining):
        return {c: k <= 0 for c in st.legal()}
    out = sure.ask(sure_line(st), clock.give(limit), k if mode == 'contract' else None)
    if out is None:
        return None
    vals = {}
    for c in st.legal():
        same = [x for x in _decl_runs(st, c) if x in out] if c not in out else [c]
        if same:
            v = out[same[0]]
            vals[c] = bool(v) if mode == 'contract' else st.decl_won + v
        else:
            v = after_eval(sure, st, c, need, mode, clock, limit)
            if v is None:
                return None
            vals[c] = v
    return vals


def after_eval(sure, st, c, need, mode, clock, limit):
    """After the mover plays `c`: the declaring side's guaranteed total (mode 'tricks') or whether the contract is
    guaranteed (mode 'contract'). None on timeout."""
    nxt = st.copy()
    nxt.play(c)
    if nxt.done_tricks == 13:
        return nxt.decl_won if mode == 'tricks' else nxt.decl_won >= need
    decl_to_move = nxt.mover % 2 == nxt.declarer % 2
    if mode == 'contract':
        k = need - nxt.decl_won
        if k <= 0 or k > nxt.remaining:
            return k <= 0
        out = sure.ask(sure_line(nxt), clock.give(limit), k)
        if out is None:
            return None
        return any(out.values()) if decl_to_move else all(out.values())
    out = sure.ask(sure_line(nxt), clock.give(limit))
    if out is None:
        return None
    return nxt.decl_won + (max(out.values()) if decl_to_move else min(out.values()))


# ---- one-card exchanges -----------------------------------------------------------------------
def exchanges(dds, st, card, viewer_seats, max_worlds):
    """Exchanges of two unseen cards between hands the viewer cannot see, consistent with the show-outs, after which
    `card` would be double-dummy best. Returns (fixing exchanges, number tried, complete)."""
    unseen = [s for s in range(4) if s not in viewer_seats]
    worlds, swaps = [], []
    for i, a in enumerate(unseen):
        for b in unseen[i + 1:]:
            for x in sorted(st.hands[a]):
                for y in sorted(st.hands[b]):
                    if x // 13 == y // 13 and not _between(st, x, y):
                        continue            # equals (no live card between them): the exchange changes nothing
                    if (x // 13) in st.voids[b] or (y // 13) in st.voids[a]:
                        continue            # contradicts a show-out
                    hands = [set(h) for h in st.hands]
                    hands[a].remove(x); hands[a].add(y)
                    hands[b].remove(y); hands[b].add(x)
                    worlds.append([tuple(sorted(h)) for h in hands])
                    swaps.append((a, x, b, y))
    complete = len(worlds) <= max_worlds
    if not complete:
        order = sorted(range(len(worlds)), key=lambda k: -max(swaps[k][1] % 13, swaps[k][3] % 13))
        keep = sorted(order[:max_worlds])
        worlds, swaps = [worlds[k] for k in keep], [swaps[k] for k in keep]
    fixes = []
    if not worlds:
        return fixes, 0, True
    results = _solve_many(dds, worlds, st, viewer_seats)
    for sw, values in zip(swaps, results):
        if card in values and values[card] == max(values.values()):
            fixes.append(sw)
    return fixes, len(worlds), complete


def _between(st, x, y):
    lo, hi = sorted((x, y))
    return any(lo < c < hi for h in st.hands for c in h) or any(lo < c < hi for _, c in st.trick)


def _solve_many(dds, worlds, st, fixed):
    trick = [(s, c) for s, c in st.trick]
    if getattr(dds, 'batch_available', False):
        out = []
        for k in range(0, len(worlds), 200):
            out += [v for v, _ in dds.solve_batch(worlds[k:k + 200], st.trump, st.leader, trick, fixed_seats=tuple(fixed))]
        return out
    return [dds.solve(w, st.trump, st.leader, trick)[0] for w in worlds]


def _exchanged_logw(reader, st, fix, unseen, auction):
    a, x, b, y = fix
    hands = [set(h) for h in st.hands]
    hands[a].remove(x); hands[a].add(y)
    hands[b].remove(y); hands[b].add(x)
    return reader.layout_logw(hands, unseen, st.played, auction)


def explain_exchanges(fixes, tried, ruled_out=0, where=None):
    """A sentence for the exchanges that would have made the card right. ruled_out: such exchanges the auction makes
    too unlikely to count; where(card, seat): the auction's probability that seat holds card."""
    if not tried:
        return None, None
    if not fixes and ruled_out:
        return 'clear', ('The only exchanges of one unseen card that make this card right are ones Sid\u2019s reading of the '
                         'auction rules out, so by the auction it does not turn on where one card lies.')
    if not fixes:
        return 'clear', ('No exchange of one unseen card between the hidden hands makes this card right, so it does not '
                         'turn on where one card lies.')
    count = {}
    for a, x, b, y in fixes:
        count[(a, x, b)] = count.get((a, x, b), 0) + 1
        count[(b, y, a)] = count.get((b, y, a), 0) + 1
    (frm, c, to), n = max(count.items(), key=lambda kv: (kv[1], kv[0][1] % 13))
    others = sorted(v for k, v in count.items() if k != (frm, c, to))
    if n >= 2 and (not others or others[-1] < n):
        odds = (f' By Sid\u2019s reading of the auction, {SEAT_NAME[to]} held it {round(100 * where(c, to))}% of the time.'
                if where else '')
        return 'layout', (f'It turned on the {sym(c)}: with it in {SEAT_NAME[to]}\u2019s hand instead of {SEAT_NAME[frm]}\u2019s, '
                          f'this card would have been right.{odds}')
    a, x, b, y = max(fixes, key=lambda f: (max(f[1] % 13, f[3] % 13), min(f[1] % 13, f[3] % 13)))
    return 'layout', (f'It turned on the layout: had {SEAT_NAME[a]}’s {sym(x)} and {SEAT_NAME[b]}’s {sym(y)} been exchanged, '
                      'this card would have been right.')


# ---- the analysis -----------------------------------------------------------------------------
def contract_parts(contract):
    """'4S', '3NX' -> (level, trump index 0-4)."""
    level, strain = int(contract[0]), contract[1]
    return level, (4 if strain == 'N' else SUITS.index(strain))


def _s(n, word='trick'):
    return f'{n} {word}{"s" if n != 1 else ""}'


def analyse(hands, contract, declarer, play, focus, actor_names=None, dds=None, sure=None, limits=None, auction=None,
            reader=None):
    """hands: four 13-card int tuples (the original deal); contract: '4S', '3NX'...; declarer: seat 0-3; play: [(seat,
    card)] in order; focus: seats whose decisions get the full treatment (the human's, or Sid's in the same chairs;
    dummy counts as declarer). actor_names: {seat: label} for other seats' cards. auction: dict(calls, dealer, vul)
    and reader: an auction.AuctionReader, to read the auction (both or neither). Returns a JSON-ready dict."""
    lim = dict(DEFAULTS, **(limits or {}))
    t0 = time.perf_counter()
    if dds is None:
        from bridge_harness.dds import DDS
        dds = DDS(cache_path='')
    own_sure = sure is None
    sure = sure or Sure()
    names = actor_names or {s: SEAT_NAME[s] for s in range(4)}
    level, trump = contract_parts(contract)
    need = level + 6
    decl_side = declarer % 2
    dummy = (declarer + 2) % 4
    controller = lambda seat: declarer if seat == dummy else seat
    focus = {controller(s) for s in focus}
    focus_declares = declarer in focus

    # ---- pass 1: double dummy at every card -----------------------------------------------------
    st = State(hands, trump, declarer)
    cards, states = [], []
    for n, (seat, c) in enumerate(play):
        if seat != st.mover:
            raise ValueError(f'card {n + 1} is out of turn')
        values, _ = dds.solve(st.dd_hands(), trump, st.leader, list(st.trick))
        best = max(values.values())
        mover_decl = seat % 2 == decl_side
        dd_before = st.decl_won + (best if mover_decl else st.remaining - best)
        who = controller(seat)
        row = dict(n=n + 1, trick=st.done_tricks + 1, seat='NESW'[seat], card=code(c), by='NESW'[who], dd=dd_before,
                   loss=best - values[c], focus=who in focus, left=len(st.hands[seat]))
        if row['loss']:
            row['better'] = [code(x) for x, v in sorted(values.items()) if v == best]
        cards.append(row)
        states.append(st.copy())
        st.play(c)
    tricks = st.decl_won if st.done_tricks == 13 else None

    # ---- pass 2: sure tricks at the focus side's decisions, cheapest first ----------------------
    sure_ok = sure.available()
    clock = Clock(lim['sure_budget'])
    skipped = dict(early=0, budget=0)
    if sure_ok:
        todo = [i for i, r in enumerate(cards) if r['focus'] and r['left'] <= lim['sure_need_cards']]
        skipped['early'] = sum(r['focus'] for r in cards) - len(todo)
        for i in sorted(todo, key=lambda i: (cards[i]['left'], i)):
            if clock.give(1) <= 0:
                skipped['budget'] += 1
                continue
            row, s = cards[i], states[i]
            c = play[i][1]
            mode = 'tricks' if row['left'] <= lim['sure_cards'] else 'contract'
            limit = lim['sure_line_seconds'] if mode == 'tricks' else lim['sure_need_seconds']
            if s.mover % 2 == decl_side:
                vals = decl_eval(sure, s, need, mode, clock, limit)
                if vals is None:
                    row['sure'] = dict(kind='declaring', mode=mode, unknown=True)
                    continue
                if mode == 'tricks':
                    g = max(vals.values())
                    row['sure'] = dict(kind='declaring', mode=mode, guaranteed=g, played=vals[c], makes=g >= need,
                                       played_makes=vals[c] >= need, keep=[code(x) for x, v in sorted(vals.items()) if v == g])
                else:
                    makes = any(vals.values())
                    row['sure'] = dict(kind='declaring', mode=mode, makes=makes, played_makes=vals[c],
                                       keep=[code(x) for x, v in sorted(vals.items()) if v] if makes else [])
            else:
                vals = {}
                for x in s.legal():
                    v = after_eval(sure, s, x, need, mode, clock, limit)
                    if v is None:
                        vals = None
                        break
                    vals[x] = v
                if vals is None:
                    row['sure'] = dict(kind='defending', mode=mode, unknown=True)
                    continue
                if mode == 'tricks':
                    low = min(vals.values())
                    row['sure'] = dict(kind='defending', mode=mode, declarer_after=vals[c], lowest=low,
                                       handed_contract=low < need <= vals[c], handed_trick=vals[c] > low,
                                       safe=[code(x) for x, v in sorted(vals.items()) if v == low])
                else:
                    row['sure'] = dict(kind='defending', mode=mode, handed_contract=vals[c] and not all(vals.values()),
                                       handed_trick=vals[c] and not all(vals.values()),
                                       safe=[code(x) for x, v in sorted(vals.items()) if not v])
    if own_sure:
        sure.close()

    # ---- pass 2b: chances of making by the auction (cell game), cheapest decisions first --------
    chance_ok = reader is not None and auction is not None and reader.available()
    chance_skipped = dict(budget=0, failed=0)
    if chance_ok:
        clock = Clock(lim['auction_budget'])
        todo = [i for i, r in enumerate(cards) if r['focus'] and r['left'] <= lim['auction_cards']]
        for i in sorted(todo, key=lambda i: (cards[i]['left'], i)):
            if clock.give(1) <= 0:
                chance_skipped['budget'] += 1
                continue
            row, s, c = cards[i], states[i], play[i][1]
            try:
                if s.mover % 2 == decl_side:
                    r = reader.declaring(s, need, s.played, auction, c)
                    if r is None or r.get('trivial'):
                        continue
                    row['chance'] = dict(kind='declaring', best=r['best'], played=r['played'],
                                         keep=[code(x) for x, v in sorted(r['chances'].items()) if v is not None and v >= r['best'] - 1e-9])
                else:
                    vals = {}
                    for x in s.legal():
                        v = reader.after(s, x, need, s.played, auction)
                        if v is not None:
                            vals[x] = v
                    if c not in vals or len(vals) < 2:
                        continue
                    low = min(vals.values())
                    row['chance'] = dict(kind='defending', played=vals[c], lowest=low,
                                         safe=[code(x) for x, v in sorted(vals.items()) if v <= low + 1e-9])
            except Exception:
                chance_skipped['failed'] += 1
        reader.close()

    def pct(p):
        return f'{round(100 * p)}%'

    # ---- pass 3: events, and why, in the order of play -------------------------------------------
    events, lost, given = [], [], []
    was_guaranteed = None          # after the declaring side's last analysed card: was the contract still guaranteed
    swap_clock = Clock(lim['swap_budget'])
    for i, row in enumerate(cards):
        sr = row.get('sure')
        c = play[i][1]
        t = row['trick']
        if sr and not sr.get('unknown') and sr['kind'] == 'declaring':
            keep = [_card(k) for k in sr['keep']]
            if sr['makes'] and not any(e['kind'] == 'had_guarantee' for e in events):
                tail = f' ({_s(sr["guaranteed"])} against any layout of the unseen cards)' if sr['mode'] == 'tricks' else ''
                start = 'From the opening lead' if t == 1 and row['n'] <= 2 else f'From trick {t}'
                events.append(dict(n=row['n'], trick=t, kind='had_guarantee',
                                   text=f'{start} you had a line guaranteeing the contract{tail}.'))
            elif sr['makes'] and was_guaranteed is False:
                last = next(((play[j][0], play[j][1]) for j in range(i - 1, -1, -1) if play[j][0] % 2 != decl_side), None)
                after = f'after {SEAT_NAME[last[0]]}\u2019s {sym(last[1])}, ' if last else ''
                events.append(dict(n=row['n'], trick=t, kind='regained',
                                   text=f'Trick {t}: {after}the contract was guaranteed again.'))
            if sr['makes'] and not sr['played_makes']:
                sr['text'] = f'This card gave away a guaranteed contract; {cards_text(keep)} kept it.'
                events.append(dict(n=row['n'], trick=t, card=row['card'], kind='gave_away', keep=sr['keep'],
                                   text=f'Trick {t}: {sym(c)} gave away the guaranteed contract; {cards_text(keep)} kept it.'))
            elif sr['mode'] == 'tricks' and sr['played'] < sr['guaranteed']:
                sr['text'] = (f'Before this card {_s(sr["guaranteed"])} were guaranteed; after it, {sr["played"]}. '
                              f'{cards_text(keep)} kept {sr["guaranteed"]}.')
                events.append(dict(n=row['n'], trick=t, card=row['card'], kind='sure_trick', keep=sr['keep'],
                                   text=f'Trick {t}: {sym(c)} dropped the guaranteed tricks from {sr["guaranteed"]} to '
                                        f'{sr["played"]}; {cards_text(keep)} kept {sr["guaranteed"]}.'))
            was_guaranteed = sr['played_makes']
        elif sr and not sr.get('unknown') and sr['kind'] == 'defending' and sr['handed_trick']:
            safe = cards_text([_card(k) for k in sr['safe']])
            if sr['handed_contract']:
                tail = f' ({_s(sr["declarer_after"])} against any layout)' if sr['mode'] == 'tricks' else ''
                sr['text'] = f'This card handed declarer a guaranteed making line{tail}; {safe} would not have.'
                events.append(dict(n=row['n'], trick=t, card=row['card'], kind='handed_contract', safe=sr['safe'],
                                   text=f'Trick {t}: {sym(c)} handed declarer a guaranteed making line{tail}; {safe} would not have.'))
            else:
                sr['text'] = (f'After this card declarer could guarantee {_s(sr["declarer_after"])}; after {safe}, '
                              f'{sr["lowest"]}.')
                events.append(dict(n=row['n'], trick=t, card=row['card'], kind='handed_trick', safe=sr['safe'],
                                   text=f'Trick {t}: {sym(c)} raised declarer\u2019s guaranteed tricks to {sr["declarer_after"]}; '
                                        f'after {safe}, {sr["lowest"]}.'))

        ch = row.get('chance')
        if ch and ch['kind'] == 'declaring' and ch['played'] < ch['best'] - 0.10:
            keep = [_card(k) for k in ch['keep']]
            ch['text'] = (f'By Sid\u2019s reading of the auction, a line starting with {cards_text(keep)} provably makes in at '
                          f'least {pct(ch["best"])} of layouts; the best provable line starting with this card, in at least '
                          f'{pct(ch["played"])}.')
            same = [e for e in events if e['n'] == row['n'] and e['kind'] in ('gave_away', 'sure_trick')]
            if same:
                same[0]['text'] += ' ' + ch['text']
            else:
                events.append(dict(n=row['n'], trick=t, card=row['card'], kind='chance_drop', keep=ch['keep'],
                                   text=f'Trick {t}, {sym(c)}: {ch["text"]}'))
        elif ch and ch['kind'] == 'defending' and ch['played'] > ch['lowest'] + 0.10:
            safe = cards_text([_card(k) for k in ch['safe']])
            ch['text'] = (f'By Sid\u2019s reading of the auction, after this card declarer had a line that provably makes in at '
                          f'least {pct(ch["played"])} of layouts; after {safe}, the best provable line made in at least '
                          f'{pct(ch["lowest"])}.')
            same = [e for e in events if e['n'] == row['n'] and e['kind'] in ('handed_contract', 'handed_trick')]
            if same:
                same[0]['text'] += ' ' + ch['text']
            else:
                events.append(dict(n=row['n'], trick=t, card=row['card'], kind='chance_handed', safe=ch['safe'],
                                   text=f'Trick {t}, {sym(c)}: {ch["text"]}'))

        if not row['loss']:
            continue
        seat = play[i][0]
        mover_decl = seat % 2 == decl_side
        if not row['focus']:
            who = controller(seat)
            given.append(dict(n=row['n'], trick=t, seat=row['seat'], by=names.get(who, SEAT_NAME[who]), card=row['card'],
                              loss=row['loss'], better=row['better'], side='declaring' if mover_decl else 'defending'))
            continue
        entry = dict(n=row['n'], trick=t, seat=row['seat'], card=row['card'], loss=row['loss'], better=row['better'],
                     dd_before=row['dd'], dd_after=row['dd'] - row['loss'] if mover_decl else row['dd'] + row['loss'])
        reasons = []
        if sr and sr.get('text'):
            entry['kind'] = 'sure' if sr['kind'] == 'declaring' else 'gift'
            reasons.append(sr['text'])
        elif sr and not sr.get('unknown') and sr['kind'] == 'declaring':
            if sr['mode'] == 'tricks':
                reasons.append(f'Not a sure-trick error: this card kept every guaranteed trick ({sr["guaranteed"]}).')
            elif sr['makes']:
                reasons.append('Not a sure-trick error: the contract stayed guaranteed after this card.')
            else:
                reasons.append('No line guaranteed the contract at this point.')
        elif sr and not sr.get('unknown'):
            reasons.append('Not a sure-trick error: this card gave declarer nothing sure that another card would have withheld.')
        if ch and ch.get('text'):
            entry.setdefault('kind', 'chance')
            reasons.append(ch['text'])
        if swap_clock.give(1) > 0:
            s = states[i]
            viewer = {declarer, dummy} if row['by'] == 'NESW'[declarer] else (
                {controller(seat), dummy} if (s.done_tricks or s.trick) else {controller(seat)})
            fixes, tried, complete = exchanges(dds, s, c, viewer, lim['swap_worlds'])
            allowed, where = fixes, None
            if chance_ok and fixes:
                try:
                    unseen = [x for x in range(4) if x not in viewer]
                    base = reader.layout_logw(s.hands, unseen, s.played, auction)
                    floor = math.log(lim['auction_ratio'])
                    allowed = [f for f in fixes if _exchanged_logw(reader, s, f, unseen, auction) - base >= floor]
                    marg = reader.marginals(s, unseen, s.played, auction, seed=row['n'])
                    where = (lambda card, seat: marg[card][seat]) if marg else None
                except Exception:
                    allowed, where = fixes, None
            kind, sentence = explain_exchanges(allowed, tried, ruled_out=len(fixes) - len(allowed), where=where)
            if sentence:
                entry.setdefault('kind', kind)
                entry['exchanges'] = dict(tried=tried, fixing=len(fixes), allowed=len(allowed), complete=complete, kind=kind)
                reasons.append(sentence)
        entry.setdefault('kind', 'unexplained')
        entry['text'] = ' '.join(reasons)
        lost.append(entry)

    analysed = [r for r in cards if r.get('sure')]
    chanced = [r for r in cards if r.get('chance')]
    return dict(version=VERSION, contract=contract, declarer='NESW'[declarer], need=need,
                focus=sorted('NESW'[s] for s in focus), focus_declares=focus_declares,
                dd_start=cards[0]['dd'] if cards else None, tricks=tricks,
                cards=cards, lost=lost, given=given, events=events,
                summary=_summary(cards, lost, given, focus_declares, tricks),
                engines=dict(sure=sure_ok, sure_cards=lim['sure_cards'], sure_need_cards=lim['sure_need_cards'],
                             sure_decisions=len(analysed), sure_unknown=sum(bool(r['sure'].get('unknown')) for r in analysed),
                             sure_skipped=skipped, sure_questions=sure.questions, sure_timeouts=sure.timeouts,
                             sure_seconds=round(sure.seconds, 2), auction=chance_ok,
                             auction_cards=lim['auction_cards'] if chance_ok else None, auction_decisions=len(chanced),
                             auction_skipped=chance_skipped, auction_seconds=round(reader.seconds, 2) if chance_ok else 0.,
                             seconds=round(time.perf_counter() - t0, 2)))


def _card(text):
    return 13 * SUITS.index(text[0]) + RANKS.index(text[1])


def _summary(cards, lost, given, focus_declares, tricks):
    """Trick accounting for the focus side: double-dummy tricks at the opening lead, tricks it lost, tricks its partner
    lost, tricks the other side gave back, tricks taken."""
    if not cards:
        return None
    start = cards[0]['dd']
    side = lambda decl_tricks: decl_tricks if focus_declares else 13 - decl_tricks
    own_side = 'declaring' if focus_declares else 'defending'
    return dict(side_start=side(start), side_end=side(tricks) if tricks is not None else None,
                lost=sum(e['loss'] for e in lost),
                partner_lost=sum(e['loss'] for e in given if e['side'] == own_side),
                gifts=sum(e['loss'] for e in given if e['side'] != own_side))


# ---- worker entry -----------------------------------------------------------------------------
_LOCAL = threading.local()       # one DDS context per thread (a DDS context must not be shared)


def init_worker(source, nice=0):
    """Analysis pool initializer: DDS comes from the bundle's source checkout; no models are loaded."""
    if nice:
        os.nice(nice)
    os.environ['BRIDGE_DDS_CACHE'] = ''
    if source and source not in sys.path:
        sys.path.insert(0, source)


def analyse_board(hands, contract, declarer, play, focus, names, limits=None, auction=None, scorer=None):
    """Pool entry point. hands: four lists of card ints; play: [(seat, card)]; names: {seat: label}; auction:
    dict(calls, dealer (seat), vul) and scorer: the bundle's hand-fit scorer file, to read the auction."""
    if getattr(_LOCAL, 'dds', None) is None:
        from bridge_harness.dds import DDS
        _LOCAL.dds = DDS(cache_path='')
    reader = None
    if auction and scorer and Path(scorer).is_file():
        try:
            from .auction import AuctionReader
            reader = AuctionReader(scorer)
        except Exception:
            reader = None
    return analyse([tuple(h) for h in hands], contract, declarer, [tuple(p) for p in play], focus,
                   actor_names={int(k): v for k, v in (names or {}).items()}, dds=_LOCAL.dds, limits=limits,
                   auction=auction if reader else None, reader=reader)
