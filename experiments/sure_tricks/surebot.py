"""Wrapper that applies one rule on top of any declarer: a card that guarantees the contract against
every split of the unseen cards (sure.Sure, nothing pinned) is preferred to a card that does not.

Among guaranteeing cards the base player's own ranking decides. Where no card guarantees the contract,
or the position is still too large to search (`max_left`, `max_nodes`), the base player's card stands.
"""
from fusionlab import Decision, symbol
from sure import Sure


class TooBig(Exception):
    pass


class Capped(Sure):
    cap = 4_000_000

    def _can(self, need, *state):
        if self.nodes > self.cap:
            raise TooBig
        return super()._can(need, *state)


def view(o):
    """Declarer's knowledge from an Observation: his two hands, the unseen pool, counts and show-outs."""
    side = o.contract.declarer % 2
    decl = [s for s in range(4) if s % 2 == side]
    defs = [s for s in range(4) if s % 2 != side]
    played = {c for _, c in o.history}
    seen = played | {c for s in decl for c in o.known_hands[s]}
    pool = [c for c in range(52) if c not in seen]
    counts = {s: 13 - sum(1 for x, _ in o.history if x == s) for s in defs}
    voids = {}
    for i, (seat, c) in enumerate(o.history):
        led = o.history[i - i % 4][1] // 13
        if c // 13 != led and seat in defs:
            voids.setdefault(seat, set()).add(led)
    return dict(hands={s: o.known_hands[s] for s in decl}, pool=pool, counts=counts, trump=o.contract.trump,
                leader=o.leader, trick=o.trick, side=side, voids=voids)


class SureFirst:
    def __init__(self, base, max_left=9, max_nodes=4_000_000):
        self.base, self.max_left, self.max_nodes = base, max_left, max_nodes

    def choose(self, o, rng):
        d = self.base.choose(o, rng)
        left = 13 - len(o.history) // 4
        if len(o.legal) == 1 or o.actor % 2 != o.contract.declarer % 2 or left > self.max_left:
            return d
        need = o.contract.level + 6 - o.declarer_tricks
        if need <= 0:
            return d
        s = Capped(**view(o))
        s.cap = self.max_nodes
        a, b = s.decl
        good = []
        try:
            for c in o.legal:
                ha, hb = s.h0[a], s.h0[b]
                if o.actor == a:
                    ha &= ~(1 << c)
                else:
                    hb &= ~(1 << c)
                if s._next(need, ha, hb, s.pool0, s.cnt0, s.void0, s.known0, s.trick0, s.leader0, o.actor, c):
                    good.append(c)
        except TooBig:
            return Decision(d.card, dict(d.details, sure='too big'))
        note = dict(d.details, sure=[symbol(c) for c in good], sure_nodes=s.nodes)
        if not good or d.card in good:
            return Decision(d.card, note)
        est = d.details.get('estimates') or {}
        pick = max(good, key=lambda c: (est.get(symbol(c), {}).get('utility', 0), -(c % 13)))
        return Decision(pick, dict(note, sure_override=symbol(d.card)))
