"""Paired, deal-clustered IMP estimates and a predeclared promotion rule."""
import math
import statistics


def plan_arena(effect, sd_parent, sd_ben_delta, generation=1, stages=3, looks=3,
               family_alpha=.05, joint_power=.8, shard_size=250):
    """Approximate power planning from a PRIOR pilot, before freezing a campaign.

    effect is the gain above the promotion margin expected in BOTH endpoints.
    Power shortfall is split between endpoints; deal correlation can make this
    conservative. No pilot effect estimate is used to select a candidate here.
    """
    from scipy.stats import norm, t
    if not all(math.isfinite(v) and v > 0 for v in (effect,sd_parent,sd_ben_delta)):
        raise ValueError('Positive finite effect and endpoint standard deviations required')
    if not 0 < joint_power < 1 or not 0 < family_alpha < 1 or min(generation,stages,looks,shard_size)<1:
        raise ValueError('Invalid power plan settings')
    alpha=family_alpha/(generation*(generation+1)*stages*looks*2)
    z_power=float(norm.ppf(1-(1-joint_power)/2))
    sizes={}
    for key, sd in (('vs_parent',sd_parent),('improvement_vs_ben',sd_ben_delta)):
        n=max(30,math.ceil(((norm.ppf(1-alpha/2)+z_power)*sd/effect)**2))
        for _ in range(10):
            required=max(30,math.ceil(((t.ppf(1-alpha/2,n-1)+z_power)*sd/effect)**2))
            if required<=n:break
            n=required
        sizes[key]=n
    target=math.ceil(max(sizes.values())/shard_size)*shard_size
    return dict(approximate=True,target_gain_above_margin=effect,joint_power=joint_power,
                adjusted_alpha=alpha,endpoint_deals=sizes,recommended_arena_deals=target,
                maximum_table_games=8*target,
                note='Use prior-pilot paired-deal SDs, including SD of the BEN difference; freeze sizes before evaluation.')


def estimate(values, alpha=.05):
    from scipy.stats import t
    values = list(values)
    if len(values) < 2 or not all(math.isfinite(x) for x in values):
        raise ValueError('At least two finite independent deal values required')
    mean = statistics.mean(values)
    se = statistics.stdev(values) / math.sqrt(len(values))
    # Degenerate samples (usually identical bots/all ties) cannot establish a
    # population improvement or justify early futility stopping.
    radius = float(t.ppf(1 - alpha / 2, len(values) - 1)) * se
    return dict(mean=mean, se=se, n=len(values), low=mean-radius, high=mean+radius,
                alpha=alpha, informative=se > 0)


def gate(rows, generation, stages, looks, family_alpha=.05, minimum_gain=0.):
    """rows already pair all opponents on exactly the same independent deals.

    Alpha is allocated across generations, candidate data stages, looks, and
    two endpoints. Student-t intervals are approximate, not exact anytime CSs.
    """
    if generation < 1 or stages < 1 or looks < 1 or not 0 < family_alpha < 1:
        raise ValueError('Invalid gate settings')
    if len({r['deal_id'] for r in rows}) != len(rows):
        raise ValueError('Repeated deals are not independent observations')
    alpha = family_alpha / (generation * (generation + 1) * stages * looks * 2)
    parent = estimate((r['vs_parent'] for r in rows), alpha)
    ben_delta = estimate((r['vs_ben'] - r['parent_vs_ben'] for r in rows), alpha)
    promoted = all(x['informative'] and x['low'] > minimum_gain for x in (parent, ben_delta))
    futile = any(x['informative'] and x['high'] <= minimum_gain for x in (parent, ben_delta))
    return dict(decision='promote' if promoted else 'futile' if futile else 'inconclusive',
                vs_parent=parent, improvement_vs_ben=ben_delta, adjusted_alpha=alpha,
                descriptive={k: estimate((r[k] for r in rows)) for k in
                             ('vs_original', 'vs_parent', 'vs_ben', 'parent_vs_ben')},
                minimum_gain=minimum_gain)
