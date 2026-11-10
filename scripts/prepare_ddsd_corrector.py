"""Freeze existing clean continuations and label them with true-deal DDS.

Outcomes are observed chosen-action tails, not synthetic labels for unplayed
cards. Forks are retained only for held-out diagnostics. No new play is run.
"""
import argparse
from collections import Counter,defaultdict
from concurrent.futures import ProcessPoolExecutor
import gzip,hashlib,json,os,random,sys,time,zipfile
from pathlib import Path
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.core import Board,Game,card
from bridge_harness.bidding_env import deal_key
from bridge_harness.dds import DDS
from bridge_harness.ddsd_corrector import encode,SCHEMA
from scripts.policy_choice_data import family_split,validate_event

SOLVER=None
REGISTRY={}
ARCHIVES={}

def bind_roles(ep,provenance):
    versions=ep['versions'];mapping={}
    if 'A' in versions:
        mapping={'candidate':'A','reference':'B','original':'C'}
    elif 'candidate' not in versions:
        source=provenance['source']
        if 'export_provenance' in source:
            mapping=source['export_provenance']['actor_bots']
        else:
            if 'archive' in source:
                if source['archive'] not in ARCHIVES:ARCHIVES[source['archive']]=zipfile.ZipFile(source['archive'])
                raw=ARCHIVES[source['archive']].read(source['member'])
            else:raw=Path(source['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=source['sha256']:raise ValueError('Original provenance changed')
            original=json.loads(gzip.decompress(raw))
            mapping={'candidate':original['candidate'],'opponent':original['opponent'],'environment':original['opponent']}
    ep['_role_versions']={role:versions[mapping.get(role,'opponent' if role=='environment' else role)]
        for role in set(ep['assignments'])}

def init_worker(library,registry):
    global SOLVER,REGISTRY
    SOLVER=DDS(library,cache_path='');REGISTRY=registry

def policy_context(ep,o):
    # Four per-controller descriptors: policy generation, sample effort,
    # belief use, near-tie window. No family/source/outcome identifiers.
    result=[]
    for offset in range(4):
        seat=(o.controller+offset)%4
        if seat==o.contract.dummy:seat=o.contract.declarer
        role=ep['assignments'][seat]
        identity=ep['_role_versions'][role]
        spec=REGISTRY.get(identity)
        if spec is None:raise ValueError('Unknown active continuation identity '+str((role,identity)))
        h=spec.get('artifact_sha256',{}).get('policy')
        generations={None:0,'02b6885e8f07da473970052d7f9ea9dc2a10fa34505ad60186e4a14d02218c60':2,
            '8c62c88b0f2041ce78273e072d0b5530598255cc39b482826901ff1660e064f5':3}
        if h not in generations:raise ValueError('Non-clean continuation policy')
        result.extend([generations[h]/6,spec.get('samples',32)/192,
            float(bool(spec.get('artifact_sha256',{}).get('belief'))),spec.get('near_tie',.125)])
    return result

def process(item):
    index,path,expected_hash,cap,pair_cap=item
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_hash:raise ValueError('Source changed')
    record=json.loads(gzip.decompress(raw));family=record['family'];split=family_split(family)
    if not record.get('policy_clean'):raise ValueError('Require policy-clean normalized corpus')
    if (record['split']=='train')!=(split=='train'):raise ValueError('Split boundary changed')
    episodes=record['unique_tables']; candidates=defaultdict(list); events=[];seen=set()
    for room,ep in episodes.items():
        if not ep.get('tables') or ep['board'].get('contract') is None:continue
        bind_roles(ep,record['provenance'][int(room)])
        if deal_key(Board.from_dict(ep['board']).hands,True)!=family:raise ValueError('Wrong family')
        for ti,table in enumerate(ep['tables']):
            key=(json.dumps(ep['board'],sort_keys=True),ep['seed'],tuple(a['card'] for a in table['actions']))
            if key in seen:continue
            seen.add(key)
            for ply,a in enumerate(table['actions']):
                if a.get('replayed_prefix'):continue
                if a.get('counterfactual_forced') or len(a.get('estimates',{}))>1:
                    phase=0 if ply<16 else 1 if ply<36 else 2
                    candidates[phase].append((room,ti,ply))
        if split!='train':
            for e in ep['audits']:
                if not e['identical_action']:
                    validate_event(ep,e);events.append((room,e))
    rng=random.Random(int(family[:16],16)); selected=set()
    limits=(max(1,cap*3//8),max(1,cap*3//8),max(1,cap-cap*6//8))
    for phase,limit in enumerate(limits):
        selected.update(rng.sample(candidates[phase],min(limit,len(candidates[phase]))))
    events=rng.sample(events,min(pair_cap,len(events)))
    needed=set(selected)
    for room,e in events:
        needed.update((room,ti,e['ply']) for ti in (e['candidate_table'],e['reference_table']))
    rows={};cache={};nodes=0;solve_seconds=0.;native=0
    for room,ep in episodes.items():
        if not ep.get('tables') or ep['board'].get('contract') is None:continue
        board=Board.from_dict(ep['board'])
        for ti,table in enumerate(ep['tables']):
            plies={p for r,t,p in needed if r==room and t==ti}
            if not plies:continue
            game=Game(board)
            for ply,a in enumerate(table['actions']):
                c=card(a['card'])
                if ply in plies:
                    o=game.observation();hands=tuple(tuple(sorted(h)) for h in game.hands)
                    key=(hands,o.contract.trump,o.leader,o.trick)
                    if key not in cache:
                        started=time.perf_counter();values,n=SOLVER.solve(hands,o.contract.trump,o.leader,o.trick)
                        solve_seconds+=time.perf_counter()-started;nodes+=n;native+=1;cache[key]=values
                    dd=cache[key][c]
                    declaring=o.actor%2==o.contract.declarer%2
                    final=table['declarer_tricks'] if declaring else 13-table['declarer_tricks']
                    already=o.declarer_tricks if declaring else ply//4-o.declarer_tricks
                    y=final-already
                    if not 0<=dd<=13-ply//4 or not 0<=y<=13-ply//4:raise ValueError('Bad target horizon')
                    context=policy_context(ep,o);x,calls=encode(o,hands,c,dd,context)
                    rows[room,ti,ply]=dict(x=x,calls=calls,dd=dd,y=y,ply=ply,declaring=declaring,
                        family=index,split=split,depth=table['depth'])
                game.play(c)
            if not game.done or game.declarer_tricks!=table['declarer_tricks'] or game.ns_score()!=table['ns_score']:
                raise ValueError('Invalid completed continuation')
    outcomes=[rows[k] for k in sorted(selected)]
    pairs=[]; pair_metadata=[]
    for room,e in events:
        a=rows[room,e['candidate_table'],e['ply']];b=rows[room,e['reference_table'],e['ply']]
        ep=episodes[room];table=ep['tables'][e['candidate_table']]
        pairs.append(dict(x=np.stack([a['x'],b['x']]),calls=np.stack([a['calls'],b['calls']]),
            dd=np.array([a['dd'],b['dd']]),y=np.array([a['y'],b['y']]),family=index,
            ply=e['ply'],declaring=a['declaring'],split=split))
        g=Game(Board.from_dict(ep['board']))
        for z in table['actions'][:e['ply']]:g.play(card(z['card']))
        o=g.observation();context=policy_context(ep,o)
        pair_metadata.append(dict(family=family,family_index=index,split=split,board=ep['board'],
            prefix=[z['card'] for z in table['actions'][:e['ply']]],
            cards=[e['candidate_card'],e['reference_card']],outcomes=[a['y'],b['y']],
            true_dd=[a['dd'],b['dd']],policy_features=context,depth=e['depth'],
            source=path,room=room,seed=ep['seed']))
    return outcomes,pairs,pair_metadata,dict(family=family,index=index,split=split,rows=len(outcomes),
        pairs=len(pairs),native_solves=native,dds_nodes=nodes,dds_seconds=solve_seconds,
        candidate_positions=sum(map(len,candidates.values())))

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--library',required=True)
    p.add_argument('--workers',type=int,default=2);p.add_argument('--cap',type=int,default=16)
    p.add_argument('--pairs',type=int,default=4);p.add_argument('--limit',type=int)
    p.add_argument('--registry',type=Path,action='append',default=[])
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((a.source/'manifest.json').read_text());registry={}
    for m in manifest['source_manifests'].values():
        for spec in m['bots'].values():registry[spec['identity']]=spec
    additional=[json.loads(p.read_text()) for p in a.registry]
    for m in additional:
        for spec in m['bots'].values():registry[spec['identity']]=spec
    files=sorted((a.source/'episodes').glob('*.json.gz'))
    if a.limit:files=files[:a.limit]
    source=[dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]
    config=dict(schema=SCHEMA,source_manifest=manifest,additional_registries=additional,source=source,cap=a.cap,pairs=a.pairs,
        split='Existing canonical modulo-ten: 0 test, 5 validation; others train',
        target='Observed remaining acting-partnership tricks minus actual-deal DD after specified card',
        selection='Outcome-blind seeded phase-stratified observed decisions; forks diagnostic only',
        dds_sha256=hashlib.sha256(Path(a.library).read_bytes()).hexdigest(),created_epoch=time.time())
    (a.out/'config.json').write_text(json.dumps(config))
    buffers=defaultdict(list);shards=[];families=[];totals=Counter();started=time.time()
    pair_file=gzip.open(a.out/'pair-positions.jsonl.gz','wt')
    def flush():
        for (kind,split),rows in buffers.items():
            if not rows:continue
            data={k:np.stack([r[k] for r in rows]) for k in rows[0] if k!='split'}
            data['x']=data['x'].astype(np.float16);data['calls']=data['calls'].astype(np.uint8)
            dest=a.out/f'{kind}-{split}-{len(shards):04}.npz';np.savez_compressed(dest,**data)
            shards.append(dict(file=dest.name,kind=kind,split=split,rows=len(rows),
                sha256=hashlib.sha256(dest.read_bytes()).hexdigest()));rows.clear()
    items=[(i,s['path'],s['sha256'],a.cap,a.pairs) for i,s in enumerate(source)]
    with ProcessPoolExecutor(a.workers,initializer=init_worker,initargs=(a.library,registry)) as pool:
        for i,(outcomes,pairs,metadata,stats) in enumerate(pool.map(process,items,chunksize=4)):
            for r in outcomes:buffers['outcomes',r['split']].append(r)
            for r in pairs:buffers['pairs',r['split']].append(r)
            for r in metadata:pair_file.write(json.dumps(r,separators=(',',':'))+'\n')
            families.append(stats);totals.update({k:v for k,v in stats.items() if k in ('rows','pairs','native_solves','dds_nodes','dds_seconds','candidate_positions')})
            if (i+1)%128==0 or i+1==len(items):
                flush();pair_file.flush()
                status=dict(families=i+1,total=len(items),seconds=time.time()-started,**totals)
                (a.out/'status.json').write_text(json.dumps(status));print(json.dumps(status),flush=True)
    pair_file.close();(a.out/'families.json').write_text(json.dumps(families))
    (a.out/'dataset.json').write_text(json.dumps(dict(schema=SCHEMA,shards=shards,totals=dict(totals),
        families=len(families),seconds=time.time()-started),indent=2))

if __name__=='__main__':main()
