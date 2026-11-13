"""E9-8: what replaying the bidder is worth over the hand-fit scorer (prediction; team/gen9 experiments/E9-8.md).

Auctions bid at all four seats by a house LSTM bidder. For every seat s, its left-hand opponent weights a
pool of random hands for s (from the 39 cards it cannot see) plus s's true hand, and the gain of a reader is
log w(true) - log mean_pool w (nats; 0 = no information). Readers:

    S          hand-fit scorer v0 (trained on Gen 5 bidder auctions)
    R-ind-.02  replay: each of s's calls is the bidder's argmax for the candidate hand, eps 0.02
    R-ind-.1   the same, eps 0.1
    R-soft     replay with the bidder's own softmax as the likelihood of each call
    R-soft-.02 the same with a floor: (1 - eps) p + eps / (legal calls), eps 0.02 (ProfileReplay's default from 12 Nov)
    R-soft-.05 the same, eps 0.05
    S+R-soft   both (a check: replay should make the scorer redundant)

Also: whether the true hand ever fails its own replay (it must not), the cost (bidder steps and seconds per
board for a pool and two hidden seats), slices by the number of non-pass calls the seat made and by auction
length, and the scorer as a proposal: drawing a pool of 512 from 8,192 uniform hands with probability
proportional to exp(S), the share of the replay posterior's mass the drawn pool keeps.

    python scripts/gen9_e9_8.py --bidder gen6 --deals 400 --pool 256 --out reports/gen9-e9-8-2026-11-12/gen6.json
"""
import argparse
import json
from pathlib import Path
import random
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bridge_harness.bidding_env import CALL_ID, CALLS                 # noqa: E402
from bridge_harness.cards.context import Context                       # noqa: E402
from bridge_harness.cards.match import lstm_step_logits                # noqa: E402
from bridge_harness.gen6_nets import FitScorer, hand_types              # noqa: E402

VULS = ('None', 'NS', 'EW', 'Both')
FLOORS = (0.02, 0.05)
BIDDERS = {'gen5': 'models/bidding/gen5-2026-11-10/bidder.keras', 'gen6': 'models/bidding/gen6-candidate-2026-11-11/bidder.keras'}


def membership(rows):
    m = np.zeros((len(rows), 52), np.int64)
    for i, h in enumerate(rows):
        m[i, list(h)] = 1
    return m


def gain(lw):
    rest = lw[1:]
    m = rest.max()
    return float(lw[0] - (m + np.log(np.mean(np.exp(rest - m)))))


class Replay:
    """The bidder replayed on a batch of candidate hands for one seat, teacher-forced on the actual auction."""

    def __init__(self, path):
        from bridge_harness.system_bidders import BenLstmBidder
        self.b = BenLstmBidder(path)
        self.steps = 0

    def logliks(self, cand, seat, dealer, vul, calls):
        """(sum log softmax prob of the seat's calls, number of the seat's calls that are the argmax) per candidate."""
        n = len(cand)
        sess = self.b.session(np.asarray(cand), np.full(n, seat), np.full(n, dealer), np.full(n, VULS.index(vul)))
        toks = np.full((n, 64), -1, np.int64)
        toks[:, :len(calls)] = [CALL_ID[c] for c in calls]
        soft, hits, k = np.zeros(n), np.zeros(n, np.int64), 0
        self.floored = {e: np.zeros(n) for e in FLOORS}
        rows = np.arange(n)
        for t, c in enumerate(calls):
            if (dealer + t) % 4 != seat:
                continue
            k += 1
            logits = lstm_step_logits(self.b, sess, rows, toks, np.full(n, t))
            legal = [CALL_ID[x] for x in Context.make(calls[:t], dealer, seat, vul).legal]
            z = logits[:, legal]
            z = z - z.max(1, keepdims=True)
            logp = z - np.log(np.exp(z).sum(1, keepdims=True))
            j = legal.index(CALL_ID[c])
            soft += logp[:, j]
            for e in FLOORS:
                self.floored[e] += np.log((1 - e) * np.exp(logp[:, j]) + e / len(legal))
            hits += (logp.argmax(1) == j)
            self.steps += n
        return soft, hits, k


def auctions(path, n, seed):
    from bridge_harness.system_bidders import BenLstmBidder
    from bridge_harness.system_fit import simulate
    rng = np.random.default_rng(seed)
    deck = np.sort(rng.permuted(np.broadcast_to(np.arange(52), (n, 52)), axis=1).reshape(n, 4, 13), axis=2)
    dealer, vul = np.arange(n) % 4, (np.arange(n) // 4) % 4
    b = BenLstmBidder(path)
    sim = simulate([b, b], deck, dealer, vul)
    return [([list(map(int, h)) for h in deck[i]], int(dealer[i]), VULS[int(vul[i])], [CALLS[int(t)] for t in sim['calls'][i] if t >= 0])
            for i in range(n)]


def summarize(rows, keys):
    out = {'n': len(rows)}
    for k in keys:
        v = np.array([r[k] for r in rows])
        out[k] = [round(float(v.mean()), 3), round(float(v.std(ddof=1) / np.sqrt(max(len(v) - 1, 1))), 3)] if len(v) > 1 else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bidder', default='gen6', choices=sorted(BIDDERS))
    ap.add_argument('--replay', default=None, choices=sorted(BIDDERS), help='bidder replayed (default: the one that bid; another one = a mis-mapped profile)')
    ap.add_argument('--deals', type=int, default=400)
    ap.add_argument('--pool', type=int, default=256)
    ap.add_argument('--proposal', type=int, default=60, help='deals on which the scorer-as-proposal check runs')
    ap.add_argument('--seed', type=int, default=8801)
    ap.add_argument('--scorer', default='models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz')
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    scorer = FitScorer(a.scorer)
    rep = Replay(BIDDERS[a.replay or a.bidder])
    rng = random.Random(a.seed)
    boards = auctions(BIDDERS[a.bidder], a.deals, a.seed)
    rows, fails, t_replay, t_scorer, proposal = [], 0, 0., 0., []
    keys = ('S', 'R-ind-.02', 'R-ind-.1', 'R-soft', 'R-soft-.02', 'R-soft-.05', 'S+R-soft')
    for i, (hands, dealer, vul, calls) in enumerate(boards):
        for s in range(4):
            o = (s + 1) % 4
            unseen = [c for c in range(52) if c not in set(hands[o])]
            cand = [sorted(hands[s])] + [sorted(rng.sample(unseen, 13)) for _ in range(a.pool)]
            length, hon = hand_types(membership(cand))
            t0 = time.time()
            S = scorer.type_log_score(length, hon, s, dealer, vul, calls)
            t1 = time.time()
            soft, hits, k = rep.logliks(cand, s, dealer, vul, calls)
            t2 = time.time()
            t_scorer += t1 - t0
            t_replay += t2 - t1
            miss = k - hits
            if miss[0]:
                fails += 1
            r = {'S': gain(S), 'R-ind-.02': gain(miss * np.log(0.02) + hits * np.log(0.98)), 'R-ind-.1': gain(miss * np.log(0.1) + hits * np.log(0.9)),
                 'R-soft': gain(soft), 'R-soft-.02': gain(rep.floored[0.02]), 'R-soft-.05': gain(rep.floored[0.05]), 'S+R-soft': gain(S + soft), 'bids': sum(1 for t, c in enumerate(calls) if (dealer + t) % 4 == s and c != 'PASS'),
                 'long': len(calls) > 4}
            rows.append(r)
            if i < a.proposal and s == (dealer + 1) % 4:
                big = [sorted(rng.sample(unseen, 13)) for _ in range(8192)]
                bl, bh = hand_types(membership(big))
                Sb = scorer.type_log_score(bl, bh, s, dealer, vul, calls)
                Rb, _, _ = rep.logliks(big, s, dealer, vul, calls)
                rep.floored = {}
                p = np.exp(Sb - Sb.max())
                p /= p.sum()
                pick = np.unique(np.random.default_rng(i).choice(len(big), 512, p=p))
                post = np.exp(Rb - Rb.max())
                post /= post.sum()
                proposal.append(float(post[pick].sum()))
    report = {'bidder': a.bidder, 'replay': a.replay or a.bidder, 'deals': a.deals, 'pool': a.pool, 'seed': a.seed, 'all': summarize(rows, keys),
              'true_hand_fails_own_replay': fails,
              'by_calls': {f'{lo}': summarize([r for r in rows if r['bids'] == lo], keys) for lo in (0, 1)} | {'2+': summarize([r for r in rows if r['bids'] >= 2], keys)},
              'by_length': {'4 or fewer calls': summarize([r for r in rows if not r['long']], keys), 'longer': summarize([r for r in rows if r['long']], keys)},
              'cost': {'replay_bidder_steps': rep.steps, 'replay_seconds_per_seat_pool': round(t_replay / len(rows), 4),
                       'scorer_seconds_per_seat_pool': round(t_scorer / len(rows), 4), 'pool': a.pool + 1},
              'scorer_as_proposal': {'n': len(proposal), 'replay_mass_kept_mean': round(float(np.mean(proposal)), 3) if proposal else None,
                                     'replay_mass_kept_median': round(float(np.median(proposal)), 3) if proposal else None}}
    print(json.dumps(report, indent=1))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
