"""Strategy-fusion lab: oracle defender, table runner and bot factories on top of bridge_harness.

Seats N,E,S,W = 0..3, suits SHDC, card = 13*suit + rank (2..A = 0..12), as in bridge_harness.core.
"""
import json
import os
import random
import sys
from pathlib import Path

os.environ.setdefault('BRIDGE_DDS_CACHE', '')
ROOT = Path(os.environ.get('SDB_ROOT', Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT))

from bridge_harness.core import Board, Game, SEATS, SUITS, card, symbol, winner   # noqa: E402
from bridge_harness.dds import DDS                                                 # noqa: E402
from bridge_harness.players import Decision, PIMCPlayer                            # noqa: E402
from bridge_harness.runner import play_table                                       # noqa: E402

SCORER = 'models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz'
GEN5_POLICY = 'models/cardplay/gen5-2026-11-10/policy.npz'
GEN7_POLICY = 'models/cardplay/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz'
# scripts/gen7_check.py: "the live 6-32 after the lead"
FAST = dict(lead_source='scorer', mid_from_trick=14, mid_samples=32, list_from_trick=7, list_solve=256)


def gen_spec(engine, **gen7):
    s = dict(id='6-32' if engine == 'gen6' else '7s-32', engine=engine, samples=32, near_tie=0., exploration=0.,
             policy=GEN5_POLICY, scorer=SCORER, gen6=dict(FAST))
    if engine == 'gen7':
        s.update(gen7_policy=str(ROOT / GEN7_POLICY), gen7=gen7)
    return s


def make_bot(name):
    """pimc-make / pimc-tricks / pimc-score (uniform layouts, the repo's PIMCPlayer), gen6 (local 6-32),
    gen7 (7s-32 block of configs/round7-candidate-phase1.json), gen7-notree."""
    if name.startswith('pimc-'):
        _, objective, *rest = name.split('-')
        return PIMCPlayer(samples=int(rest[0]) if rest else 32, objective=objective)
    from bridge_harness.gen7 import Gen7Player, player, resolved
    if name == 'gen6':
        return player(gen_spec('gen6'), ROOT)
    block = json.loads((ROOT / 'configs/round7-candidate-phase1.json').read_text())['gen7_bots']['7s-32']['gen7']
    if name == 'gen7-notree':
        block = {k: v for k, v in block.items() if k != 'tree'}
    elif name != 'gen7':
        raise ValueError(name)
    return Gen7Player(gen_spec('gen7', **resolved(block)), ROOT)


class OracleDefender:
    """Sees all four hands. Card choice, in order:

      1. double-dummy optimal on the true deal;
      2. among those, best for the defence in the "denied" deal: the true deal with each `critical`
         card still in a defender's hand exchanged with the highest card of its suit that declarer
         or dummy still holds above it (the queen becomes the ace; once the ace is gone, the king).
         Double dummy on the true deal assumes declarer guesses right, so once the contract is
         'cold' that way every defensive card looks equal and a plain DD defender throws tricks
         away. In the denied deal the guess cannot succeed, which shows what those cards cost
         against a declarer who still has to guess;
      3. on lead, not an `avoid` suit; when discarding, a card that can be spared (the defender
         stays as long in the suit as the longer of declarer and dummy; in an `avoid` suit the
         partner of the critical card's holder has only idle cards), other suits before `avoid` suits;
      4. lowest card.
    """
    def __init__(self, board, avoid=(), dds=None, critical=()):
        self.board, self.avoid = board, {SUITS.index(s) for s in avoid}
        self.dds = dds or DDS(cache_path='')
        self.critical = [card(x) if isinstance(x, str) else x for x in critical]
        self.side = board.contract.declarer % 2

    def hands(self, o):
        played = {c for _, c in o.history}
        return tuple(tuple(c for c in h if c not in played) for h in self.board.hands)

    def denied(self, hands):
        """Card exchange (dict) that promotes each live critical card, or {} if none applies."""
        swap = {}
        for x in self.critical:
            if not any(x in hands[s] for s in range(4) if s % 2 != self.side):
                continue
            above = [c for s in range(4) if s % 2 == self.side for c in hands[s]
                     if c // 13 == x // 13 and c > x and c not in swap]
            if above:
                h = max(above)
                swap[x], swap[h] = h, x
        return swap

    def choose(self, o, rng):
        if len(o.legal) == 1:
            return Decision(o.legal[0], {'forced': True})
        hands = self.hands(o)
        v = self.dds.solve(hands, o.contract.trump, o.leader, o.trick)[0]
        best = max(v[c] for c in o.legal)
        cands = [c for c in o.legal if v[c] == best]
        second = {c: 0 for c in cands}
        swap = self.denied(hands) if len(cands) > 1 else {}
        if swap:
            m = lambda c: swap.get(c, c)
            dv = self.dds.solve(tuple(tuple(sorted(m(c) for c in h)) for h in hands), o.contract.trump, o.leader, o.trick)[0]
            second = {c: dv[m(c)] for c in cands}
        leading = not o.trick
        discarding = bool(o.trick) and o.legal[0] // 13 != o.trick[0][1] // 13
        me = hands[o.actor]
        holder = {x // 13 for x in self.critical if x in me}

        def spare(suit):
            """Cards of this suit the defender can let go and still match declarer's and dummy's length."""
            mine = sum(1 for c in me if c // 13 == suit)
            if suit in self.avoid and suit not in holder:
                return mine                                 # partner holds the critical card: these are idle
            theirs = max(sum(1 for c in hands[s] if c // 13 == suit) for s in range(4) if s % 2 == self.side)
            return mine - theirs

        def key(c):
            suit = c // 13
            if leading:
                return (-second[c], suit in self.avoid, c % 13, suit)
            if discarding and suit != o.contract.trump:
                return (-second[c], spare(suit) <= 0, suit in self.avoid, c % 13, suit)
            return (-second[c], c % 13, suit)
        c = min(cands, key=key)
        return Decision(c, {'oracle': True, 'dd_equal': len(cands)})


def tricks_text(actions):
    out = []
    for i in range(0, len(actions), 4):
        out.append(' '.join(a['seat'] + ':' + a['card'] for a in actions[i:i + 4]))
    return out


def run(board, bot, avoid=(), seed=1, prefix=(), dds=None, name='decl', critical=()):
    """Bot plays declarer and dummy; the oracle defends. Returns the table dict of runner.play_table."""
    d = board.contract.declarer
    assign = ['def'] * 4
    assign[d] = assign[(d + 2) % 4] = name
    t = play_table(board, assign, {name: bot, 'def': OracleDefender(board, avoid, dds, critical)}, seed=seed, prefix=prefix)
    if t['status'] != 'ok':
        raise RuntimeError(t.get('traceback'))
    return t


def first_touch(table, suit):
    """(trick number, seat) of the first card led in `suit`, or None."""
    s = suit if isinstance(suit, str) else SUITS[suit]
    for i in range(0, len(table['actions']), 4):
        a = table['actions'][i]
        if a['card'][0] == s:
            return i // 4 + 1, a['seat']
    return None


def dd_tricks(board, dds=None):
    """Declarer's double-dummy tricks on the true deal after the fixed opening lead (or the best lead)."""
    dds = dds or DDS(cache_path='')
    g = Game(board)
    if board.opening_lead is not None:
        g.play(board.opening_lead)
    o = g.observation()
    v = dds.solve(tuple(tuple(h) for h in g.hands), o.contract.trump, o.leader, o.trick)[0]
    declaring = o.actor % 2 == o.contract.declarer % 2
    return max(v.values()) if declaring else 13 - max(v.values())
