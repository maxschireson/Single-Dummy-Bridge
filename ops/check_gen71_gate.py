"""Read-only, snapshot-pinned family-deduplicated Gen71 policy comparison gate."""
import concurrent.futures as cf
import hashlib
import json
import math
from pathlib import Path
import statistics
import urllib.request
from scipy.stats import t


def gate(values):
    n=len(values);mean=statistics.mean(values) if n else None
    se=statistics.stdev(values)/math.sqrt(n) if n>1 else None
    ci=[mean-float(t.ppf(.975,n-1))*se,mean+float(t.ppf(.975,n-1))*se] if se is not None else None
    return dict(n=n,mean=mean,se=se,ci=ci,minimum_boards=1000,eligible=bool(n>=1000 and ci is not None and ci[0]>0),
                method='Nominal paired Student-t95%, family-deduplicated native/total IMPs; repeated monitoring, no sequential correction')


def check(control,registry,heads):
    mine=json.loads((Path(control['target'])/'manifest.json').read_text());actor=mine['bots']['71s-32'];old=mine['bots']['7s-32']
    trained=set(json.loads((Path(control['target'])/'artifacts/validation/all-training-families.json').read_text()))
    pairs={p for p in mine['pair_weights'] if len(set(p.split('~')))>1}
    def get(url):
        with urllib.request.urlopen(url,timeout=45) as f:return f.read()
    def worker(s):
        revision=s.get('revision') or heads[s['branch']];base='https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/'+revision+'/arena/'
        m=json.loads(get(base+'manifest.json'));assert m['identity']==s['cohort']
        if '71s-32' not in m['bots']:return None
        candidate=m['bots']['71s-32']
        for key in ('artifact_sha256','gen7','gen6','samples'):assert candidate[key]==actor[key],(s['branch'],key)
        if '7s-32' in m['roster']:
            for key in ('artifact_sha256','gen7','gen6','samples'):assert m['bots']['7s-32'][key]==old[key],(s['branch'],'old',key)
        prefix=base+'replays/data/'+m['identity']+'/';idx=json.loads(get(prefix+'index.json'));assert idx['versions']['71s-32']==candidate['identity'];rows=list(idx.get('records',[]))
        for name in idx.get('record_shards',[]):
            raw=get(prefix+name);assert hashlib.sha256(raw).hexdigest()==idx['record_shard_sha256'][name];v=json.loads(raw);rows.extend(v if isinstance(v,list) else v['records'])
        return dict(branch=s['branch'],revision=revision,cohort=m['identity'],rows=rows)
    sources=[s for s in registry['sources'] if (s.get('group')=='gen7' or str(s.get('generation','')).startswith('7')) and not any(x in s['branch'] for x in ('pre7','trial','test','prototype'))]
    found=[];errors=[]
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        fs={pool.submit(worker,s):s for s in sources}
        for f in cf.as_completed(fs):
            try:
                result=f.result()
                if result:found.append(result)
            except Exception as e:errors.append(dict(branch=fs[f]['branch'],error=repr(e)))
    seen={p:{} for p in pairs};excluded={p:set() for p in pairs}
    for src in found:
        for row in src['rows']:
            pair=row['pair'];value=row.get('own_imps');reverse='~'.join(reversed(pair.split('~')))
            if pair not in seen and reverse in seen:pair=reverse;value=-value if isinstance(value,(int,float)) else None
            if pair not in seen or not isinstance(value,(int,float)):continue
            family=row['family']
            if family in trained:excluded[pair].add(family);continue
            key=(row['completed_epoch'],src['branch'],row['index'])
            if family not in seen[pair] or key<seen[pair][family][0]:seen[pair][family]=(key,value)
    comparison=gate([r[1] for r in seen.get('71s-32~7s-32',{}).values()]);comparison['eligible']=comparison['eligible'] and not errors
    return dict(counts={p:len(rows) for p,rows in seen.items()},excluded_training_families={p:len(rows) for p,rows in excluded.items()},gate=comparison,
                sources=[{k:v for k,v in s.items() if k!='rows'} for s in found],errors=errors)


if __name__=='__main__':
    import argparse,time
    p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--registry',type=Path,required=True);p.add_argument('--heads',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    heads={l.split()[1].removeprefix('refs/heads/'):l.split()[0] for l in a.heads.read_text().splitlines()}
    out=check(json.loads(a.control.read_text()),json.loads(a.registry.read_text()),heads);out['checked_epoch']=time.time();a.out.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
