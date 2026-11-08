from dataclasses import dataclass, field
import json
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
    def __init__(self, samples=32, objective="score"):
        if samples < 1 or objective not in ("score", "tricks", "make"):
            raise ValueError("Invalid PIMC settings")
        from .dds import DDS
        self.dds = DDS()
        self.samples, self.objective = samples, objective

    def close(self):
        self.dds.close()

    def choose(self, o, rng):
        if len(o.legal) == 1:
            return Decision(o.legal[0], {"samples": 0, "dds_calls": 0, "forced": True})
        sampler = Sampler(o)
        sums = {c: 0.0 for c in o.legal}
        tricks_sum = dict(sums)
        nodes = 0
        declaring = o.actor % 2 == o.contract.declarer % 2
        future_tricks = 13 - len(o.history) // 4
        vul = vulnerable(o.vulnerability, o.contract.declarer)
        for _ in range(self.samples):
            values, n = self.dds.solve(sampler.draw(rng), o.contract.trump, o.leader, o.trick)
            nodes += n
            if set(values) != set(o.legal):
                raise RuntimeError("DDS legal-card expansion mismatch")
            for c, t in values.items():
                total = o.declarer_tricks + (t if declaring else future_tricks - t)
                utility = score(o.contract, total, vul) if self.objective == "score" else \
                    total if self.objective == "tricks" else int(total >= o.contract.level + 6)
                sums[c] += utility if declaring else -utility
                tricks_sum[c] += total
        best = max(sums.values())
        choice = rng.choice(sorted(c for c, v in sums.items() if v == best))
        return Decision(choice, {"samples": self.samples, "dds_calls": self.samples,
            "dds_nodes": nodes, "objective": self.objective,
            "estimates": {symbol(c): {"utility": sums[c] / self.samples,
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


def make_player(spec, samples=32, ben_url="http://127.0.0.1:8085", timeout=120, objective="score"):
    if spec == "random":
        return RandomPlayer()
    if spec == "greedy":
        return GreedyPlayer()
    if spec == "pimc":
        return PIMCPlayer(samples, objective)
    if spec == "ben":
        return BenPlayer(ben_url, timeout)
    raise ValueError(f"Unknown player: {spec}")
