"""Report a fresh follow-up separately from a result-dependent pooled sample."""
import argparse,json,math,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.loop_registry import sha
from bridge_harness.selfplay import atomic_json

def summarize(rows):
    v=np.asarray([r['imps'] for r in rows],float);n=len(v)
    mean=float(v.mean());se=float(v.std(ddof=1)/math.sqrt(n))
    return dict(boards=n,total_imps=int(v.sum()),mean_imps=mean,se_imps=se,total_imp_se=se*n,
        descriptive_95_normal_interval=[mean-1.96*se,mean+1.96*se],
        mean_over_se=mean/se if se else None,wins=int((v>0).sum()),losses=int((v<0).sum()),ties=int((v==0).sum()))

def main():
    p=argparse.ArgumentParser();p.add_argument('--first',type=Path,required=True);p.add_argument('--followup',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=[];manifests=[];time_seconds=[]
    for root in (a.first,a.followup):
        r=json.loads((root/'result.json').read_text());m=json.loads((root/'manifest.json').read_text())
        if not r['complete'] or r['boards']!=m['target']:raise ValueError('Incomplete batch')
        if r['manifest_identity']!=m['identity']:raise ValueError('Wrong manifest')
        result.append(r);manifests.append(m)
        status=json.loads((root/'status.json').read_text())
        time_seconds.append(status['updated_epoch']-status['started_epoch'])
    first,new=result
    for key in ('bots','audit','common_bidder','two_self_rooms','independent_room_seeds','pair_schedule','runtime_sha256'):
        if manifests[0][key]!=manifests[1][key]:raise ValueError('Changed comparison: '+key)
    if set(r['family'] for r in first['rows']) & set(r['family'] for r in new['rows']):raise ValueError('Family overlap')
    if manifests[1]['followup_of']!=manifests[0]['identity']:raise ValueError('Wrong parent batch')
    groups=dict(first_50=summarize(first['rows']),new_100=summarize(new['rows']),combined_150=summarize(first['rows']+new['rows']))
    doc=dict(candidate_sha256=first['candidate_sha256'],reference_sha256=first['reference_sha256'],groups=groups,
        runs=[dict(path=str(root),manifest_sha256=sha(root/'manifest.json'),result_sha256=sha(root/'result.json'),
                   execution_seconds=seconds) for root,seconds in zip((a.first,a.followup),time_seconds)],
        failures=sum(r['failures'] for r in result),paired_tables=sum(r['paired_tables'] for r in result),
        replayed_card_actions=sum(r['replayed_card_actions'] for r in result),reserved_test_evaluated=False,promoted=False,
        interpretation='The new 100 are an unchanged-model, fixed-size follow-up. Combined 150 intervals are descriptive because extension was requested after observing the first 50. All inference is by unique paired deal, never by tables or repeated regimes.')
    atomic_json(a.output.with_suffix('.json'),doc)
    lines=['# Dense v5 belief: 100-board follow-up','',
        'The same selected dense v5 belief model played 100 additional fresh paired deals against 4b. '
        'Only belief weights differ: v3 policy and bidding, 32 search layouts, near-tie threshold 0.125, '
        'zero exploration, matched contracts and common per-ply random streams are unchanged.','',
        '| Batch | Paired boards | Total IMPs | IMP/board ± SE | Mean/SE | Wins / losses / ties |',
        '|---|---:|---:|---:|---:|---:|']
    for name,g in groups.items():
        lines.append(f"| {name} | {g['boards']} | {g['total_imps']:+d} | {g['mean_imps']:+.3f} ± {g['se_imps']:.3f} | {g['mean_over_se']:+.2f} | {g['wins']} / {g['losses']} / {g['ties']} |")
    lines+=['',doc['interpretation'],'',
        f"All {doc['paired_tables']} tables completed with {doc['failures']} failures; {doc['replayed_card_actions']:,} card actions passed legal replay. "
        'The original and follow-up cohorts are family-disjoint. Common/native outputs coincide and are counted once. '
        'No reserved test families were used, no model was promoted, and attention remains paused.','',
        f"The new batch took {time_seconds[1]/60:.2f} minutes with two workers. Its seed was {manifests[1]['seed']}. "
        'Collection stopped at 100 additional boards without a performance-based early stop.','',
        f"Candidate SHA256: `{first['candidate_sha256']}`. Reference SHA256: `{first['reference_sha256']}`.",'',
        '[Original smoke test](belief_v5_play_smoke_2026-11-10.md) · '
        '[Candidate model and restore instructions](../models/cardplay/gen5-belief-size-loss-2026-11-10)']
    a.output.with_suffix('.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(groups,indent=2))

if __name__=='__main__':main()
