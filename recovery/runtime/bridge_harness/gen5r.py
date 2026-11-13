"""Gen5R identities and allocation; unchanged networks, large-position quadrature."""
from copy import deepcopy
from pathlib import Path
import json
from .layout_reduction import ReductionConfig
from .training import digest

PAIR_WEIGHTS = {'5R32~4b':16, '5R32~3':8, '5R32~2':6, '5R32~1':2,
                '5R192~ben':2, '5R32~5R192':3, '5R32~5-32':3}
LABELS = {'5R32':'Gen 5R (32)', '5R192':'Gen 5R (192)', '5-32':'Gen 5 (32)',
          '4b':'Gen 4b', '3':'Gen 3', '2':'Gen 2', '1':'Gen 1', 'ben':'BEN (16)'}

def load_plan(path=None):
    p=json.loads(Path(path or Path(__file__).resolve().parents[1]/'configs/round5r.json').read_text())
    if p['pair_weights'] != PAIR_WEIGHTS or set(p['roster']) != set(LABELS):
        raise ValueError('Gen5R requires the requested seven-match allocation')
    if not p['launch_enabled'] or p['pending'] or p['common_bidder'] != '5R32':
        raise ValueError('Gen5R plan is not ready')
    if (p['large_from'],p['large_pool_multiplier'],p['medium_enabled'],p['weighting']) != (10,4,False,'belief'):
        raise ValueError('Gen5R uses large positions only and exact belief moment weights')
    if (p['ben']['bidding'],p['ben']['play_samples'],p['ben']['opening_lead_samples']) != ('neural-only',16,16):
        raise ValueError('Preserve BEN settings')
    return p

def reduction(plan, budget):
    from dataclasses import asdict
    return asdict(ReductionConfig(large_from=plan['large_from'],medium_enabled=False,
        large_pool=budget*plan['large_pool_multiplier'],large_budget=budget,
        large_tolerance=plan['large_tolerance'],weighting=plan['weighting'],ridge=plan['ridge']))

def make_bots(old, plan):
    if old['bots']['5']['artifact_sha256'] != old['bots']['5-32']['artifact_sha256']:
        raise ValueError('Source Gen5 networks differ by effort')
    bots={k:deepcopy(old['bots'][k]) for k in ('4b','3','2','1','ben','5-32')}
    if 'layout_reduction' in bots['5-32']:
        raise ValueError('Baseline must retain random sampling')
    for key, source, budget in [('5R32','5-32',32),('5R192','5',192)]:
        spec=deepcopy(old['bots'][source]);spec.pop('identity')
        spec.update(id=key,samples=budget,layout_reduction=reduction(plan,budget))
        spec['identity']=digest(spec);bots[key]=spec
    return bots
