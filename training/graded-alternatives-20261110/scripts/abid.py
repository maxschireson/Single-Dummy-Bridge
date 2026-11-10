"""Vectorised bidding simulator, alternative-call grader and trainer.

Rules, scoring, feature encoding and model loading come from the user's harness
(bridge_harness.core / bidding_env / bidding_ppo); this module only adds a fast
batched implementation of the same things and is checked against them in selfcheck.py.
"""
import gzip
import json
import sys

import numpy as np

sys.path.insert(0, '/home/claude/gen5r')
from bridge_harness import core  # noqa: E402
from bridge_harness.bidding_env import BidObservation, encode as h_encode  # noqa: E402

PASS, DBL, RDBL, FIRST_BID = 2, 3, 4, 5
IMP_LIMITS = np.array(core.IMP_LIMITS)
# strain order inside call ids is C, D, H, S, N; DD table rows are S, H, D, C, NT
ROW_OF_STRAIN = np.array([3, 2, 1, 0, 4])
SEAT = {'N': 0, 'E': 1, 'S': 2, 'W': 3}


def _score_table():
    t = np.zeros((7, 5, 3, 2, 14), np.int32)
    for level in range(1, 8):
        for s, strain in enumerate('CDHSN'):
            for dbl in range(3):
                c = core.Contract(level, strain, 0, dbl)
                for vul in (0, 1):
                    for tricks in range(14):
                        t[level - 1, s, dbl, vul, tricks] = core.score(c, tricks, bool(vul))
    return t


SCORE = _score_table()


def imps(diff):
    diff = np.asarray(diff)
    return np.sign(diff) * np.searchsorted(IMP_LIMITS, np.abs(diff), side='right')


class Deals:
    """Hands, dealer, vulnerability, DD table and the 33 static input features per seat."""

    def __init__(self, hands, dealer, vul, table):
        self.hands = hands                      # list of 4 tuples of card ints (harness encoding)
        self.dealer = np.asarray(dealer, np.int64)
        self.vul = list(vul)
        self.table = np.asarray(table, np.int64)  # (N, 5, 4): rows S,H,D,C,NT; columns N,E,S,W
        n = len(hands)
        self.static = np.zeros((n, 4, 33), np.float32)
        self.vulflag = np.zeros((n, 4), np.int64)
        for i in range(n):
            for seat in range(4):
                obs = BidObservation(tuple(hands[i][seat]), seat, seat, self.vul[i], ())
                self.static[i, seat] = h_encode(obs)[0, :33]
                self.vulflag[i, seat] = core.vulnerable(self.vul[i], seat)

    def __len__(self):
        return len(self.hands)

    def subset(self, idx):
        d = object.__new__(Deals)
        idx = np.asarray(idx)
        d.hands = [self.hands[i] for i in idx]
        d.dealer, d.vul = self.dealer[idx], [self.vul[i] for i in idx]
        d.table, d.static, d.vulflag = self.table[idx], self.static[idx], self.vulflag[idx]
        return d

    @classmethod
    def from_export(cls, path, limit=None):
        """The user's uploaded format: PBN hands NESW, dealer letter, dds rows S,H,D,C,NT."""
        rows = [json.loads(line) for line in gzip.open(path)]
        if limit:
            rows = rows[:limit]
        return cls([tuple(core.parse_hand(h) for h in r['hands']) for r in rows],
                   [SEAT[r['dealer']] for r in rows], [r['vulnerability'] for r in rows],
                   [r['dds'] for r in rows])

    @classmethod
    def from_solved(cls, path, limit=None):
        """Output of solve_tables.py: hands as card ints, dealer as int."""
        rows = sorted((json.loads(line) for line in open(path)), key=lambda r: r['index'])
        if limit:
            rows = rows[:limit]
        return cls([tuple(tuple(h) for h in r['hands']) for r in rows], [r['dealer'] for r in rows],
                   [r['vulnerability'] for r in rows], [r['dds'] for r in rows])


class Auctions:
    """State of M auctions as arrays. `deal` indexes a Deals object; `side` is the learner's side (0 NS, 1 EW)."""

    WIDTH = 48

    def __init__(self, deals, deal, side):
        m = len(deal)
        self.deals = deals
        self.deal = np.asarray(deal, np.int64)
        self.side = np.asarray(side, np.int64)
        self.dealer = deals.dealer[self.deal]
        self.calls = np.zeros((m, self.WIDTH), np.int8)
        self.n = np.zeros(m, np.int64)
        self.last = np.full(m, -1, np.int64)
        self.last_seat = np.zeros(m, np.int64)
        self.doubled = np.zeros(m, np.int64)
        self.passes = np.zeros(m, np.int64)
        self.first = np.full((m, 2, 5), -1, np.int64)
        self.done = np.zeros(m, bool)

    def __len__(self):
        return len(self.deal)

    def clone(self, idx):
        a = object.__new__(Auctions)
        a.deals = self.deals
        for name in ('deal', 'side', 'dealer', 'calls', 'n', 'last', 'last_seat', 'doubled', 'passes', 'first', 'done'):
            setattr(a, name, getattr(self, name)[idx].copy())
        return a

    def seat(self, idx):
        return (self.dealer[idx] + self.n[idx]) % 4

    def legal(self, idx):
        seat = self.seat(idx)
        last, dbl = self.last[idx], self.doubled[idx]
        same_side = (seat % 2) == (self.last_seat[idx] % 2)
        mask = np.zeros((len(idx), 40), bool)
        mask[:, PASS] = True
        mask[:, DBL] = (last >= 0) & (dbl == 0) & ~same_side
        mask[:, RDBL] = (dbl == 1) & same_side
        mask[:, FIRST_BID:] = np.arange(35)[None, :] > last[:, None]
        return mask

    def inputs(self, idx):
        """Padded (B, T, 193) features and lengths for the player to act in each listed auction."""
        idx = np.asarray(idx)
        n = self.n[idx]
        seat = self.seat(idx)
        length = n // 4 + 1
        t_max = int(length.max())
        b = len(idx)
        if int(n.max()) + 4 > self.calls.shape[1] + 4:
            raise RuntimeError('auction longer than buffer')
        padded = np.concatenate([np.zeros((b, 4), np.int8), self.calls[idx]], axis=1)
        pos = (n % 4)[:, None, None] + 4 * np.arange(t_max)[None, :, None] + np.arange(4)[None, None, :]
        valid = np.arange(t_max)[None, :] < length[:, None]
        pos = np.minimum(pos, padded.shape[1] - 1)
        tok = padded[np.arange(b)[:, None, None], pos].astype(np.int64)
        x = np.zeros((b, t_max, 193), np.float32)
        x[:, :, :33] = self.deals.static[self.deal[idx], seat][:, None, :] * valid[:, :, None]
        bi, ti = np.nonzero(valid)
        for j in range(4):
            x[bi, ti, 33 + 40 * j + tok[bi, ti, j]] = 1.0
        return x, length.astype(np.int32)

    def apply(self, idx, action):
        idx = np.asarray(idx)
        action = np.asarray(action, np.int64)
        if not len(idx):
            return
        seat = self.seat(idx)
        n = self.n[idx]
        if int(n.max()) >= self.calls.shape[1]:
            grow = np.zeros((len(self.deal), self.calls.shape[1]), np.int8)
            self.calls = np.concatenate([self.calls, grow], axis=1)
        self.calls[idx, n] = action
        is_pass, is_x, is_xx, is_bid = action == PASS, action == DBL, action == RDBL, action >= FIRST_BID
        self.passes[idx] = np.where(is_pass, self.passes[idx] + 1, 0)
        self.doubled[idx] = np.where(is_x, 1, np.where(is_xx, 2, np.where(is_bid, 0, self.doubled[idx])))
        bid_i = idx[is_bid]
        if len(bid_i):
            order = action[is_bid] - FIRST_BID
            s_side, strain = seat[is_bid] % 2, order % 5
            cur = self.first[bid_i, s_side, strain]
            self.first[bid_i, s_side, strain] = np.where(cur < 0, seat[is_bid], cur)
            self.last[bid_i] = order
            self.last_seat[bid_i] = seat[is_bid]
        self.n[idx] = n + 1
        self.done[idx] = self.passes[idx] >= np.where(self.last[idx] < 0, 4, 3)

    def ns_score(self):
        """NS score of each finished auction from the DD table (0 when passed out)."""
        out = np.zeros(len(self.deal), np.int64)
        c = np.nonzero(self.last >= 0)[0]
        level, strain = self.last[c] // 5, self.last[c] % 5
        declarer = self.first[c, self.last_seat[c] % 2, strain]
        tricks = self.deals.table[self.deal[c], ROW_OF_STRAIN[strain], declarer]
        vul = self.deals.vulflag[self.deal[c], declarer]
        s = SCORE[level, strain, self.doubled[c], vul, tricks]
        out[c] = np.where(declarer % 2 == 0, s, -s)
        return out

    def call_text(self, i):
        from bridge_harness.bidding_env import CALLS
        return [CALLS[int(c)] for c in self.calls[i, :self.n[i]]]


def forward(policy, x, lengths, chunk=4096):
    out = []
    for s in range(0, len(x), chunk):
        p, _ = policy.forward(x[s:s + chunk], lengths[s:s + chunk])
        out.append(p.numpy())
    return np.concatenate(out) if out else np.zeros((0, 40), np.float32)


def masked(p, mask):
    q = np.maximum(p, 1e-12) * mask
    return q / q.sum(axis=1, keepdims=True)


def run_greedy(auc, learner, opponent, on_learner=None, chunk=4096):
    """Play every unfinished auction to the end with greedy calls.

    Seats on auc.side use `learner`, the others `opponent`.
    on_learner(idx, probs, mask, action) is called for each batch of learner decisions before they are applied.
    """
    while True:
        active = np.nonzero(~auc.done)[0]
        if not len(active):
            return
        seat = auc.seat(active)
        learning = (seat % 2) == auc.side[active]
        for flag, policy in ((True, learner), (False, opponent)):
            idx = active[learning == flag]
            if not len(idx):
                continue
            x, lengths = auc.inputs(idx)
            mask = auc.legal(idx)
            p = masked(forward(policy, x, lengths, chunk), mask)
            action = p.argmax(axis=1)
            if flag and on_learner is not None:
                on_learner(idx, p, mask, action)
            auc.apply(idx, action)


def duplicate(deals, candidate, opponent, chunk=4096):
    """Two rooms per deal, greedy. Returns per-deal IMPs for the candidate and both rooms' auctions."""
    n = len(deals)
    auc = Auctions(deals, np.concatenate([np.arange(n), np.arange(n)]),
                   np.concatenate([np.zeros(n, np.int64), np.ones(n, np.int64)]))
    run_greedy(auc, candidate, opponent, chunk=chunk)
    ns = auc.ns_score()
    return imps(ns[:n] - ns[n:]), auc


def summary(x):
    x = np.asarray(x, float)
    n = len(x)
    return dict(n=n, total=float(x.sum()), mean=float(x.mean()), se=float(x.std(ddof=1) / np.sqrt(n)),
                wins=int((x > 0).sum()), losses=int((x < 0).sum()), ties=int((x == 0).sum()))


def grade(deals, learner, opponent, threshold=0.01, max_alts=4, chunk=4096, keep_frac=0.0, seed=0):
    """Baseline greedy auctions in both rooms plus a rollout of every plausible alternative learner call.

    Returns the baseline auctions and a dict of arrays, one row per learner decision that has at least
    one alternative: auction index, call count before the decision, greedy call, the learner's own
    probabilities, alternative calls (padded with -1) and their IMP gain over the greedy line.
    """
    n = len(deals)
    base = Auctions(deals, np.concatenate([np.arange(n), np.arange(n)]),
                    np.concatenate([np.zeros(n, np.int64), np.ones(n, np.int64)]))
    rec = dict(auction=[], n=[], greedy=[], probs=[], mask=[])
    alt_parent, alt_slot, alt_call, alt_snap = [], [], [], []
    count = [0]
    seen = [0]
    rng = np.random.default_rng(seed)

    def on_learner(idx, p, mask, action):
        seen[0] += len(idx)
        q = p.copy()
        q[np.arange(len(idx)), action] = 0.0
        order = np.argsort(-q, axis=1)[:, :max_alts]
        top = np.take_along_axis(q, order, axis=1)
        keep = top >= threshold
        has = keep.any(axis=1)
        if keep_frac > 0:
            has = has | (rng.random(len(idx)) < keep_frac)
        if not has.any():
            return
        rows = np.nonzero(has)[0]
        ids = count[0] + np.arange(len(rows))
        count[0] += len(rows)
        rec['auction'].append(idx[rows]); rec['n'].append(base.n[idx[rows]].copy())
        rec['greedy'].append(action[rows]); rec['probs'].append(p[rows].astype(np.float32)); rec['mask'].append(mask[rows])
        r, k = np.nonzero(keep[rows])
        if not len(r):
            return
        snap = base.clone(idx[rows][r])
        snap.apply(np.arange(len(r)), order[rows][r, k])
        alt_parent.append(ids[r]); alt_slot.append(k); alt_call.append(order[rows][r, k]); alt_snap.append(snap)

    run_greedy(base, learner, opponent, on_learner, chunk)
    base_ns = base.ns_score()
    d = count[0]
    out = dict(auction=np.concatenate(rec['auction']), n=np.concatenate(rec['n']), greedy=np.concatenate(rec['greedy']),
               probs=np.concatenate(rec['probs']), mask=np.concatenate(rec['mask']),
               alt=np.full((d, max_alts), -1, np.int64), adv=np.zeros((d, max_alts), np.float32))
    parent, slot, call = np.concatenate(alt_parent), np.concatenate(alt_slot), np.concatenate(alt_call)
    pool = object.__new__(Auctions)
    pool.deals = deals
    for name in ('deal', 'side', 'dealer', 'calls', 'n', 'last', 'last_seat', 'doubled', 'passes', 'first', 'done'):
        parts = [getattr(s, name) for s in alt_snap]
        if name == 'calls':
            width = max(p.shape[1] for p in parts)
            parts = [np.pad(p, ((0, 0), (0, width - p.shape[1]))) for p in parts]
        setattr(pool, name, np.concatenate(parts))
    run_greedy(pool, learner, opponent, None, chunk)
    alt_ns = pool.ns_score()
    parent_auction = out['auction'][parent]
    sign = np.where(base.side[parent_auction] == 0, 1, -1)
    out['alt'][parent, slot] = call
    out['adv'][parent, slot] = imps((alt_ns - base_ns[parent_auction]) * sign)
    graded = int((out['alt'] >= 0).any(axis=1).sum())
    stats = dict(deals=n, learner_decisions=seen[0], kept_decisions=d, graded_decisions=graded, alternatives=len(parent),
                 nonzero=int((out['adv'][parent, slot] != 0).sum()),
                 mean_adv=float(out['adv'][parent, slot].mean()),
                 positive=int((out['adv'][parent, slot] > 0).sum()), negative=int((out['adv'][parent, slot] < 0).sum()))
    return base, out, stats


def decision_inputs(base, auction, n):
    """Rebuild network inputs for stored decisions (auction index, call count before the decision)."""
    snap = base.clone(auction)
    snap.n = np.asarray(n, np.int64).copy()
    width = snap.calls.shape[1]
    snap.calls[np.arange(width)[None, :] >= snap.n[:, None]] = 0
    return snap.inputs(np.arange(len(auction)))
