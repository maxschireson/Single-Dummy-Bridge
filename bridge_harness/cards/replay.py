"""Replay reader: a bidder's own likelihood of a seat's calls, over hand types (Gen 9 WIP; E9-8).

For a profile whose generator we hold, the exact reading of a seat's calls is a replay: run the bidder on
each candidate hand, teacher-forced on the actual auction, and take the probability it gives to each call
the seat made. ``ReplayReader(path).type_log_score(length, hon, seat, dealer, vulnerability, auction)`` has
FitScorer's interface, so the Gen 9 player can use it as a profile's row in place of the scorer.

The house LSTM bidders' inputs depend only on the hand type (points, lengths, the A K Q J T of each suit and
the number of lower cards), so a type is replayed through any hand with that type, and results are cached
per seat and auction.

Every call's likelihood has a floor: (1 - eps) p + eps / (legal calls), eps 0.02 by default (REPLAY_EPS), so a
call the bidder all but never makes (a psych, a player straying from the profile) costs a layout about
log(eps / legal) rather than ruling it out.
"""
import os
from pathlib import Path
import sys

import numpy as np

from ..bidding_env import CALL_ID
from ..gen6_nets import hand_types
from .context import Context
from .match import lstm_step_logits
from .rb_meanings import type_hand

VULS = ('None', 'NS', 'EW', 'Both')
REPLAY_EPS = 0.02
GENERATOR_KINDS = ('house', 'anchor', 'synthetic')     # models whose card's 'generator' block is honoured
REPO = __import__('pathlib').Path(__file__).resolve().parents[2]


class ReplayReader:
    def __init__(self, bidder, eps=REPLAY_EPS, temperature=1.0, cache_auctions=16):
        if isinstance(bidder, str):
            from ..system_bidders import BenLstmBidder
            bidder = BenLstmBidder(bidder)
        self.b, self.eps, self.temperature = bidder, float(eps), float(temperature)
        self.sha256 = getattr(bidder, 'sha256', None)
        self.cache, self.cache_auctions = {}, cache_auctions

    def _replay(self, length, hon, seat, dealer, vul, calls):
        n = len(length)
        hands = np.array([type_hand(length[i], hon[i]) for i in range(n)])
        sess = self.b.session(hands, np.full(n, seat), np.full(n, dealer), np.full(n, VULS.index(vul)))
        toks = np.full((n, max(64, len(calls) + 1)), -1, np.int64)
        toks[:, :len(calls)] = [CALL_ID[c] for c in calls]
        out, rows = np.zeros(n), np.arange(n)
        for t, c in enumerate(calls):
            if (dealer + t) % 4 != seat:
                continue
            z = lstm_step_logits(self.b, sess, rows, toks, np.full(n, t)) / self.temperature
            legal = [CALL_ID[x] for x in Context.make(calls[:t], dealer, seat, vul).legal]
            z = z[:, legal]
            z = z - z.max(1, keepdims=True)
            p = np.exp(z)
            p /= p.sum(1, keepdims=True)
            out += np.log((1 - self.eps) * p[:, legal.index(CALL_ID[c])] + self.eps / len(legal) + 1e-300)
        return out

    def type_log_score(self, length, hon, seat, dealer, vulnerability, auction):
        length = np.asarray(length, np.int64).reshape(-1, 4)
        hon = np.asarray(hon, np.int64).reshape(-1, 4)
        calls = tuple(Context.make(auction, dealer, seat).calls)
        key = (calls, int(dealer), vulnerability, int(seat))
        known = self.cache.get(key)
        if known is None:
            if len(self.cache) >= self.cache_auctions:
                self.cache.clear()
            known = self.cache[key] = {}
        packed = (length * (14 ** np.arange(4))).sum(1) * 32 ** 4 + (hon * (32 ** np.arange(4))).sum(1)
        uniq, first, inverse = np.unique(packed, return_index=True, return_inverse=True)
        todo = [i for i, k in enumerate(uniq) if int(k) not in known]
        if todo:
            idx = first[todo]
            vals = self._replay(length[idx], hon[idx], int(seat), int(dealer), vulnerability, list(calls))
            for k, v in zip(uniq[todo], vals):
                known[int(k)] = float(v)
        return np.array([known[int(k)] for k in uniq])[inverse.ravel()]

    def seat_log_score(self, member, seat, dealer, vulnerability, auction):
        length, hon = hand_types(member)
        return self.type_log_score(length, hon, seat, dealer, vulnerability, auction)


class RuleReplay:
    """A deterministic bidder (rule_bidder.RuleSystemBidder, or anything with call()) replayed on hand types:
    P(call) = (1 - eps) [the bidder makes it] + eps / (legal calls)."""

    def __init__(self, bidder, eps=0.02, cache_auctions=16):
        self.b, self.eps = bidder, float(eps)
        self.cache, self.cache_auctions = {}, cache_auctions

    def type_log_score(self, length, hon, seat, dealer, vulnerability, auction):
        length = np.asarray(length, np.int64).reshape(-1, 4)
        hon = np.asarray(hon, np.int64).reshape(-1, 4)
        calls = tuple(Context.make(auction, dealer, seat).calls)
        key = (calls, int(dealer), vulnerability, int(seat))
        known = self.cache.get(key)
        if known is None:
            if len(self.cache) >= self.cache_auctions:
                self.cache.clear()
            known = self.cache[key] = {}
        packed = (length * (14 ** np.arange(4))).sum(1) * 32 ** 4 + (hon * (32 ** np.arange(4))).sum(1)
        uniq, first, inverse = np.unique(packed, return_index=True, return_inverse=True)
        turns = [(t, c) for t, c in enumerate(calls) if (dealer + t) % 4 == seat]
        legal = {t: len(Context.make(calls[:t], dealer, seat, vulnerability).legal) for t, _ in turns}
        toks = [CALL_ID[c] for c in calls]
        vi = VULS.index(vulnerability)
        for k, i in zip(uniq, first):
            if int(k) in known:
                continue
            hand = type_hand(length[i], hon[i])
            v = 0.
            for t, c in turns:
                try:
                    hit = int(self.b.call(hand, int(seat), int(dealer), vi, toks[:t])) == CALL_ID[c]
                except (ValueError, IndexError):          # rule_bidder.py edge cases: no evidence from this call
                    continue
                v += np.log((1 - self.eps) * hit + self.eps / legal[t])
            known[int(k)] = float(v)
        return np.array([known[int(k)] for k in uniq])[inverse.ravel()]


class ProfileReplay:
    """The replay hook of the Gen 9 player (gen9.py 'replay_reader'): type_log_score(..., profile=<system id>) is the
    log-likelihood of the seat's calls under that profile's own bidder, or None for a profile whose bidder is not held.
    Bidders come from the Gen 8 system packages (configs/systems/<id>.json, kind ben-lstm-keras)."""

    def __init__(self, root='.', eps=REPLAY_EPS, model=None):
        from ..systems import SystemRegistry
        from pathlib import Path
        self.root, self.eps, self.readers, self.refused = Path(root), eps, {}, {}
        card = getattr(model, 'bidding', None) or {}
        gen = card.get('generator') or {}
        if gen and getattr(model, 'kind', 'unknown') not in GENERATOR_KINDS:
            # a guest's card naming its own bidder must not hand that bidder to the house (G9-D6)
            self._refuse(str(gen.get('profile') or card.get('id')), f'generator block on a {getattr(model, "kind", "unknown")} model')
        elif gen.get('kind') == 'rule_bidder':             # a card written for the rule bidder: its own tables
            from .. import rule_bidder as rb
            self.readers[str(gen.get('profile') or card.get('id'))] = RuleReplay(
                rb.RuleSystemBidder(gen.get('settings') or {}, gen.get('opponents', 'standard')), eps=gen.get('eps', 0.02))
        try:
            self.registry = SystemRegistry.load()
        except Exception:                              # no registry here: no profile has a bidder
            self.registry = None

    def reader(self, profile):
        if profile in self.readers:
            return self.readers[profile]
        r = None
        if self.registry is not None and profile in self.registry:
            try:
                g = self.registry[profile].generator('ben-lstm-keras')
                for base in (self.root, REPO):                   # the run's root, then the repository
                    path = base / g['path']
                    if base == REPO and not g.get('external') and not path.exists() and g.get('restore'):
                        restore(REPO / g['restore'], path)          # a model kept in the repository as parts
                    if not g.get('external') and path.exists():
                        r = ReplayReader(str(path), eps=self.eps)
                        if g.get('sha256') and r.sha256 != g['sha256']:
                            raise ValueError(f'{path}: bidder identity differs from the system package')
                        break
            except (ValueError, KeyError, OSError) as e:
                r = None
                self._refuse(profile, f'{type(e).__name__}: {e}')
        self.readers[profile] = r
        return r

    def _refuse(self, profile, reason):
        """A profile we will not replay although it was offered: recorded, and said once on stderr."""
        if profile not in self.refused:
            self.refused[profile] = reason
            print(f'replay: no replay for profile {profile}: {reason}', file=sys.stderr)

    def type_log_score(self, length, hon, seat, dealer, vulnerability, auction, profile=None):
        r = self.reader(profile) if profile is not None else None
        self.calls = getattr(self, 'calls', 0) + 1
        if r is not None:
            self.used = getattr(self, 'used', 0) + 1
            log = os.environ.get('BRIDGE_REPLAY_LOG')
            if log:
                with open(log, 'a') as f:
                    f.write(f'{profile} seat={seat} types={len(np.asarray(length).reshape(-1, 4))}\n')
        return None if r is None else r.type_log_score(length, hon, seat, dealer, vulnerability, auction)


def restore(script, target):
    """Run a model's restore script (it joins the parts kept in git and checks their sha256) once, under a lock, so
    that worker processes starting together do not race; a no-op if the target exists."""
    import fcntl
    import subprocess
    script, target = Path(script), Path(target)
    if not script.exists():
        return
    import hashlib
    import tempfile
    name = hashlib.sha256(str(target.resolve()).encode()).hexdigest()[:16]
    with open(Path(tempfile.gettempdir()) / f'restore-{name}.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not target.exists():
            subprocess.run([sys.executable, script.name], cwd=script.parent, check=True, stdout=subprocess.DEVNULL)


def replay_factory(model, other=None, root='.'):
    """Factory for gen9.py's 'replay_reader': one ProfileReplay per partnership (bidders loaded on first use):
    house nets through the system registry, and a rule bidder named by the partnership's card ('generator' block,
    kind 'rule_bidder', under the profile id given there or the card's id)."""
    return ProfileReplay(root, eps=REPLAY_EPS, model=model)
