from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import random
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError

from .core import SEATS, card, hand_text, normalize_bid, score, symbol, vulnerable, winner
from .sampling import Sampler


@dataclass
class Decision:
    card: int
    details: dict = field(default_factory=dict)


class RandomPlayer:
    def choose(self, o, rng):
        return Decision(rng.choice(o.legal))


class GreedyPlayer:
    """Deliberately weak, information-legal baseline; no search or bidding knowledge."""
    def choose(self, o, rng):
        cheap = lambda c: (c % 13, c // 13)
        if o.trick:
            winning = [c for c in o.legal if winner(o.trick + ((o.actor, c),), o.contract.trump) == o.actor]
            partner_winning = winner(o.trick, o.contract.trump) % 2 == o.actor % 2
            if winning and not partner_winning:
                return Decision(min(winning, key=cheap))
            return Decision(min(o.legal, key=cheap))
        return Decision(max(o.legal, key=lambda c: (c % 13, -c // 13)))


class PIMCPlayer:
    def __init__(self, samples=32, objective="score", batch=True, near_tie=0.0, sampler_factory=Sampler, layout_reduction=None):
        if samples < 1 or objective not in ("score", "tricks", "make") \
                or not math.isfinite(near_tie) or near_tie < 0:
            raise ValueError("Invalid PIMC settings")
        from .dds import DDS
        # Share exact position answers across new training/evaluation runs.
        # An explicit empty BRIDGE_DDS_CACHE disables persistence for timing.
        cache_root = Path(os.environ.get('XDG_CACHE_HOME',Path.home()/'.cache'))
        cache_path = os.environ.get('BRIDGE_DDS_CACHE',str(cache_root/'single-dummy-bridge'/'dds-positions.sqlite'))
        self.dds = DDS(cache_path=cache_path)
        self.samples, self.objective = samples, objective
        self.batch, self.near_tie = batch, near_tie
        self.sampler_factory = sampler_factory
        self.layout_reduction = None
        if layout_reduction is not None:
            from .layout_reduction import ReductionConfig
            self.layout_reduction = ReductionConfig(**layout_reduction) if isinstance(layout_reduction, dict) else layout_reduction

    def close(self):
        self.dds.close()

    def choose(self, o, rng):
        if len(o.legal) == 1:
            return Decision(o.legal[0], {"samples": 0, "dds_calls": 0, "forced": True,
                "behavior_probabilities": {symbol(o.legal[0]): 1.0}, "selected_probability": 1.0})
        if self.layout_reduction is not None:
            from .layout_reduction import choose_reduced
            reduced = choose_reduced(self, o, rng)
            if reduced is not None:
                return reduced
        sampler = self.sampler_factory(o)
        sums = {c: 0.0 for c in o.legal}
        tricks_sum = dict(sums)
        utilities = {c: [] for c in o.legal}
        nodes = 0
        declaring = o.actor % 2 == o.contract.declarer % 2
        future_tricks = 13 - len(o.history) // 4
        vul = vulnerable(o.vulnerability, o.contract.declarer)
        worlds = [sampler.draw(rng) for _ in range(self.samples)]
        before = self.dds.cache_stats()
        if self.batch:
            solved = self.dds.solve_batch(worlds, o.contract.trump, o.leader, o.trick,
                fixed_seats=[s for s, h in enumerate(o.known_hands) if h is not None])
        else:
            solved = [self.dds.solve(h, o.contract.trump, o.leader, o.trick) for h in worlds]
        for values, n in solved:
            nodes += n
            if set(values) != set(o.legal):
                raise RuntimeError("DDS legal-card expansion mismatch")
            for c, t in values.items():
                total = o.declarer_tricks + (t if declaring else future_tricks - t)
                utility = score(o.contract, total, vul) if self.objective == "score" else \
                    total if self.objective == "tricks" else int(total >= o.contract.level + 6)
                sums[c] += utility if declaring else -utility
                utilities[c].append(utility if declaring else -utility)
                tricks_sum[c] += total
        best = max(sums.values())
        eligible = sorted(c for c, v in sums.items() if best - v <= self.samples * self.near_tie + 1e-9)
        choice = rng.choice(eligible)
        best_card = min(c for c, v in sums.items() if v == best)
        def stderr(values):
            if self.samples < 2:
                return None
            mean = sum(values) / self.samples
            return math.sqrt(sum((v - mean) ** 2 for v in values) / (self.samples * (self.samples - 1)))
        after = self.dds.cache_stats()
        return Decision(choice, {"samples": self.samples, "dds_calls": self.samples,
            "dds_native_solves": after['native_solves']-before['native_solves'],
            "dds_cache_hits": after['hits']-before['hits'],
            "dds_duplicate_worlds": after['duplicate_worlds']-before['duplicate_worlds'],
            "dds_nodes": nodes, "objective": self.objective, "batch": self.batch,
            "unique_worlds": len(set(worlds)), "near_tie": self.near_tie,
            "behavior_probabilities": {symbol(c): (1.0 / len(eligible) if c in eligible else 0.0) for c in sums},
            "selected_probability": 1.0 / len(eligible),
            "selected_pimc_gap": (best - sums[choice]) / self.samples,
            "estimates": {symbol(c): {"utility": sums[c] / self.samples,
                           "utility_stderr": stderr(utilities[c]),
                           "gap_to_best": (best - sums[c]) / self.samples,
                           "gap_stderr": stderr([a - b for a, b in zip(utilities[best_card], utilities[c])]),
                           "declarer_tricks": tricks_sum[c] / self.samples} for c in sums}})


class BenPlayer:
    """BEN HTTP API, pinned interface checked against 9b5f431 (2026-11-08)."""
    def __init__(self, url="http://127.0.0.1:8085", timeout=120):
        self.url, self.timeout = url.rstrip("/"), timeout

    def request(self, endpoint, params):
        url = self.url + "/" + endpoint + "?" + urlencode(params)
        try:
            with urlopen(url, timeout=self.timeout) as response:
                data = json.load(response)
        except HTTPError as e:
            body = e.read().decode(errors="replace")[:4000]
            raise RuntimeError(f"BEN {endpoint} HTTP {e.code}: {body}") from e
        if "error" in data or ("card" not in data and "bid" not in data):
            raise RuntimeError(f"BEN {endpoint}: {data}")
        return data

    @staticmethod
    def context(bids):
        return "".join({"PASS": "--", "X": "Db", "XX": "Rd"}.get(b, b) for b in bids)

    def choose(self, o, rng):
        if len(o.legal) == 1:
            return Decision(o.legal[0], {"forced": True})
        params = dict(hand=hand_text(o.original_hand(o.controller)),
                      seat=SEATS[o.controller], dealer=SEATS[o.dealer],
                      vul=o.vulnerability, ctx=self.context(o.auction),
                      matchtype="IMP", details="false")
        endpoint = "play" if o.history else "lead"
        if o.history:
            params.update(dummy=hand_text(o.original_hand(o.contract.dummy)),
                          played="".join(symbol(c) for _, c in o.history), format="false")
        response = self.request(endpoint, params)
        c = card(response["card"])
        if c not in o.legal:
            raise ValueError(f"BEN returned illegal card {response['card']}")
        return Decision(c, {"endpoint": endpoint, "request": params, "response": response})

    def bid(self, hand, seat, dealer, vulnerability, bids):
        params = dict(hand=hand_text(hand), seat=SEATS[seat], dealer=SEATS[dealer],
                      vul=vulnerability, ctx=self.context(bids), matchtype="IMP", details="false")
        response = self.request("bid", params)
        return normalize_bid(response["bid"]), {"request": params, "response": response}


def make_player(spec, samples=32, ben_url="http://127.0.0.1:8085", timeout=120, objective="score",
                batch=True, near_tie=0.0):
    if spec.startswith("manifest:"):
        from .loop_registry import build_player
        return build_player(spec.removeprefix("manifest:"))
    if spec == "random":
        return RandomPlayer()
    if spec == "greedy":
        return GreedyPlayer()
    if spec == "pimc":
        return PIMCPlayer(samples, objective, batch, near_tie)
    if spec == "ben":
        return BenPlayer(ben_url, timeout)
    raise ValueError(f"Unknown player: {spec}")
