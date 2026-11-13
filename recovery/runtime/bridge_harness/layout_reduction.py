"""Optional clustered DDS quadrature over complete belief-sampled layout pools.

Weights can match the sampler's exact linear feature expectations. Those weights
are quadrature weights, not exact probabilities of the geometric clusters.
No DDS answer is used to choose representatives or their weights.
"""
from dataclasses import dataclass
import math
import time
import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.optimize import minimize
from scipy.spatial.distance import pdist, squareform

from .layout_geometry import encode, HONOR_WEIGHTS
from .dds import DDS
from .dds_cache import position_key


def pack(hands, trump, leader, trick):
    """Use the existing DDS cache representation; no value-model dependency."""
    return np.frombuffer(position_key(DDS._deal(hands, trump, leader, trick)), np.uint8).copy()


@dataclass(frozen=True)
class ReductionConfig:
    large_from: int = 10
    medium_from: int = 7
    medium_enabled: bool = False
    large_pool: int = 128
    large_budget: int = 32
    medium_pool: int = 64
    medium_budget: int = 16
    large_tolerance: float = 0.
    medium_tolerance: float = 0.
    weighting: str = 'belief'
    ridge: float = .001
    representative: str = 'medoid'

    def __post_init__(self):
        if not 1 <= self.medium_from < self.large_from <= 13:
            raise ValueError('Invalid position-size cutoffs')
        for pool, budget in ((self.large_pool, self.large_budget), (self.medium_pool, self.medium_budget)):
            if not isinstance(pool, int) or not isinstance(budget, int) or not 1 <= budget <= pool:
                raise ValueError('Invalid layout budget')
        if any(not math.isfinite(x) or x < 0 for x in (self.large_tolerance, self.medium_tolerance, self.ridge)):
            raise ValueError('Invalid tolerance or ridge')
        if self.weighting not in ('cluster', 'pool', 'belief') or self.representative not in ('medoid', 'random'):
            raise ValueError('Unknown reduction mode')

    def schedule(self, remaining):
        if remaining >= self.large_from:
            return self.large_pool, self.large_budget, self.large_tolerance
        if self.medium_enabled and remaining >= self.medium_from:
            return self.medium_pool, self.medium_budget, self.medium_tolerance
        return None


def feature_mean(sampler, observation):
    """Exact expected linear geometry under this sampler's constrained model."""
    if not hasattr(sampler, 'marginals'):
        from .sampling import Sampler
        from .bidding_sampling import WeightedSampler
        if type(sampler) is not Sampler:
            raise ValueError('Belief calibration requires sampler marginals')
        sampler = WeightedSampler(observation)
    probability = np.asarray(sampler.marginals(), float)
    if probability.shape != (52, 4) or not np.isfinite(probability).all():
        raise ValueError('Invalid ownership marginals')
    cards = probability.T.reshape(4, 4, 13).copy()
    cards[[h is not None for h in observation.known_hands]] = 0
    seats = (observation.actor + np.arange(4)) % 4
    cards = cards[seats]
    return np.r_[cards.sum(-1).ravel(), (cards @ HONOR_WEIGHTS).ravel()]


def cluster_layouts(features, budget, tolerance=0., rng=None):
    """Average linkage over all draws, retaining multiplicities and all mass.

    Distance tolerance can merge to fewer clusters; budget is a hard ceiling.
    With zero tolerance this is a capped hierarchy cut, not a calibrated natural
    scale. Nonzero tolerances should be fixed before outcome evaluation.
    """
    features = np.asarray(features, float)
    n = len(features)
    if features.ndim != 2 or not np.isfinite(features).all() or not 1 <= budget <= n:
        raise ValueError('Invalid geometry or budget')
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError('Invalid clustering tolerance')
    z = features / np.maximum(np.linalg.norm(features, axis=1, keepdims=True), 1e-12)
    condensed = np.maximum(pdist(z, metric='sqeuclidean') / 2, 0)
    distances = squareform(condensed)
    if n == 1:
        labels = np.ones(1, int); threshold = tolerance
    else:
        tree = linkage(condensed, method='average')
        ceiling = float(tree[n-budget-1, 2]) if budget < n else 0.
        threshold = max(tolerance, ceiling)
        labels = fcluster(tree, threshold, criterion='distance')
    indices, masses = [], []
    for label in np.unique(labels):
        members = np.flatnonzero(labels == label)
        medoid = int(members[np.argmin(distances[np.ix_(members, members)].sum(1))])
        indices.append(medoid if rng is None else int(rng.choice(members)))
        masses.append(len(members) / n)
    if len(indices) > budget:
        raise RuntimeError('Hierarchy cut exceeded budget')
    return np.array(indices, int), np.array(masses), dict(
        clusters=len(indices), distance_threshold=threshold, tolerance=tolerance,
        max_cluster_mass=float(max(masses)), linkage='average', metric='cosine')


def calibrate_weights(features, indices, target, prior, ridge=.001):
    """Nonnegative, unit-sum moment fit, with small concentration penalty.

    The ridge is toward uniform selected weights, not the noisy cluster counts.
    Cluster masses initialize the solver and are a safe fallback on failure.
    Exact moments need not lie inside the selected layouts' convex hull; expose
    the residual instead of asserting an exact fit or exact cluster masses.
    """
    features = np.asarray(features, float); target = np.asarray(target, float)
    prior = np.asarray(prior, float); indices = np.asarray(indices, int)
    if (features.ndim != 2 or target.shape != (features.shape[1],) or
        prior.shape != (len(indices),) or not len(indices) or
        not np.isfinite(features).all() or not np.isfinite(target).all() or
        not np.isfinite(prior).all() or (prior < 0).any() or prior.sum() <= 0 or
        not math.isfinite(ridge) or ridge < 0):
        raise ValueError('Invalid weight calibration inputs')
    prior = prior / prior.sum(); k = len(prior)
    # Half a card/strength point floor prevents nearly-constant coordinates from
    # dominating the optimization. Known-hand coordinates have zero residual.
    scale = np.maximum(features.std(0), .5)
    a = (features[indices] - target) / scale
    gram = a @ a.T / a.shape[1]
    h = gram + ridge * k * np.eye(k)
    uniform = np.full(k, 1/k)
    def fun(w): return float(w @ gram @ w + ridge*k*np.square(w-uniform).sum())
    def jac(w): return 2 * (h @ w - ridge*k*uniform)
    fit = minimize(fun, prior, jac=jac, method='SLSQP', bounds=[(0., 1.)]*k,
                   constraints=[dict(type='eq', fun=lambda w: w.sum()-1,
                                     jac=lambda w: np.ones_like(w))],
                   options=dict(ftol=1e-10, maxiter=100))
    valid = (fit.success and np.isfinite(fit.x).all() and fit.x.min() >= -1e-8 and
             abs(fit.x.sum()-1) < 1e-7 and fun(fit.x) <= fun(prior)+1e-9)
    w = np.maximum(fit.x, 0) if valid else prior.copy(); w /= w.sum()
    def residual(v): return float(np.square(v @ a).mean())
    return w, dict(success=bool(valid), iterations=int(fit.nit),
                   standardized_moment_mse_before=residual(prior),
                   standardized_moment_mse_after=residual(w),
                   max_weight=float(w.max()), weight_effective_count=float(1/(w @ w)),
                   target_in_selected_hull_approximately=residual(w)<1e-10,
                   ridge=ridge, regularizer='squared concentration, toward uniform representatives')


def reduce_pool(raw, fixed, budget, tolerance=0., weighting='belief', target=None, ridge=.001, rng=None):
    start=time.process_time(); features=encode(raw, fixed)
    indices, masses, info=cluster_layouts(features, budget, tolerance, rng)
    info['cluster_weights']=masses.tolist()
    if weighting not in ('cluster', 'pool', 'belief'): raise ValueError('Unknown weighting')
    if weighting != 'cluster':
        if weighting == 'belief' and target is None: raise ValueError('Belief target required')
        target = features.mean(0) if weighting == 'pool' else target
        masses, fit=calibrate_weights(features, indices, target, masses, ridge)
        info['calibration']=fit
    info.update(weighting=weighting, weights=masses.tolist(), indices=indices.tolist(),
                pool=len(raw), requested_budget=budget, reduction_cpu_seconds=time.process_time()-start)
    return indices, masses, info


def choose_reduced(player, o, rng):
    """PIMC hook. Return None to use the unchanged small-position player."""
    config=player.layout_reduction
    remaining=13-len(o.history)//4; schedule=config.schedule(remaining)
    if schedule is None: return None
    pool, budget, tolerance=schedule
    t=time.process_time(); sampler=player.sampler_factory(o)
    worlds=[sampler.draw(rng) for _ in range(pool)]
    sampling_cpu=time.process_time()-t
    raw=np.stack([pack(h, o.contract.trump, o.leader, o.trick) for h in worlds])
    fixed=np.tile([h is not None for h in o.known_hands], (pool, 1))
    t=time.process_time()
    target=feature_mean(sampler, o) if config.weighting == 'belief' else None
    moment_cpu=time.process_time()-t
    rr=np.random.default_rng(rng.getrandbits(64)) if config.representative == 'random' else None
    indices, weights, info=reduce_pool(raw, fixed, budget, tolerance, config.weighting, target, config.ridge, rr)
    # Zero-weight representatives need not be solved. Keep candidate multiplicity
    # in clustering and weights, even when DDS itself caches duplicate positions.
    positive=weights>0; indices=indices[positive];weights=weights[positive];weights/=weights.sum()
    selected=[worlds[int(i)] for i in indices]; before=player.dds.cache_stats()
    t=time.process_time()
    solved=(player.dds.solve_batch(selected, o.contract.trump, o.leader, o.trick,
                                  fixed_seats=np.flatnonzero(fixed[0]).tolist()) if player.batch else
            [player.dds.solve(h, o.contract.trump, o.leader, o.trick) for h in selected])
    dds_cpu=time.process_time()-t
    return weighted_decision(o, rng, solved, weights, player.objective, player.near_tie,
                             player.dds.cache_stats(), before,
                             dict(info, sampling_cpu_seconds=sampling_cpu, moment_cpu_seconds=moment_cpu,
                                  dds_cpu_seconds=dds_cpu, actual_indices=indices.tolist(), actual_weights=weights.tolist()),
                             len(set(selected)), player.batch)


def weighted_decision(o, rng, solved, weights, objective, near_tie, after, before, reduction, unique, batch):
    from .players import Decision
    from .core import score, vulnerable, symbol
    declaring=o.actor%2 == o.contract.declarer%2; remaining=13-len(o.history)//4
    means={c:0. for c in o.legal}; tricks=dict(means); nodes=0
    for (values, count), w in zip(solved, weights):
        if set(values) != set(o.legal): raise RuntimeError('DDS legal-card expansion mismatch')
        nodes+=count
        for c, t in values.items():
            total=o.declarer_tricks+(t if declaring else remaining-t)
            value=score(o.contract, total, vulnerable(o.vulnerability, o.contract.declarer)) if objective=='score' else total if objective=='tricks' else int(total>=o.contract.level+6)
            means[c]+=float(w)*(value if declaring else -value);tricks[c]+=float(w)*total
    best=max(means.values());eligible=sorted(c for c,v in means.items() if best-v<=near_tie+1e-9)
    choice=rng.choice(eligible);n=len(solved)
    return Decision(choice, dict(samples=n, dds_calls=n, dds_nodes=nodes, objective=objective, batch=batch,
        dds_native_solves=after['native_solves']-before['native_solves'], dds_cache_hits=after['hits']-before['hits'],
        dds_duplicate_worlds=after['duplicate_worlds']-before['duplicate_worlds'], unique_worlds=unique,
        near_tie=near_tie, behavior_probabilities={symbol(c):1/len(eligible) if c in eligible else 0. for c in means},
        selected_probability=1/len(eligible), selected_pimc_gap=best-means[choice], layout_reduction=reduction,
        uncertainty_note='No IID standard error for deterministic representatives and calibrated weights.',
        estimates={symbol(c):dict(utility=v, utility_stderr=None, gap_to_best=best-v, gap_stderr=None,
                                  declarer_tricks=tricks[c]) for c,v in means.items()}))
