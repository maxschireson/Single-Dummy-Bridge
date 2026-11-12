"""Card-play experience: what a partnership's finished boards say about its signals and its play.

Gen 9 work in progress (G9-S5; design: docs/gen9/signals.md section 5). Used by no arena bot.

After a board every hand is known, so each statistic is exact. Two kinds, in experience-v1 shapes:

  card.<key>   count. One occasion per play by the partnership's defenders in a situation where its
               descriptor gives a signal, holding two or more cards of the class, the message
               sendable. Labels: 'all/<n>' and 'hit/<n>' (the card the true fact prescribes was
               played), n = the number of messages (2) for a signal and the number of cards held in
               the suit for an opening lead; and the same with '/<s>' added, s = the class size.
  play.info    moment on FACTOR_GRID. One occasion per decision of ours that reads this partnership's
               plays: the gain in the true layout's log weight from those plays at each factor
               (scripts/gen8_play_info.py's measure). Written by whoever computes the gains.

Estimators shrink toward the profile: `honesty` (posterior mean and sd on a grid, Beta prior centred on
the profile's value, the reader's floor allowed for exactly through the class-size labels) and `phi`
(experience.grid_best with a prior curve peaked at the profile's factor).
"""
import math

import numpy as np

from . import experience as xp
from .core import Game
from .signals import MESSAGES, SPOT, SPOT_MASK, SUIT_MASK, facts, lead_table, pick, situation, spot_rules

FACTOR_GRID = (0., .1, .2, .3, .5, .75, 1., 1.25, 1.5)


def occasions(board, plays, model, side, allowed=None, detail=False):
    """[(full key, n, s, hit)] for the defenders of `side` (0 = North-South, 1 = East-West) on a finished board.
    `plays` is the board's (seat, card) sequence; `model` a signals.SignalModel for that partnership. With
    `allowed` ({ply: set of cards}), the class is cut to those cards (a bot's tie set: what it could choose among).
    With `detail`, each tuple also has the message the true hand called for (-1 for a lead) and where the card
    played stood in the class ('high', 'low' or 'mid').

    The class is the spots two to nine of the suit played, except for an opening lead, where it is every card held in
    the suit led, honours included (the lead convention chooses among them; signals.lead_table)."""
    c = board.contract
    out = []
    if c is None or not model:
        return out
    original = [set(h) for h in board.hands]
    history = []
    held = [set(h) for h in board.hands]
    for i, (seat, x) in enumerate(plays):
        history.append((seat, x))
        if seat % 2 == side and seat not in (c.declarer, c.dummy):
            sit = situation(history, i, c)
            kind = model.signal(sit[0]) if sit else None
            if kind not in (None, 'none'):
                key, suit = sit[0], x // 13
                lead = key == 'lead.opening'
                if lead or x % 13 <= SPOT:
                    K = np.zeros((1, 52), bool)
                    K[0, [y for y in held[seat] if y // 13 == suit and (lead or y % 13 <= SPOT)
                          and (allowed is None or y in allowed.get(i, ()))]] = True
                    s = int(K.sum())
                    if s >= 2:
                        orig = np.zeros((1, 52), bool)
                        orig[0, list(original[seat])] = True
                        led_suit = history[i - i % 4][1] // 13
                        if lead:
                            d = model.descriptor
                            table = lead_table(d.get('length_lead_vs_nt' if c.trump == 4 else 'length_lead_vs_suit', '4th'),
                                               d.get('lead_from_ak', 'ace'), d.get('honor_sequence_lead', 'top'))
                            bits = int(sum(1 << (y % 13) for y in held[seat] if y // 13 == suit))
                            prescribed, n = suit * 13 + int(table[bits]), s
                        else:
                            m = facts(kind, orig, suit, c.trump, led_suit)
                            prescribed = -1 if m is None else int(pick(K, spot_rules(kind, model.descriptor)[int(m[0])])[0])
                            n = len(MESSAGES[kind])
                        if prescribed >= 0:
                            row = (model.full_key(key, kind), n, s, x == prescribed)
                            if detail:
                                members = np.flatnonzero(K[0])
                                where = 'high' if x == members.max() else 'low' if x == members.min() else 'mid'
                                row += (-1 if lead else int(m[0]), where)
                            out.append(row)
        held[seat].discard(x)
    return out


def card_stats(board, plays, model, side):
    """{'card.<key>': count statistic} for one finished board."""
    tallies = {}
    for key, n, s, hit in occasions(board, plays, model, side):
        t = tallies.setdefault(f'card.{key}', {})
        for label in (f'all/{n}', f'all/{n}/{s}') + ((f'hit/{n}', f'hit/{n}/{s}') if hit else ()):
            t[label] = t.get(label, 0.) + 1.
    return {name: xp.count(**{k: v for k, v in t.items()}) for name, t in tallies.items()}


def honesty(stat, prior_mean=.8, prior_n=8., eps=.05, steps=400):
    """(posterior mean, posterior sd) of honesty h from a card.<key> count, where the prescribed card is played
    with probability (1 - eps) (h + (1 - h) / n) + eps / s. Uses the '/<s>' labels when present (exact for the
    reader's floor), else the aggregates with s = n. Prior Beta centred on `prior_mean`, worth `prior_n` occasions."""
    labels = (stat or {}).get('n', {})
    cells = {}
    labels = {k: v for k, v in labels.items() if k.split('/')[0] in ('hit', 'all')}
    for label, v in labels.items():
        parts = label.split('/')
        if len(parts) == 3:
            cells.setdefault((int(parts[1]), int(parts[2])), [0., 0.])[parts[0] == 'all'] += v
    if not cells:
        for label, v in labels.items():
            parts = label.split('/')
            if len(parts) == 2:
                cells.setdefault((int(parts[1]), int(parts[1])), [0., 0.])[parts[0] == 'all'] += v
    a = max(prior_mean * prior_n, 1e-3) + 1.
    b = max((1 - prior_mean) * prior_n, 1e-3) + 1.
    grid = (np.arange(steps) + .5) / steps
    logp = (a - 1) * np.log(grid) + (b - 1) * np.log(1 - grid)
    for (n, s), (hit, total) in cells.items():
        if total:
            p = (1 - eps) * (grid + (1 - grid) / n) + eps / s
            logp += hit * np.log(p) + (total - hit) * np.log(np.maximum(1 - p, 1e-300))
    w = np.exp(logp - logp.max())
    w /= w.sum()
    mean = float(w @ grid)
    return mean, float(math.sqrt(max(w @ (grid - mean) ** 2, 0.)))


def play_info(gains):
    """One occasion of play.info: the gains at each factor of FACTOR_GRID."""
    return xp.moment(FACTOR_GRID, gains)


def phi(stat, prior_phi=.3, prior_n=100., curvature=.01):
    """The factor with the best shrunk mean gain: experience.grid_best with a prior curve peaked at `prior_phi`
    (-curvature x (factor - prior_phi)^2 nats, worth `prior_n` occasions)."""
    if not stat:
        return prior_phi
    prior = [-curvature * (g - prior_phi) ** 2 for g in stat['grid']]
    return xp.grid_best(stat, prior, prior_n)[0]


def replay_plays(board, actions):
    """(seat, card) for every recorded play of a table's actions: a convenience for card_stats on records."""
    from .core import card
    game = Game(board)
    out = []
    for a in actions:
        if game.done:
            break
        o = game.observation()
        x = card(a['card'])
        game.play(x)
        out.append((o.actor, x))
    return out


def card_delta(player, key, board, plays, carding, side):
    """The experience-v1 delta of one finished board for the partnership on `side` (0 = North-South), from its declared
    carding (a carding block or descriptor): its card.<key> counts (honesty) and card.<key>.emit counts (emission
    tables). Empty stats when nothing is declared."""
    from .gen9_play import carding_parts
    from .signals import SignalModel
    descriptor, _ = carding_parts(carding)
    model = SignalModel(descriptor)
    if not model:
        return xp.delta(player, key, {})
    return xp.delta(player, key, dict(card_stats(board, plays, model, side), **emission_stats(board, plays, model, side)))


def emission_stats(board, plays, model, side):
    """{'card.<key>.emit': count} for one finished board: occasions by the message the true hand called for and where the
    card played stood in the class (labels 'm<message>/low', '/high', '/mid'). Spot signals only (no leads, no odd-even)."""
    tallies = {}
    for key, n, s, hit, message, where in occasions(board, plays, model, side, detail=True):
        if message < 0 or key.endswith('odd_even'):
            continue
        t = tallies.setdefault(f'card.{key}.emit', {})
        t[f'm{message}/{where}'] = t.get(f'm{message}/{where}', 0.) + 1.
    return {name: xp.count(**t) for name, t in tallies.items()}


def emission(stat, messages=2, alpha=10.):
    """[[P(low), P(high), P(middle)] per message] from a card.<key>.emit count: each message's counts shrunk toward the
    pooled positions (no signal) with weight `alpha`. Middle counts come only from classes of three or more cards, so this
    slightly understates the middle where classes of two are common; the reader renormalises low and high for those."""
    n = (stat or {}).get('n', {})
    counts = np.array([[n.get(f'm{m}/{w}', 0.) for w in ('low', 'high', 'mid')] for m in range(messages)])
    pooled = counts.sum(axis=0)
    prior = (pooled + 1.) / (pooled.sum() + 3.)
    rows = (counts + alpha * prior) / (counts.sum(axis=1, keepdims=True) + alpha)
    return rows.tolist()
