"""Direct swapped-partnership matches; legacy substitution data stays separate."""
from collections import Counter
import math
from pathlib import Path
import time
import numpy as np
from . import mixed_arena as legacy
from .bidding_env import deal_key
from .core import Board, SEATS, imps
from .fork_audit import collect_board, ForkBudget, stream
from .runner import replay
from .training import digest


def schedule(m, index):
    if not 0 <= index < m['target']: raise ValueError('Index outside frozen cohort')
    # Each seven-board block is shuffled independently, preserving 4:2:1
    # throughout collection, rather than only at the end.
    block = ['AB']*4 + ['AC']*2 + ['BC']
    stream(m['seed'], 'direct-pair-block', index//7).shuffle(block)
    pair = block[index%7]
    return pair, stream(m['seed'], 'direct-table-order', index).randrange(2)


def assignments(m, pair, swapped):
    x,y = (m['direct_versions'][c] for c in pair)
    roles = {m['direct_versions']['A']:'candidate', m['direct_versions']['B']:'reference', m['direct_versions']['C']:'original'}
    ns,ew = (y,x) if swapped else (x,y)
    return [roles[ns],roles[ew],roles[ns],roles[ew]]


def run_board(root,m,board_dict,index):
    board=Board.from_dict(board_dict); pair,order=schedule(m,index)
    specs=m['bots']; names=m['direct_versions']
    players={}
    for label,role in [('A','candidate'),('B','reference'),('C','original')]:
        if label in pair:
            players[role]=legacy.ArenaPlayer(specs[names[label]],root,specs[names['B']] if label=='A' else None)
    versions={label:specs[name]['identity'] for label,name in names.items()}
    seed=int(digest([m['seed'],index,'play'])[:12],16)
    budget=ForkBudget(**m['audit']); tables={}
    try:
        for swapped in (order,1-order):
            budget.max_forks=max(0,m['audit']['max_forks']-budget.forks)
            tables[swapped]=collect_board(board,players,assignments(m,pair,swapped),seed,budget,versions)
        delta=tables[0]['tables'][0]['ns_score']-tables[1]['tables'][0]['ns_score']
        family=deal_key(board.hands,True)
        r=dict(schema='direct-fork-pair-v1',status='ok',generation=m['generation'],index=index,
            family=family,board=board_dict,split=legacy.split(family),pair=pair,execution_order=order,
            versions=versions,manifest_identity=m['identity'],focal=tables[0],control=tables[1],
            score_difference=delta,imps=imps(delta),base_cpu=budget.base_cpu,branch_cpu=budget.branch_cpu,
            completed_epoch=time.time())
        validate_pair(r,m,board,index)
        return r
    finally:
        for p in players.values(): p.close()


def validate_pair(r,m,board,index):
    pair,order=schedule(m,index)
    expected_versions={k:m['bots'][v]['identity'] for k,v in m['direct_versions'].items()}
    if (r['schema']!='direct-fork-pair-v1' or r['board']!=board.to_dict() or r['index']!=index
        or r['manifest_identity']!=m['identity'] or r['pair']!=pair or r['execution_order']!=order
        or r['family']!=deal_key(board.hands,True) or r['split']!=legacy.split(r['family'])
        or r['versions']!=expected_versions): raise ValueError('Changed direct-pair identity')
    for swapped,label in [(0,'focal'),(1,'control')]:
        e=r[label]; replay(e); expected=assignments(m,pair,swapped)
        if e['assignments']!=expected or e['versions']!=expected_versions or e['board']!=r['board']:
            raise ValueError('Wrong direct partnership')
        for table in e['tables']:
            for a in table['actions']:
                if a['player']!=expected[SEATS.index(a['controller'])]: raise ValueError('Wrong controller')
        for audit in e['audits']:
            a=e['tables'][audit['candidate_table']];b=e['tables'][audit['reference_table']];ply=audit['ply']
            if a['actions'][ply]['player']!='candidate': raise ValueError('Audit is not A policy vs B policy')
            if [x['card'] for x in a['actions'][:ply]] != [x['card'] for x in b['actions'][:ply]]:
                raise ValueError('Counterfactual prefix changed')
            if audit['gain_imps']!=imps((a['ns_score']-b['ns_score'])*(1 if audit['actor']%2==0 else -1)):
                raise ValueError('Bad local audit score')
    delta=r['focal']['tables'][0]['ns_score']-r['control']['tables'][0]['ns_score']
    if r['score_difference']!=delta or r['imps']!=imps(delta): raise ValueError('Bad swapped-seat score')


def compact(r):
    events=r['focal']['audits']+r['control']['audits'];actual=[a for a in events if not a['identical_action']]
    return dict(index=r['index'],family=r['family'],split=r['split'],pair=r['pair'],imps=r['imps'],
        audits=len(events),deviations=len(actual),recursive=sum(a['depth']>0 for a in actual),
        local_imp_sum=sum(a['gain_imps'] for a in actual),skips=sum(len(r[k]['budget_skips']) for k in ('focal','control')),
        tables=sum(len(r[k]['tables']) for k in ('focal','control')),base_cpu=r['base_cpu'],branch_cpu=r['branch_cpu'],
        completed_epoch=r['completed_epoch'])


def summarize(rows,m):
    from scipy.stats import t
    rows=sorted(rows,key=lambda r:r['index']);groups={}
    for pair in ('AB','AC','BC'):
        subset=[r for r in rows if r['pair']==pair];v=np.array([r['imps'] for r in subset],float);n=len(v)
        mean=float(v.mean()) if n else None
        half=float(t.ppf(.975,n-1)*v.std(ddof=1)/math.sqrt(n)) if n>1 else None
        groups[pair]=dict(boards=n,imps=int(v.sum()),mean_imps=mean,
            descriptive_95_ci=[mean-half,mean+half] if half is not None else None,
            wins=int((v>0).sum()),losses=int((v<0).sum()),ties=int((v==0).sum()),
            base_cpu=sum(r['base_cpu'] for r in subset),branch_cpu=sum(r['branch_cpu'] for r in subset))
    contiguous=0
    for r in rows:
        if r['index']!=contiguous:break
        contiguous+=1
    n=len(rows);base=sum(r['base_cpu'] for r in rows);branch=sum(r['branch_cpu'] for r in rows)
    return dict(completed=n,target=m['target'],complete=n==m['target'],contiguous=contiguous,
        batch_completed=n+m.get('legacy_completed',0),batch_target=m.get('batch_target',m['target']),
        total_imps=None,by_pair=groups,demotion=None,best=m['candidate'],candidate_status='provisional-no-cross-pair-pooling',
        audited_deviations=sum(r['deviations'] for r in rows),audits=sum(r['audits'] for r in rows),
        tables=sum(r['tables'] for r in rows),base_cpu=base,branch_cpu=branch,
        compute_multiplier=(base+branch)/base if base else None,split_boards=dict(Counter(r['split'] for r in rows)),
        epoch=time.time(),next_step='train-successor' if n==m['target'] else 'collect',
        interpretation='Direct swapped-seat matches, separate AB/AC/BC scores; legacy data excluded from scores.')
