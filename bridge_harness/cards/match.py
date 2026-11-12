"""Card-to-profile distance, call likelihoods per profile, and system detection (Gen 9 WIP, G9-B4).

Distance (architecture 3): bid deals with a profile's generator and count, over the calls a
card covers, how often the card's first fitting rule is not the call made, by family. Families
whose break rate passes a threshold are the card's *residual* against that profile: where the
filter should speak even when the profile matches. Families with too few calls to measure stay
read (residual_block); calls where only the card's catch-all fits are counted apart (`silent`).

Detection (architecture 5): once a board is over all hands are known, so the likelihood of a
pair's calls under a profile is a likelihood of calls given hands:

    deterministic generator (rule bidder, a compiled card's bidder):
        P(c | h) = (1 - eps) [generator calls c] + eps / (number of legal calls)
    bidding net:  P(c | h) = (1 - eps) softmax_net(c) + eps / (number of legal calls)
    unknown:      P(c | h) = (1 - mix) softmax_reference(c) + mix / (number of legal calls)

Per board and pair these are summed into the experience statistic `profile` (a loglik), and
``experience.posterior`` turns the sums into a probability over profiles.
"""
from collections import Counter, defaultdict
import random

import numpy as np

from ..bidding_env import CALL_ID, CALLS
from .context import Context
from .features import features_of_hands
from .system import CardSystem

VULS = ('None', 'NS', 'EW', 'Both')


# ---- distance ------------------------------------------------------------------------------------
def card_distance(card, bid_deal, deals=1000, seed=0, residual_at=0.10):
    """Break rate of a generator against a card over covered calls.

    bid_deal(hands, dealer, vul) -> calls (strings) for one deal, all four seats bid by the profile.
    Returns {'rate', 'covered', 'calls', 'by_family': {family: [breaks, covered]}, 'residual': [...]}."""
    system = card if isinstance(card, CardSystem) else CardSystem(card)
    rng = random.Random(seed)
    tally = defaultdict(Counter)
    covered = total = skipped = silent = 0
    for i in range(deals):
        deck = list(range(52))
        rng.shuffle(deck)
        hands = [sorted(deck[13 * k:13 * k + 13]) for k in range(4)]
        dealer, vul = i % 4, VULS[(i // 4) % 4]
        try:
            calls = bid_deal(hands, dealer, vul)
        except (ValueError, IndexError):
            skipped += 1
            continue
        for t, call in enumerate(calls):
            seat = (dealer + t) % 4
            total += 1
            rules = system.rules(Context.make(calls[:t], dealer, seat, vul))
            if rules is None:
                continue
            covered += 1
            f = features_of_hands([hands[seat]])
            first = next(r for r in rules if r.pred.dist(f)[0] == 0)
            if first.family == 'catch':                   # the card is silent on this hand here: not a contradiction
                silent += 1
                covered -= 1
                continue
            tally[first.family]['break' if first.call != call else 'ok'] += 1
    nb = sum(c['break'] for c in tally.values())
    by = {k: [c['break'], c['break'] + c['ok']] for k, c in sorted(tally.items())}
    measured = sorted(k for k, (b, n) in by.items() if n >= 20)
    residual = sorted(k for k in measured if by[k][0] / by[k][1] > residual_at)
    return dict(rate=nb / max(covered, 1), covered=covered, calls=total, by_family=by, measured=measured, residual=residual,
                silent=silent, skipped_deals=skipped)


def residual_block(distance):
    """A card document's residual entry for one profile, from card_distance: families read under that profile are the
    residual ones and every family not measured (believe the declaration where nothing says otherwise)."""
    return {'residual': list(distance['residual']), 'measured': list(distance['measured'])}


# ---- call likelihoods ----------------------------------------------------------------------------
def legal_tokens(calls, dealer, seat, vul):
    return [CALL_ID[c] for c in Context.make(calls, dealer, seat, vul).legal]


class DeterministicProfile:
    """A generator that makes one call: anything with call(hand, seat, dealer, vul_index, tokens) -> token."""

    def __init__(self, name, bidder, eps=0.05):
        self.name, self.bidder, self.eps = name, bidder, eps

    def call_probs(self, hands, dealer, vul, calls, seats):
        out = []
        for t, c in enumerate(calls):
            seat = (dealer + t) % 4
            if seat not in seats:
                continue
            legal = legal_tokens(calls[:t], dealer, seat, vul)
            try:
                tok = self.bidder.call(hands[seat], seat, dealer, VULS.index(vul), [CALL_ID[x] for x in calls[:t]])
            except (ValueError, IndexError):
                tok = None
            p = {x: self.eps / len(legal) for x in legal}
            if tok in p:
                p[tok] += 1 - self.eps
            else:
                p = {x: 1 / len(legal) for x in legal}
            out.append((p, CALL_ID[c], len(legal)))
        return out

    def call_log_probs(self, hands, dealer, vul, calls, seats):
        return [np.log(p.get(c, 1e-300)) for p, c, n in self.call_probs(hands, dealer, vul, calls, seats)]


def lstm_step_logits(b, sess, rows, calls, turn):
    """One recurrent step of a BEN-format LSTM session (as system_bidders._LstmSession.act), returning logits."""
    from ..system_bidders import _sigmoid
    u = b.units
    ar = np.arange(len(rows))
    z = sess.gates[rows].copy()
    for back in range(4):
        pos = turn - 4 + back
        z += b.w_ctx[40 * back + np.where(pos >= 0, calls[ar, np.maximum(pos, 0)], 0)]
    inp = None
    for layer, ((w, rec, bias), (scale, shift)) in enumerate(zip(b.lstm, b.bn)):
        if layer:
            z = inp @ w
        z = z + bias + sess.h[rows, layer] @ rec
        c = _sigmoid(z[:, u:2 * u]) * sess.c[rows, layer] + _sigmoid(z[:, :u]) * np.tanh(z[:, 2 * u:3 * u])
        h = _sigmoid(z[:, 3 * u:]) * np.tanh(c)
        sess.h[rows, layer], sess.c[rows, layer] = h, c
        inp = h * scale + shift
    return inp @ b.wd + b.bd


class NetProfile:
    """A BEN-format LSTM bidder read as a call distribution, teacher-forced on the actual auction."""

    def __init__(self, name, path, eps=0.05, temperature=1.0):
        from ..system_bidders import BenLstmBidder
        self.name, self.b, self.eps, self.temperature = name, BenLstmBidder(path), eps, temperature

    def call_probs(self, hands, dealer, vul, calls, seats):
        """Per call of `seats`: the softmax over legal calls (as a dict token -> p)."""
        sess = {s: self.b.session(np.array([hands[s]]), np.array([s]), np.array([dealer]), np.array([VULS.index(vul)])) for s in seats}
        row = np.full((1, 64), -1, np.int64)
        toks = [CALL_ID[c] for c in calls]
        row[0, :len(toks)] = toks
        out = []
        for t, c in enumerate(calls):
            seat = (dealer + t) % 4
            if seat not in seats:
                continue
            logits = lstm_step_logits(self.b, sess[seat], np.array([0]), row, np.array([t]))[0] / self.temperature
            legal = legal_tokens(calls[:t], dealer, seat, vul)
            z = logits[legal]
            z = np.exp(z - z.max())
            out.append((dict(zip(legal, z / z.sum())), CALL_ID[c], len(legal)))
        return out

    def call_log_probs(self, hands, dealer, vul, calls, seats):
        return [np.log((1 - self.eps) * p.get(c, 0.0) + self.eps / n) for p, c, n in self.call_probs(hands, dealer, vul, calls, seats)]


class UnknownMixture:
    """`unknown` as some other system that bids sometimes like each candidate: the per-call average of the
    candidates' distributions, mixed with uniform."""

    def __init__(self, candidates, mix=0.2, name='unknown'):
        self.name, self.cands, self.mix = name, list(candidates), mix

    def call_log_probs(self, hands, dealer, vul, calls, seats):
        per = [p.call_probs(hands, dealer, vul, calls, seats) for p in self.cands]
        out = []
        for k in range(len(per[0])):
            c, n = per[0][k][1], per[0][k][2]
            avg = np.mean([d[k][0].get(c, 0.0) for d in per])
            out.append(np.log((1 - self.mix) * avg + self.mix / n))
        return out


class UnknownProfile:
    """A broad call model: a reference net, mixed with uniform."""

    def __init__(self, reference, mix=0.5, name='unknown'):
        self.name, self.ref, self.mix = name, reference, mix

    def call_log_probs(self, hands, dealer, vul, calls, seats):
        return [np.log((1 - self.mix) * p.get(c, 0.0) + self.mix / n) for p, c, n in self.ref.call_probs(hands, dealer, vul, calls, seats)]


def board_loglik(profiles, hands, dealer, vul, calls, seats):
    """{profile name: summed log P of the calls made by `seats`} for one finished board."""
    return {p.name: float(np.sum(p.call_log_probs(hands, dealer, vul, calls, seats))) for p in profiles}


def experience_delta(player, key, loglik):
    """The experience-v1 delta for the profile evidence of one board (G9-A2 statistic 'profile')."""
    from .. import experience as E
    return E.delta(player, key, {'profile': E.loglik(**loglik)})


def boards_to_identify(ll, truth, threshold=0.95, prior=None, orderings=200, seed=0):
    """Boards until the probability of `truth` first stays at or above `threshold`, over random orderings.

    ll: (boards, candidates) log-likelihoods; columns in the order of `prior` (dict name -> p) or uniform.
    Returns a list per ordering (None if never reached)."""
    names = list(prior) if prior else None
    ll = np.asarray(ll, float)
    k = ll.shape[1]
    logp0 = np.log(np.array([prior[n] for n in names])) if prior else np.full(k, -np.log(k))
    ti = truth
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(orderings):
        order = rng.permutation(len(ll))
        cum = logp0 + np.cumsum(ll[order], axis=0)
        cum -= cum.max(1, keepdims=True)
        post = np.exp(cum)
        post /= post.sum(1, keepdims=True)
        ok = post[:, ti] >= threshold
        if not ok[-1]:
            out.append(None)
            continue
        bad = np.flatnonzero(~ok)
        out.append(int(bad[-1]) + 2 if len(bad) else 1)
    return out
