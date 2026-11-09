"""Importance labels from hypothetical legal worlds, never the true hidden deal."""
import hashlib
import json
import random
from dataclasses import asdict
import numpy as np
from .core import score, vulnerable, imps
from .bidding_sampling import WeightedSampler


def public_key(o):
    return hashlib.sha256(json.dumps(asdict(o), sort_keys=True).encode()).hexdigest()


def importance(o, frozen_belief, dds):
    """32 worlds: 24 frozen v4 + 8 uniform, all legal. No outcomes in API.

    Value of perfect information under DDS is only an importance heuristic,
    not an estimate of achievable single-dummy play improvement.
    """
    if len(o.legal) < 2:
        return dict(evpi=0., weight=1., worlds=0, switch_fraction=0.)
    rng = random.Random(int(public_key(o)[:16], 16))
    weighted = WeightedSampler(o, frozen_belief.logits(o))
    uniform = WeightedSampler(o)
    worlds = [weighted.draw(rng) for _ in range(24)] + [uniform.draw(rng) for _ in range(8)]
    values = dds.solve_batch(worlds, o.contract.trump, o.leader, o.trick,
                            fixed_seats=[s for s, h in enumerate(o.known_hands) if h is not None])
    declaring = o.actor % 2 == o.contract.declarer % 2
    future = 13-len(o.history)//4
    vul = vulnerable(o.vulnerability, o.contract.declarer)
    reference = score(o.contract, o.contract.level+6, vul)
    utility = np.array([[imps((score(o.contract, o.declarer_tricks +
        (v[c] if declaring else future-v[c]), vul)-reference)*(1 if declaring else -1))
        for c in o.legal] for v, _ in values], dtype=np.float64)
    baseline = int(utility.mean(0).argmax())
    regrets = utility.max(1)-utility[:, baseline]
    evpi = max(0., float(regrets.mean()))
    return dict(evpi=evpi, weight=1.+3.*min(evpi/2., 1.), worlds=32,
                switch_fraction=float((regrets > 0).mean()))
