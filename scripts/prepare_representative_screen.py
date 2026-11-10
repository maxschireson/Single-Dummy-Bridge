"""Freeze 200 independent validation deals, excluding the earlier geometry data."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import random
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.core import Board, Game, card
from scripts.test_representative_sampling import seed
from scripts.prepare_layout_embedding import save


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--exclude-contexts',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--count',type=int,default=200);p.add_argument('--large-fraction',type=float,default=.8)
    p.add_argument('--reference-check-contexts',type=Path);a=p.parse_args()
    if not 0<=a.large_fraction<=1:raise ValueError('Invalid stage fraction')
    manifest=json.loads(a.manifest.read_text())
    with gzip.open(a.exclude_contexts,'rt') as f:excluded={r['family'] for r in json.load(f)}
    excluded.update(manifest['reserved_families'])
    candidates=[r for r in manifest['normalized_sources'] if r['split']=='validation' and r['family'] not in excluded]
    random.Random(2026111035).shuffle(candidates)
    large=round(a.count*a.large_fraction);rows=[];skipped=[]
    for candidate in candidates:
        if len(rows)==a.count:break
        stage='large' if len(rows)<large else 'medium';family=candidate['family'];choices=[]
        for source in candidate['sources']:
            if not source.get('policy_clean'):continue
            raw=Path(source['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=source['sha256']:raise ValueError('Source checksum changed')
            ep=json.loads(gzip.decompress(raw))
            if ep['family']!=family:raise ValueError('Family mismatch')
            for room in ep.get('unique_tables',{}).values():
                if room.get('status')!='ok' or not room['board'].get('contract') or not room.get('tables'):continue
                trajectory=room['tables'][0];game=Game(Board.from_dict(room['board']))
                for action in trajectory['actions']:
                    o=game.observation();remaining=13-len(o.history)//4
                    if len(o.legal)>1 and ((stage=='large' and remaining>=10) or (stage=='medium' and 7<=remaining<=9)):
                        choices.append(dict(family=family,split='validation',stage=stage,remaining=remaining,board=room['board'],
                            history=[c for _,c in o.history],source=source['path'],source_sha256=source['sha256']))
                    game.play(card(action['card']))
        if not choices:skipped.append(family);continue
        rows.append(random.Random(seed(family,'independent-screen')).choice(choices))
    if len(rows)!=a.count:raise ValueError(f'Only {len(rows)} eligible validation deals')
    if a.reference_check_contexts:
        prior=json.loads(a.reference_check_contexts.read_text())
        checks={r['family'] for r in prior if r.get('double_reference')}
        if not checks <= {r['family'] for r in rows}:raise ValueError('Missing reference-check families')
        for r in rows:
            if r['family'] in checks:r['double_reference']=True
    else:
        for stage,n in [('large',round(large*.1)),('medium',round((a.count-large)*.1))]:
            indices=[i for i,r in enumerate(rows) if r['stage']==stage]
            random.Random(seed(stage,'reference-check')).shuffle(indices)
            for i in indices[:n]:rows[i]['double_reference']=True
    random.Random(2026111036).shuffle(rows)
    save(a.out,rows)
    save(a.out.with_suffix('.manifest.json'),dict(count=len(rows),families=len({r['family'] for r in rows}),
        stages=dict(large=large,medium=a.count-large),excluded_families=len(excluded),skipped=skipped,
        source_manifest=str(a.manifest),source_sha256=hashlib.sha256(a.manifest.read_bytes()).hexdigest(),
        policy='One position per family; clean normalized validation sources only; original geometry and reserved test families excluded.',
        double_reference=sum(r.get('double_reference',False) for r in rows)))
    print(json.dumps(dict(prepared=len(rows),large=large,medium=a.count-large)),flush=True)


if __name__=='__main__':main()
