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


def sampled_utilities(o, frozen_belief, dds):
    """32 worlds: 24 frozen v4 + 8 uniform, all legal. No outcomes in API.

    Value of perfect information under DDS is only an importance heuristic,
    not an estimate of achievable single-dummy play improvement.
    """
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
    return worlds, utility


def importance(o, frozen_belief, dds):
    if len(o.legal) < 2:
        return dict(evpi=0., weight=1., worlds=0, switch_fraction=0.)
    _, utility = sampled_utilities(o, frozen_belief, dds)
    baseline = int(utility.mean(0).argmax())
    regrets = utility.max(1)-utility[:, baseline]
    evpi = max(0., float(regrets.mean()))
    return dict(evpi=evpi, weight=1.+3.*min(evpi/2., 1.), worlds=32,
                switch_fraction=float((regrets > 0).mean()))


def card_information_value(owners, utility, min_group=4, prior_worlds=4.):
    """Cross-fitted value of revealing each card's owner under a frozen proposal.

    Even/odd halves each contain 12 weighted + 4 uniform worlds. Select a
    conditional action on one half; evaluate its utility on the other half.
    Each owner group needs >=4 worlds in BOTH halves. Shrink conditional action
    values toward the unconditional values with four pseudo-worlds. True deal
    owners, observed outcomes and the candidate network are never accepted.
    Values include information from correlations, not isolated causal effects.
    """
    owners=np.asarray(owners);utility=np.asarray(utility,dtype=np.float64)
    if owners.shape != (32,52) or utility.shape[0] != 32 or utility.ndim != 2:
        raise ValueError('Expected 32 hypothetical layouts and all legal action utilities')
    gain=np.zeros(52,np.float64)
    for parity in (0,1):
        train=np.arange(parity,32,2);test=np.arange(1-parity,32,2)
        mean=utility[train].mean(0);baseline=int(mean.argmax())
        for c in range(52):
            actions=np.full(len(test),baseline,int)
            for owner in range(4):
                ix=train[owners[train,c]==owner];j=owners[test,c]==owner
                if len(ix)<min_group or j.sum()<min_group:continue
                conditional=(utility[ix].sum(0)+prior_worlds*mean)/(len(ix)+prior_worlds)
                actions[j]=int(conditional.argmax())
            gain[c]+=.5*float((utility[test,actions]-utility[test,baseline]).mean())
    return np.maximum(gain,0.)


def impactful_cards(o, frozen_belief, dds):
    if len(o.legal)<2:return np.zeros(52,np.float32)
    worlds,u=sampled_utilities(o,frozen_belief,dds)
    owners=np.full((32,52),-1,np.int8)
    for i,hands in enumerate(worlds):
        for seat,hand in enumerate(hands):owners[i,list(hand)]=seat
    return card_information_value(owners,u).astype(np.float32)
