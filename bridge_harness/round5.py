"""Validate and schedule the pending v5 arena; never launch unprovided models."""
from fractions import Fraction
import json
from pathlib import Path
import random

from .training import digest


def members(pair):
    return pair.split('~') if '~' in pair else list(pair)


def validate_plan(plan):
    roster=set(plan['roster'])
    if roster & {'4','4p','P'} or '4b' not in roster or not {'5','ben'}<=roster:
        raise ValueError('v5 roster must retain 4b, exclude 4/4p, and include v5/BEN')
    if plan.get('v5_samples')!=192 or plan.get('historical_v5_samples')!=32:raise ValueError('Gen5 uses 32 vs older bots and 192 vs BEN/control')
    total=sum(plan['pair_weights'].values());ben_weight=0
    for pair,weight in plan['pair_weights'].items():
        pair_members=members(pair)
        if len(pair_members)!=2 or any(v not in roster for v in pair_members):raise ValueError('Invalid matchup')
        if not isinstance(weight,int) or isinstance(weight,bool) or weight<=0:raise ValueError('Positive integer weights required')
        if set(pair_members)&{'4b','3','2','1'} and pair_members[0]!='5-32':raise ValueError('Historical comparisons require Gen5 at 32 samples')
        if 'ben' in pair_members:
            if set(pair_members)!={'5','ben'}:raise ValueError('BEN may only face v5')
            ben_weight+=weight
    if Fraction(ben_weight,total)!=Fraction(str(plan['ben_match_fraction'])):raise ValueError('BEN allocation differs from declared fraction')
    ben=plan['ben']
    if ben['bidding']!='neural-only' or ben['opening_lead_samples']!=16 or ben['play_samples']!=16:raise ValueError('BEN requires neural bidding and 16-sample lead/play')
    return plan


def load_plan(path=None):
    path=path or Path(__file__).resolve().parents[1]/'configs/round5.json'
    return validate_plan(json.loads(Path(path).read_text()))


def schedule(plan,count,seed):
    validate_plan(plan)
    if count<1:raise ValueError('Positive match count required')
    weights=plan['pair_weights'];block=[p for p,n in weights.items() for _ in range(n)]
    rows=[]
    for i in range((count+len(block)-1)//len(block)):
        shuffled=block.copy();random.Random(int(digest([seed,'round5-block',i])[:16],16)).shuffle(shuffled)
        rows.extend(shuffled[:count-len(rows)])
    # Exact declared allocation in each full block; a partial tail is approximate.
    return rows


def require_ready(plan):
    validate_plan(plan)
    if not plan.get('launch_enabled') or plan.get('pending'):
        raise RuntimeError('v5 launch is pending the user model/upgrade handoff')
    if not plan.get('bots',{}).get('5',{}).get('identity'):
        raise RuntimeError('Frozen v5 actor identity required')
