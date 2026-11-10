"""Prepare and summarize a bounded belief-only integration smoke test."""
import argparse,copy,gzip,json,math,sys,time
from pathlib import Path
import shutil
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.bidding_env import make_board,deal_key
from bridge_harness.loop_registry import sha
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest

def prepare(a):
    source=json.loads((a.source/'manifest.json').read_text())
    root=a.run.resolve()
    if root.exists():raise ValueError('Use a new immutable smoke directory')
    selected=json.loads((a.candidate.parent/'result.json').read_text())
    if sha(a.candidate)!=selected['selected_sha256']:raise ValueError('Candidate hash mismatch')
    spec=copy.deepcopy(source['bots']['4b'])
    if spec['artifact_sha256']['policy']=='e179a71ed132dcd0f9ca06b486ec087e9f5b26edb4210e99ed2e04c9439b21ed':
        raise ValueError('Bad v4 policy is forbidden')
    data=json.loads((a.data/'dataset.json').read_text())
    frozen=json.loads((a.data/'manifest.json').read_text())
    excluded={f['family'] for f in frozen['families']}
    for entry in data['shards']:
        with np.load(entry['file'],allow_pickle=False) as z:excluded.update(map(str,z['split_group']))
    from bridge_harness.core import Board
    for line in (a.source/source['corpus']).read_text().splitlines():
        excluded.add(deal_key(Board.from_dict(json.loads(line)).hands,True))
    boards=[];families=set();index=0
    while len(boards)<a.boards:
        board=make_board(a.seed,index,'dev');index+=1
        family=deal_key(board.hands,True)
        if family in excluded or family in families:continue
        families.add(family);boards.append(board.to_dict())
    (root/'models').mkdir(parents=True)
    for kind,checksum in spec['artifact_sha256'].items():
        path=a.source/spec[kind]
        if sha(path)!=checksum:raise ValueError('Changed source model')
        shutil.copyfile(path,root/spec[kind])
    candidate=copy.deepcopy(spec);candidate.update(id='gen5b-smoke',label='V5 belief smoke candidate',belief='models/belief-v5.npz')
    shutil.copyfile(a.candidate,root/candidate['belief'])
    candidate['artifact_sha256']['belief']=sha(a.candidate)
    candidate['identity']=digest({k:v for k,v in candidate.items() if k!='identity'})
    corpus=root/'boards.jsonl';corpus.write_text(''.join(json.dumps(b)+'\n' for b in boards))
    repo=Path(__file__).resolve().parents[1]
    runtime={str(p.relative_to(repo)):sha(p) for p in (repo/'bridge_harness').glob('*.py')}
    for name in ['bridge_harness/libbridge_dds.so','scripts/run_supplemental_arena.py','scripts/belief_play_smoke.py']:
        runtime[name]=sha(repo/name)
    m=dict(schema='v4-two-auction-arena-v1',title='Bounded v5 belief smoke versus 4b',purpose='integration smoke; not a significance test',
        roster=['5b','4b'],bots={'5b':candidate,'4b':spec},target=a.boards,seed=a.seed,
        corpus=corpus.name,corpus_sha256=sha(corpus),runtime_sha256=runtime,
        audit=dict(probability=0.,multiplier=1.,max_depth=0,max_forks=0),pair_schedule=[['5b','4b']],
        audit_references={'5b':'4b'},common_bidder='4b',two_self_rooms=True,independent_room_seeds=False,
        source_manifest=source['identity'],candidate_selected_epoch=selected['best_epoch'],
        excluded_known_families=len(excluded),reserved_test_evaluated=False,promoted=False,
        interpretation='Same bidder, policy, search, contracts and per-ply random streams; swap partnerships. Common and native regimes coincide and must be counted once.')
    m['identity']=digest(m);atomic_json(root/'manifest.json',m)
    atomic_json(root/'created_epoch.json',time.time());atomic_json(root/'families.json',sorted(families))
    print(json.dumps(dict(run=str(root),target=a.boards,samples=spec['samples'],excluded_families=len(excluded),candidate_sha256=sha(a.candidate))))

def summarize(a):
    from bridge_harness.runner import replay
    from bridge_harness.core import imps
    root=a.run;m=json.loads((root/'manifest.json').read_text());rows=[];actions=0;passed=0;max_seconds=0.
    for path in sorted((root/'episodes').glob('*.json.gz')):
        with gzip.open(path,'rt') as f:r=json.load(f)
        if r['manifest_identity']!=m['identity']:raise ValueError('Wrong manifest')
        common,native=r['regimes']['common'],r['regimes']['native']
        if common!=native:raise ValueError('Same bidder produced different regimes')
        ids=common['tables']
        if len(ids)!=2 or len(r['unique_tables'])!=2:raise ValueError('Expected two swapped tables')
        scores=[]
        for room,table_id in enumerate(ids):
            table=r['unique_tables'][table_id]
            expected=['candidate' if s%2==room else 'opponent' for s in range(4)]
            if table['assignments']!=expected:raise ValueError('Partnership mismatch')
            if table['board']['contract'] is not None:
                replay(table)
                if len(table['tables'])!=1 or len(table['tables'][0]['actions'])!=52:raise ValueError('Incomplete play')
                actions+=52
            if table['audits']:raise ValueError('Unexpected branching')
            scores.append(table['tables'][0]['ns_score'])
            max_seconds=max(max_seconds,table['tables'][0].get('seconds',0.))
        if common['imps']!=imps(scores[0]-scores[1]):raise ValueError('Bad paired IMP score')
        passed+=r['unique_tables'][ids[0]]['board']['contract'] is None
        rows.append(dict(index=r['index'],family=r['family'],imps=common['imps'],score_difference=scores[0]-scores[1]))
    if len({r['family'] for r in rows})!=len(rows):raise ValueError('Duplicate family')
    values=np.array([r['imps'] for r in rows],float);n=len(values)
    failures=(root/'errors.jsonl').read_text().splitlines() if (root/'errors.jsonl').exists() else []
    result=dict(complete=n==m['target'],boards=n,target=m['target'],played_boards=n-passed,passed_out_boards=passed,
        paired_tables=2*n,replayed_card_actions=actions,failures=len(failures),total_imps=int(values.sum()),
        mean_imps=float(values.mean()) if n else None,se_imps=float(values.std(ddof=1)/math.sqrt(n)) if n>1 else None,
        wins=int((values>0).sum()),losses=int((values<0).sum()),ties=int((values==0).sum()),
        max_table_seconds=max_seconds,wall_seconds=time.time()-json.loads((root/'created_epoch.json').read_text()),
        manifest_identity=m['identity'],candidate_sha256=m['bots']['5b']['artifact_sha256']['belief'],
        reference_sha256=m['bots']['4b']['artifact_sha256']['belief'],rows=rows,
        reserved_test_evaluated=False,promoted=False,
        interpretation='Smoke test only. No estimate here establishes a small strength difference; common/native records counted once.')
    atomic_json(root/'result.json',result);print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','summarize']);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--source',type=Path);p.add_argument('--candidate',type=Path);p.add_argument('--data',type=Path)
    p.add_argument('--boards',type=int,default=50);p.add_argument('--seed',type=int,default=202611100741)
    a=p.parse_args();prepare(a) if a.command=='prepare' else summarize(a)

if __name__=='__main__':main()
