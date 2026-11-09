"""Freeze policy-clean play sources, merging rooms by canonical deal family."""
import argparse
from collections import Counter, defaultdict
import gzip, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.belief_capacity import sha
from scripts.screen_attention_belief import split, save_json, PREFLIGHT_EXCLUDED

BAD_POLICY='e179a71ed132dcd0f9ca06b486ec087e9f5b26edb4210e99ed2e04c9439b21ed'
CLEAN_NAMES={'1','2','3','3early','3.5','4b','Q'}

def clean_local(episode):
    """Use the two ACTIVE bot identities, not unused manifest bot specs."""
    names={episode.get('candidate'),episode.get('opponent')}
    return len(names)>=1 and names <= CLEAN_NAMES

def freeze(old_screen, transfer, output):
    old=json.loads((old_screen/'manifest.json').read_text())
    by_family=defaultdict(dict);counts=Counter()
    def add(family,source_split,source):
        expected='validation' if int(family[:8],16)%5==0 else 'train'
        if source_split!=expected:raise ValueError('Source split mismatch')
        if family in PREFLIGHT_EXCLUDED:return
        by_family[family][source['sha256']]=source
    for entry in old['families']:
        for source in entry['sources']:
            p=Path(source['path'])
            if sha(p)!=source['sha256']:raise ValueError('Old source changed')
            episode=json.loads(gzip.decompress(p.read_bytes()))
            if not clean_local(episode):counts['excluded_local_episodes']+=1;continue
            counts['retained_local_episodes']+=1
            add(entry['family'],episode['split'],dict(**source,policy_clean=True))
    provenance=json.loads((transfer/'provenance.json').read_text())
    family_splits=json.loads((transfer/'family-splits.json').read_text())
    for record in provenance:
        active=record['active_bots'];mapped=set(record['actor_bots'].values())
        if not mapped or not mapped<=set(active):raise ValueError('Incomplete actor provenance')
        if any(not active[n].get('policy_sha256') or active[n]['policy_sha256']==BAD_POLICY for n in mapped):
            raise ValueError('Contaminated exported policy')
        p=transfer/record['file']
        if sha(p)!=record['sha256']:raise ValueError('Export file changed')
        episode=json.loads(gzip.decompress(p.read_bytes()))
        if episode['family']!=record['family'] or episode['split']!=record['split']:
            raise ValueError('Export provenance mismatch')
        if episode['split']!=family_splits[episode['family']]:raise ValueError('Family split changed')
        actors={record['actor_bots'].get(n,n) for n in episode['assignments']}
        if not actors<=mapped:raise ValueError('Unverified active actor')
        counts['retained_export_games']+=1
        add(record['family'],record['split'],dict(path=str(p.resolve()),sha256=record['sha256'],
            policy_clean=True,active_policy_sha256=sorted({active[n]['policy_sha256'] for n in mapped})))
    families=[dict(family=f,split=split(f),sources=list(s.values())) for f,s in sorted(by_family.items())]
    counts.update({'families_'+s:sum(e['split']==s for e in families) for s in ('train','validation','test')})
    result=dict(schema='policy-clean-belief-sources-v1',families=families,counts=dict(counts),
        old_screen_manifest_sha256=sha(old_screen/'manifest.json'),export_sha256=sha(transfer/'export.json'),
        provenance_sha256=sha(transfer/'provenance.json'),excluded_policy_sha256=BAD_POLICY,
        split_rule='Keep inherited train boundary; divide held-out families into validation (hash%10=5) and test (hash%10=0).')
    save_json(output,result);print(json.dumps(result['counts']),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--old-screen',type=Path,required=True)
    p.add_argument('--transfer',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();freeze(a.old_screen,a.transfer,a.out)
