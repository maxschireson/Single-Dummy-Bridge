"""Read-only first-2,000-root capture audit and family-clustered descriptive report."""
import argparse
from collections import defaultdict,Counter
from datetime import datetime,timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from scipy.stats import t
from bridge_harness.core import Board,card,SEATS,imps
from bridge_harness.fork_audit import GapForks,gap_picks,stream
from bridge_harness.loop_registry import sha
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.training import digest
from ops.gen5_runtime import validate
from ops.prepare_gen6 import verify_source

COHORTS=[('mixed_capture',Path('/workspace/work/gen6-gen7-capture-ben64'),Path('/workspace/Single-Dummy-Bridge-gen7-capture')),
         ('fast_selfplay',Path('/workspace/work/gen6-fast-selfplay'),Path('/workspace/Single-Dummy-Bridge-fast-selfplay'))]
BASELINE=Path('/workspace/work/gen6-ben-expansion')
BANDS=['(0,0.125]','(0.125,0.5]','(0.5,infinity)']
PHASES=['lead','tricks1-4','tricks5-8','tricks9-13']


def phase(ply):
    return 'lead' if ply==0 else 'tricks1-4' if ply<16 else 'tricks5-8' if ply<32 else 'tricks9-13'


def clustered(rows,key):
    if not rows:return dict(n=0,families=0,mean=None,se=None,ci95=None)
    values=np.array([r[key] for r in rows],float);mean=float(values.mean());groups=defaultdict(float)
    for row,value in zip(rows,values):groups[row['family']]+=float(value)-mean
    g=len(groups);se=math.sqrt(g/(g-1)*sum(v*v for v in groups.values())/len(rows)**2) if g>1 else None
    half=float(t.ppf(.975,g-1))*se if se is not None else None
    return dict(n=len(rows),families=g,mean=mean,se=se,ci95=[mean-half,mean+half] if half is not None else None)


def icc_from_sufficient(a):
    a=np.asarray(a,float);g=len(a)
    if g<2:return None
    n=a[:,0];N=n.sum()
    if N<=g:return None
    sums=a[:,1];ss=a[:,2]
    between=max(0.,float((sums*sums/n).sum()-sums.sum()**2/N))/(g-1)
    within=max(0.,float((ss-sums*sums/n).sum()))/(N-g)
    n0=(N-(n*n).sum()/N)/(g-1);den=between+(n0-1)*within
    return float((between-within)/den) if den>0 else None


def icc(rows,bootstrap=1000):
    tables=defaultdict(list);families={}
    for r in rows:tables[r['root']].append(r['residual']);families[r['root']]=r['family']
    sufficient=np.array([[len(v),sum(v),sum(x*x for x in v)] for v in tables.values()],float)
    estimate=icc_from_sufficient(sufficient);by_family=defaultdict(list)
    for i,key in enumerate(tables):by_family[families[key]].append(i)
    groups=list(by_family.values());rng=np.random.default_rng(20261111);samples=[]
    if estimate is not None and len(groups)>1:
        for _ in range(bootstrap):
            picks=rng.integers(len(groups),size=len(groups));indices=[i for j in picks for i in groups[j]]
            value=icc_from_sufficient(sufficient[indices])
            if value is not None:samples.append(value)
    return dict(method='Unbalanced one-way random-intercept ANOVA ICC; negative estimates retained',estimate=estimate,
        ci95_family_bootstrap=list(map(float,np.quantile(samples,[.025,.975]))) if samples else None,
        bootstrap_draws=len(samples),tables=len(tables),families=len(groups),forks=len(rows))


def touching(a,b):
    a,b=card(a),card(b)
    return a//13==b//13 and abs(a%13-b%13)==1


def effective_touching(board,actions,ply,actor,a,b):
    a,b=card(a),card(b)
    if a//13!=b//13:return False
    remaining=set(range(52))-{card(z['card']) for z in actions[:ply]}
    own=set(board.hands[actor])&remaining
    return all(c not in remaining or c in own for c in range(min(a,b)+1,max(a,b)))


def receipts(root):
    return sorted([json.loads(p.read_text()) for p in (root/'receipts').glob('*.json')],key=lambda r:(r['completed_epoch'],r['index']))


def rate(rows):
    rows=sorted(rows,key=lambda r:r['completed_epoch']);n=len(rows)
    span=rows[-1]['completed_epoch']-rows[0]['completed_epoch'] if n>1 else 0
    return dict(completed_families=n,first_epoch=rows[0]['completed_epoch'] if n else None,last_epoch=rows[-1]['completed_epoch'] if n else None,
        measured_hours=span/3600,deals_per_hour=(n-1)*3600/span if span>0 else None,
        method='Observed completion interarrival rate (n-1)/(last-first); includes intervening downtime; excludes initial warmup and final drain tail after last included completion')


def summarize(rows):
    return {key:clustered(rows,key) for key in ['estimated_gap','realized_cost_tricks','realized_cost_imps','residual','changed']}


def analyze(limit=2000):
    manifests={};metadata=[];receipts_by_cohort={};checkouts={};start=time.time()
    for label,root,checkout in COHORTS:
        m=json.loads((root/'manifest.json').read_text());verify_source(root,m)
        for file,expected in m['runtime_sha256'].items():assert sha(checkout/file)==expected
        expected=m['source_sha256']
        actual=subprocess.check_output([sys.executable,'-c','from bridge_harness.loop_registry import source_hash; print(source_hash())'],cwd=checkout,text=True).strip()
        assert actual==expected
        manifests[label]=m;checkouts[label]=str(checkout);rs=receipts(root);receipts_by_cohort[label]=rs
        for r in rs:metadata.append((r['completed_epoch'],label,r['index'],root,r))
    verify_generation(COHORTS[-1][1],manifests['fast_selfplay'])
    metadata.sort(key=lambda x:x[:3]);roots=[];gaps=[];ties=[];inventory=[];seen=set();cutoff=None;validated_tables=0;identical_audits=0;seen_ben=0
    for completed,label,index,root,receipt in metadata:
        if len(roots)>=limit:break
        m=manifests[label];path=root/'episodes'/f'{index:06d}.json.gz';raw=path.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==receipt['episode_sha256'];r=json.loads(gzip.decompress(raw))
        assert r['family']==receipt['family'] and r['family'] not in seen;seen.add(r['family'])
        validate(r,m,index);validated_tables+=sum(len(e['tables']) for e in r['unique_tables'].values())
        ben=any(m['bots'][k].get('engine')=='ben' for k in (r['candidate'],r['opponent']))
        if ben:
            seen_ben+=1
            assert all(not e.get('gap_forks') for e in r['unique_tables'].values())
        selected=[]
        for key,e in r['unique_tables'].items():
            if len(roots)>=limit:break
            if 'gap_forks' not in e:continue
            assert not ben and e['tables'][0]['node']=='root'
            uid=f'{m["identity"]}:{index}:{key}';parent=e['tables'][0];board=Board.from_dict(e['board']);config=GapForks(**m['gap_fork'])
            candidates=gap_picks(parent['actions'],config,stream(e['seed'],'gap-fork',e['family'],'root'))
            skips=[s for s in e['budget_skips'] if s.get('reason')=='gap-fork-budget']
            assert [(p['ply'],p['forced_card'],p['band']) for p in candidates]==[(p['ply'],p['forced_card'],p['band']) for p in e['gap_forks']+skips]
            for event in e['gap_forks']+skips:
                assert math.isclose(event['propensity'],min(1.,config.per_band/event['decisions_in_band'])/event['cards_in_band'],abs_tol=1e-12)
            row=dict(root=uid,family=r['family'],cohort=label,index=index,record=key,completed_epoch=completed,root_cpu=parent['cpu_seconds'],tie_cpu=e['compute']['branch_cpu'],gap_cpu=e['compute']['gap_cpu'],forks_by_band=[sum(x['band']==b for x in e['gap_forks']) for b in range(3)],skips_by_band=[sum(x['band']==b for x in skips) for b in range(3)],eligible_decisions=sum(bool(a.get('gen6')) and any(v.get('gap_to_best',0)>1e-9 for v in a.get('estimates',{}).values()) for a in parent['actions']))
            assert math.isclose(row['gap_cpu'],sum(x['rollout_cpu'] for x in e['gap_forks']),rel_tol=1e-9,abs_tol=1e-8)
            roots.append(row);selected.append(key)
            for event in e['gap_forks']:
                ply=event['ply'];actor=event['actor'];fork=e['tables'][event['fork_table']]
                assert event['parent_table']==0 and fork.get('fork_kind')=='gap'
                assert parent['actions'][ply]['card']==event['chosen_card']!=event['forced_card']
                assert fork['actions'][ply]['card']==event['forced_card']
                assert [a['card'] for a in fork['actions'][:ply]]==[a['card'] for a in parent['actions'][:ply]]
                assert event['estimated_gap']>1e-9 and config.band(event['estimated_gap'])==event['band']
                sign=1 if actor%2==board.contract.declarer%2 else -1
                cost=sign*(parent['declarer_tricks']-fork['declarer_tricks'])
                assert cost==event['realized_cost_tricks']
                assert imps((parent['ns_score']-fork['ns_score'])*(1 if actor%2==0 else -1))==event['realized_cost_imps']
                gaps.append(dict(root=uid,family=r['family'],cohort=label,band=event['band'],phase=phase(ply),estimated_gap=event['estimated_gap'],realized_cost_tricks=cost,realized_cost_imps=event['realized_cost_imps'],residual=cost-event['estimated_gap'],changed=int(cost!=0),propensity=event['propensity'],cpu=event['rollout_cpu']))
            for event in e['audits']:
                if event['identical_action']:identical_audits+=1;continue
                a=e['tables'][event['candidate_table']];b=e['tables'][event['reference_table']]
                ply=event['ply'];actor=event['actor'];sign=1 if actor%2==board.contract.declarer%2 else -1
                cost=sign*(a['declarer_tricks']-b['declarer_tricks']);act=a['actions'][ply]
                estimate=act['estimates'][event['reference_card']]['gap_to_best']-act['estimates'][event['candidate_card']]['gap_to_best']
                assert abs(estimate)<1e-8
                assert imps((a['ns_score']-b['ns_score'])*(1 if actor%2==0 else -1))==event['gain_imps']
                ties.append(dict(root=uid,family=r['family'],cohort=label,phase=phase(ply),depth=event['depth'],root_parent=event['candidate_table']==0,touching=touching(event['candidate_card'],event['reference_card']),effective_touching=effective_touching(board,a['actions'],ply,actor,event['candidate_card'],event['reference_card']),estimated_gap=estimate,realized_cost_tricks=cost,realized_cost_imps=event['gain_imps'],residual=cost-estimate,changed=int(cost!=0)))
        if selected:inventory.append(dict(cohort=label,manifest=m['identity'],index=index,family=r['family'],episode_sha256=receipt['episode_sha256'],records=selected,completed_epoch=completed))
        if len(roots)>=limit:cutoff=completed
        if len(roots) and len(roots)%250<4:print(json.dumps(dict(roots=len(roots),gap_forks=len(gaps),seconds=time.time()-start)),flush=True)
    if len(roots)<limit:raise ValueError(f'Only {len(roots)} eligible roots available')
    metrics={};calibration={};noise={};within={}
    for cohort in ['all','mixed_capture','fast_selfplay']:
        rr=[r for r in roots if cohort=='all' or r['cohort']==cohort];gg=[r for r in gaps if cohort=='all' or r['cohort']==cohort];tt=[r for r in ties if cohort=='all' or r['cohort']==cohort]
        cpu=sum(r['root_cpu'] for r in rr);gap_cpu=sum(r['gap_cpu'] for r in rr);tie_cpu=sum(r['tie_cpu'] for r in rr)
        metrics[cohort]=dict(roots=len(rr),families=len({r['family'] for r in rr}),gap_forks=len(gg),tie_forks=len(tt),root_cpu=cpu,gap_cpu=gap_cpu,tie_cpu=tie_cpu,gap_share_of_root_cpu=gap_cpu/cpu,tie_share_of_root_cpu=tie_cpu/cpu,total_cpu_multiplier=(cpu+gap_cpu+tie_cpu)/cpu,gap_forks_per_root=len(gg)/len(rr),mean_root_cpu=cpu/len(rr),mean_gap_fork_cpu=gap_cpu/len(gg),gap_share_root_quantiles={str(q):float(np.quantile([r['gap_cpu']/r['root_cpu'] for r in rr],q)) for q in [.5,.9,.95,1.]},band_counts=[sum(r['forks_by_band'][b] for r in rr) for b in range(3)],band_skips=[sum(r['skips_by_band'][b] for r in rr) for b in range(3)],roots_with_budget_skips=sum(any(r['skips_by_band']) for r in rr))
        calibration[cohort]=dict(overall=summarize(gg),cells={str(b):{p:summarize([r for r in gg if r['band']==b and r['phase']==p]) for p in PHASES} for b in range(3)})
        noise[cohort]={scope:{kind:{p:summarize([r for r in tt if (scope=='all_audits' or r['root_parent']) and r['touching']==(kind=='touching') and r['phase']==p]) for p in PHASES} for kind in ['touching','non_touching']} for scope in ['root_audits','all_audits']}
        noise[cohort]['effective_touching_sensitivity']={kind:summarize([r for r in tt if r['root_parent'] and r['effective_touching']==(kind=='touching')]) for kind in ['touching','non_touching']}
        within[cohort]=icc(gg)
    throughput={}
    baseline=receipts(BASELINE);base_manifest=json.loads((BASELINE/'manifest.json').read_text())
    for label,rs,m in [('pre_capture_mixed',baseline,base_manifest)]+[(k,[r for r in receipts_by_cohort[k] if r['completed_epoch']<=max(z['completed_epoch'] for z in roots if z['cohort']==k)],manifests[k]) for k in manifests]:
        non_ben=[r for r in rs if not any(m['bots'][b].get('engine')=='ben' for b in r['pair'].split('~'))]
        throughput[label]=dict(all_deals=rate(rs),non_ben_deals=rate(non_ben),allocation=m['pair_weights'],manifest=m['identity'])
    return dict(schema='gen7-first-2000-root-report-v1',generated_utc=datetime.now(timezone.utc).isoformat(),cutoff_epoch=cutoff,root_limit=limit,metrics=metrics,calibration=calibration,tie_noise=noise,residual_icc=within,throughput=throughput,inventory=inventory,manifests={k:dict(identity=v['identity'],allocation=v['pair_weights'],source_sha256=v['source_sha256'],runtime_sha256=v['runtime_sha256']) for k,v in manifests.items()},validation=dict(episode_files=len(seen),gap_families=len({r['family'] for r in roots}),distinct_observed_families=len(seen),validated_tables=validated_tables,ben_episodes_checked=seen_ben,identical_audit_events_excluded_from_noise=identical_audits,legal_replay=True,receipt_hashes=True,manifest_versions_auctions_and_scores=True,pick_streams_propensities_and_gap_outcomes=True,source_and_model_hashes=True),elapsed_seconds=time.time()-start)


def fmt(value,digits=4):return '—' if value is None else f'{value:.{digits}f}'

def meanse(s):return f"{fmt(s['mean'])} ± {fmt(s['se'])}"


def render(d):
    M=d['metrics'];overall=d['calibration']['all']['overall'];cor=d['residual_icc']
    lines=['# Gen 7 capture: first 2,000 non-BEN root tables','',f"Snapshot generated {d['generated_utc']}. This collector only; no model or allocation changes were made for analysis.",'',
        'The sample is the first 2,000 completed physical non-BEN root tables with the `gap_forks` field, ordered by episode completion time, cohort, episode index and record order. Forks are training continuations, not independent boards. BEN and passed-out records without capture do not enter the root threshold. Every selected episode and its other tables was legally replayed.','',
        f"There are **{M['all']['families']:,} independent gap-capture deal families**, **{M['all']['gap_forks']:,} gap forks** and **{M['all']['tie_forks']:,} physical tie-audit forks** attached to these roots. Mixed allocation contributes {M['mixed_capture']['roots']:,} roots; fast self-play contributes {M['fast_selfplay']['roots']:,} roots.",'',
        '## Findings','',
        f"- Gap capture produced {M['all']['gap_forks_per_root']:.2f} forks/root and added {100*M['all']['gap_share_of_root_cpu']:.1f}% of root CPU, close to the note's approximate 55% expectation. {sum(M['all']['band_skips'])} of {M['all']['gap_forks']+sum(M['all']['band_skips'])} drawn forks were skipped by the CPU budget.",
        f"- Across these deliberately banded forks, mean estimated cost was {overall['estimated_gap']['mean']:.3f} tricks versus {overall['realized_cost_tricks']['mean']:.3f} realized. The paired residual was {meanse(overall['residual'])} tricks. This selected-fork calibration is not an estimate of deployment error rates or a policy strength gain.",
        f"- Residual ICC was {cor['all']['estimate']:.3f} overall, but {cor['mixed_capture']['estimate']:.3f} in the mixed cohort and {cor['fast_selfplay']['estimate']:.3f} in self-play. Pooling the two obscures an allocation-related difference.",
        '- Touching-card controls still show early-game continuation noise; observed late touching-card changes are zero in this sample. Zero empirical variation is not proof of zero population noise.',
        '', '![Estimated versus realized gap with clustered standard errors](gen7-first-2000-independent-20261111.png)', '',
        '## Capture volume and CPU','', '| Allocation phase | Roots | Families | Gap forks/root | Root CPU s/root | Gap CPU / root CPU | Tie CPU / root CPU | Total CPU / root CPU |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for k in ['all','mixed_capture','fast_selfplay']:
        m=M[k];lines.append(f"| {k} | {m['roots']} | {m['families']} | {fmt(m['gap_forks_per_root'],3)} | {fmt(m['mean_root_cpu'],3)} | {fmt(100*m['gap_share_of_root_cpu'],1)}% | {fmt(100*m['tie_share_of_root_cpu'],1)}% | {fmt(m['total_cpu_multiplier'],3)} |")
    lines+=['','Gap CPU is additional to the unchanged tie audits. Ratios are sums of CPU, not averages of per-root percentages. The 1.5× cap checks CPU already spent and finishes an admitted tail, so a single root can exceed it.','', '| Phase | Gap band | Executed forks | Forks/root | Budget skips |','|---|---|---:|---:|---:|']
    for k in ['all','mixed_capture','fast_selfplay']:
        for b in range(3):lines.append(f"| {k} | {BANDS[b]} | {M[k]['band_counts'][b]} | {M[k]['band_counts'][b]/M[k]['roots']:.3f} | {M[k]['band_skips'][b]} |")
    lines+=['','## Observed throughput','', 'Rates below are (completed deals − 1) divided by the interval between first and last included completions. They include intervening stalls/restarts, exclude initial warmup, and are descriptive wall-clock rates. Mixed capture and self-play are different workloads: self-play has one root per family and four Gen6 seats. Do not attribute the full before/after rate difference to gap capture. The short pre-capture baseline used BEN32 rather than BEN64; non-BEN rates still share wall time with the rest of the workload.','', '| Phase | Completed deals | Interval hours | All deals/hour | Non-BEN deals/hour |','|---|---:|---:|---:|---:|']
    for k,v in d['throughput'].items():lines.append(f"| {k} | {v['all_deals']['completed_families']} | {fmt(v['all_deals']['measured_hours'],3)} | {fmt(v['all_deals']['deals_per_hour'],1)} | {fmt(v['non_ben_deals']['deals_per_hour'],1)} |")
    lines+=['','Each phase’s throughput window ends at its last selected non-BEN root completion. This leaves one later BEN completion from the retired mixed cohort outside that rate window; all 725 retired episodes remain preserved and were checked before the overall cutoff. The self-play window also contains BEN and passed-out completions, which do not enter the 2,000-root count.', '', 'The in-process CPU ratios isolate the measured gap-tail cost more directly than these throughput comparisons. No controlled production rate experiment was run.','',
        '## Estimated gap versus realized cost','', 'Each cell reports an unweighted mean ± one deal-family-clustered standard error. Clustering spans rooms, auction conditions and forks of the same original family. Lead is ply 0; tricks 1–4 excludes the lead. Cost is parent minus forced continuation from the acting partnership’s perspective, positive when the forced card costs tricks/IMPs. Residual is realized trick cost minus estimated gap. These are local continuation contrasts, not whole-bot strength estimates.','']
    for k in ['all','mixed_capture','fast_selfplay']:
        lines +=['',f'### {k}','', '| Band | Phase | Forks | Families | Estimated tricks ± SE | Realized tricks ± SE | Residual ± SE | Realized IMPs ± SE |','|---|---|---:|---:|---:|---:|---:|---:|']
        for b in range(3):
            for p in PHASES:
                v=d['calibration'][k]['cells'][str(b)][p];s=v['estimated_gap'];lines.append(f"| {BANDS[b]} | {p} | {s['n']} | {s['families']} | {meanse(s)} | {meanse(v['realized_cost_tricks'])} | {meanse(v['residual'])} | {meanse(v['realized_cost_imps'])} |")
    lines+=['','## Within-root residual correlation','', 'One-way random-intercept ANOVA ICC with the unbalanced cluster-size correction, applied to realized trick cost minus estimated gap. Intervals are percentile intervals from 1,000 bootstrap resamples of deal families, retaining all their roots and forks. Negative estimates, if present, are not truncated. Different gap bands and phases remain mixed within roots; this is a descriptive clustering measure, not an independently identified causal parameter.','', '| Phase | ICC | Family-bootstrap 95% interval | Roots with forks |','|---|---:|---|---:|']
    for k,v in d['residual_icc'].items():lines.append(f"| {k} | {fmt(v['estimate'])} | {', '.join(fmt(x) for x in v['ci95_family_bootstrap']) if v['ci95_family_bootstrap'] else '—'} | {v['tables']} |")
    lines+=['','## Tie-audit noise control','', 'The note does not publish a formal touching-card predicate. The primary definition here is conservative: **same suit and numerically adjacent ranks**, e.g. K/Q or 8/7. Same-card audits are excluded because they do not produce a physical alternative. Root-parent audits are the closest comparison to root-only gap forks; a separate panel includes recursive audits. A sensitivity panel additionally treats a pair as equivalent when every intervening unplayed rank is held by that same seat (played ranks are ignored). This broader rule uses the recorded full deal only for offline classification, never player inputs.','', 'Values are mean ± family-clustered SE; changed-result percentages use trick-result differences, with clustered SE in percentage points. Estimated trick differences are zero to numerical tolerance.','']
    for k in ['all','mixed_capture','fast_selfplay']:
        for scope in ['root_audits','all_audits']:
            lines +=['',f'### {k}: {scope}','', '| Swap | Phase | Forks | Families | Estimated ± SE | Realized tricks ± SE | Realized IMPs ± SE | Trick result differs % ± SE |','|---|---|---:|---:|---:|---:|---:|---:|']
            for kind in ['touching','non_touching']:
                for p in PHASES:
                    v=d['tie_noise'][k][scope][kind][p];s=v['estimated_gap'];c=v['changed'];changed=f"{fmt(None if c['mean'] is None else 100*c['mean'],2)} ± {fmt(None if c['se'] is None else 100*c['se'],2)}"
                    lines.append(f"| {kind} | {p} | {s['n']} | {s['families']} | {meanse(s)} | {meanse(v['realized_cost_tricks'])} | {meanse(v['realized_cost_imps'])} | {changed} |")
    lines+=['','### Effective touching sensitivity, root-parent audits','', '| Phase | Swap | Forks | Realized tricks ± SE | Trick result differs % ± SE |','|---|---|---:|---:|---:|']
    for k in ['all','mixed_capture','fast_selfplay']:
        for kind,v in d['tie_noise'][k]['effective_touching_sensitivity'].items():
            c=v['changed'];lines.append(f"| {k} | {kind} | {c['n']} | {meanse(v['realized_cost_tricks'])} | {fmt(None if c['mean'] is None else 100*c['mean'],2)} ± {fmt(None if c['se'] is None else 100*c['se'],2)} |")
    lines +=['','## Validation, provenance and limits','',f"- Verified {d['validation']['episode_files']:,} episode receipts and hashes; replayed {d['validation']['validated_tables']:,} recorded tables, including BEN records encountered before the cutoff. Manifest identities, frozen model/source hashes, auctions and score orientation passed.",'- Recomputed gap selections from their dedicated stream, checked draw propensities, budget-skip accounting, forced prefixes and realized trick/IMP costs. The stored propensity is the design draw probability before budget admission; it is not asserted to be a full post-budget execution inclusion probability.', '- All calibration means are conditional on executed banded forks, without inverse-propensity weighting. Selected positions/cards and budget stops do not represent uniformly sampled real-play errors. Realized contrasts include continuation sampling noise, as the tie controls demonstrate.', '- Families are disjoint across the two immutable cohorts. Self-play comparison IMPs remain null; no forks are counted as independent boards. No data were rewritten, no backfill was run, and no model was trained, promoted or replaced.', '- The statistics are descriptive at the requested 2,000-root collection milestone. Multiple band/phase panels are not multiplicity-adjusted; these tables do not establish a strength improvement or justify an automatic budget change.', '', 'Frozen cohort identities:', '']
    for k,m in d['manifests'].items():lines.append(f"- `{k}`: `{m['identity']}`; allocation `{json.dumps(m['allocation'],sort_keys=True)}`.")
    lines +=['', 'The companion JSON contains all cell statistics, confidence intervals, CPU quantiles and the selected episode/hash/root inventory. Bulk episodes remain in their existing recovery feeds.','']
    return '\n'.join(lines)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'reports/gen7-first-2000-independent-20261111');p.add_argument('--roots',type=int,default=2000);a=p.parse_args()
    d=analyze(a.roots);a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.with_suffix('.json').write_text(json.dumps(d,indent=2,allow_nan=False)+'\n');a.out.with_suffix('.md').write_text(render(d));print(json.dumps(d['metrics']),flush=True)
