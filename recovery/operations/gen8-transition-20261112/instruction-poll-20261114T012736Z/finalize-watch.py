from pathlib import Path
import datetime
import json
import os

C=Path('/workspace/work/gen6-fast-selfplay-stream')
CASE=Path(__file__).resolve().parent
def read(p):
    return json.loads(p.read_text())
w=read(C/'instruction-watch.json')
scan=read(CASE/'github-scan.json')
h=read(CASE/'health-after.json')
a=read(CASE/'automation-state.json')
research=read(CASE/'research-commit-review.json')
s=read(C/'stream.json')
assert s['seed']==6586995816951042092
assert (C/'stream.json').read_bytes()==(CASE/'stream-before.json').read_bytes()
assert w['next_comment_scan_since']==scan['comments_since']
assert scan['branch_scan']['pages'][-1]<100
oldrefs=w['watched_source_refs']
newrefs=scan['refs']
newbranches=sorted(set(newrefs)-set(oldrefs))
removed=sorted(set(oldrefs)-set(newrefs))
assert newbranches==['feature/gen9-genx-stu'] and not removed,(newbranches,removed)
peer_review=read(CASE/'genx-stu-peer-review.json')
assert peer_review['new_branch_reviewed'] and not peer_review['adopted_by_this_stream']
assert newrefs['feature/gen9-genx-stu']==peer_review['revision']=='43d555eb48be2d80405a5bea86b464bf9d864b19'
for path,sha in scan['main_files'].items():
    assert w['file_revisions'][path]==sha,(path,sha)
for path,sha in scan['source_files'].items():
    assert w['source_file_revisions']['paths'][path]==sha,(path,sha)
assert scan['pages']['owned_entries']==w['registry_review']['owned_entries']
oldcase=Path(w['scan_evidence_path']).parent
oldscan=read(oldcase/'github-scan.json')
for path,row in oldscan['versioned_plans'].items():
    assert scan['versioned_plans'][path]==row,path
assert set(scan['versioned_plans'])-set(oldscan['versioned_plans'])=={'configs/round9-genx-stu.json'}
assert scan['versioned_plans']['configs/round9-genx-stu.json']['scope'].startswith('Explicit Max authority to Gen9/will on Azure4')
assert h['same_pids_as_previous_poll'] and h['cache_rotation_already_diagnosed']
assert len(h['all_lineage_locks'])==18
assert not scan['comments']['issue_comments'] and not scan['comments']['review_comments']
assert not read(CASE/'commit-comments.json')['comments']
assert read(CASE/'collector-environment-review.json')['frozen_net_and_scorer_have_no_bf16_path']
start=scan['poll_start']
w['previous_check']={'checked_at':w['checked_at'],'scan_evidence_path':w['scan_evidence_path']}
w['checked_at']=start
w['checked_epoch']=datetime.datetime.fromisoformat(start.replace('Z','+00:00')).timestamp()
w['completed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')
w['comments_since']=scan['comments_since']
w['next_comment_scan_since']=start
w['result']=scan['result']
w['collection_action']='Continue current immutable Gen8 collection; no restart, drain, source/settings/model/worker change, training, promotion, registry or shared UI mutation.'
w['notification']='quiet: no current applicable collection instruction changed and no new blocker or completion'
w['instruction_changes']=[]
w['watched_source_refs']=newrefs
w['checked_paths']=list(dict.fromkeys(w['checked_paths']+[v['path'] for v in scan['checked_files'].values()]))
w['scan_evidence_path']=str(CASE/'github-scan.json')
w['stream_manifest']=s['manifest']
w['health']=h
w['comment_scan']={'poll_start':start,'comments_since':scan['comments_since'],'next_comment_scan_since':start,'new_issue_comments':[],'new_review_comments':[],'new_review_submissions':[],'new_commit_comments':[],'complete':True}
w['new_issue_comments']=[]
w['new_review_comments']=[]
w['recent_issues']=scan['issues']
w['recent_prs']=scan['recent_prs']
w['automation_context'].update(a)
w['automation_context']['evidence']=str(CASE/'automation-state.json')
w['next_check']=a['next_run_time']
w['registry_review'].update(revision=scan['pages']['revision'],blob=scan['pages']['registry_blob'],owned_entries=scan['pages']['owned_entries'],disposition='All six owned entries and retired pins are unchanged; no registry edit.')
w['coordination_review'].update(read(CASE/'coordination-review.json'))
w['source_file_revisions']={'ref':newrefs['feature/gen8-prototype-20261112'],'paths':scan['source_files']}
w['poll_checkpoint_note']='Comments scan is anchored to poll START, not finish. Current watch/recovery publication is independently verified after the existing publisher captures these exact bytes; proof is in this case.'
w['completion_status']={'completed':h['state']['completed'],'target':s['target'],'complete':False,'source_budget_only':True,'gen71_comparison_gate_enabled':False,'selfplay_launch_enabled':False}
w['stu_scope_review']['latest_poll_review']={'poll_start':start,'revision':research['revision'],'commits':research['commits'],'scope':research['scope'],'disposition':research['disposition'],'applied':False,'evidence':str(CASE/'research-commit-review.json')}
w['latest_scope_review']={'revision':scan['coordination']['revision'],'blob':scan['coordination']['blob'],'entry':scan['coordination']['latest_entry'],'scope':scan['coordination']['scope'],'disposition':scan['coordination']['disposition'],'continuing_authority':scan['coordination']['continuing_general_authority'],'current_effect':'Continue immutable Gen8 source 792c4cb, manifest cd98, five-pair main mix, three normal workers, zero BEN and source budget 18283. The Gen X Stu opening is specifically for Will/Gen9 on Azure4. No all-collector switch or Codex actor/source/settings change is authorized.'}
w['genx_stu_peer_review']=peer_review
w['research_disposition']='Gen X Stu is now authorized for Will/Gen9 on Azure4 under its own ready plan. That scoped peer opening does not redirect this Codex collector. Stu loop training, model measurement, row aliases and further research remain unadopted by this stream. Preserve the current immutable Gen8 cohort and all released-model exclusion requirements for any later new cohort.'
w['future_gen9_review']['latest_genx_peer_review']={'poll_start':start,'branch':peer_review['branch'],'revision':peer_review['revision'],'plan':peer_review['plan']['path'],'plan_blob':peer_review['plan']['sha'],'launch_enabled':True,'scope':'Will/Gen9 on Azure4 only; no local switch','adopted_by_this_stream':False,'evidence':str(CASE/'genx-stu-peer-review.json')}
w['performance_proposal_review']['research_revision']=research['revision']
w['performance_proposal_review']['applied']=False
w['performance_proposal_review']['latest_poll_review']={'number':34,'head':scan['performance_proposal']['head'],'state':scan['performance_proposal']['state'],'merged':scan['performance_proposal']['merged'],'reviews':[],'frozen_source_retained':True,'conditional_bf16_guidance_applies':False,'current_runtime_has_no_bf16_path':True}
w['publisher_retry_review']['latest_poll_recheck']={'poll_start':start,'current_publisher':h['publisher'],'disposition':'Earlier retry and its unconfirmed cause remain archived. Current publication is fresh; no manual restart, push or configuration change.'}
w['shared_reporting_review']['latest_poll_review']={'revision':scan['pages']['revision'],'index_blob':scan['pages']['index_blob'],'replay_blob':scan['pages']['replay_blob'],'shared_ui_mutated':False,'known_replay_blocker_unchanged':True,'ladder_mount_preserved':True}
for b in w['blockers']:
    if b.get('path')=='arena/replays/common.js':
        b.update(last_checked_revision=scan['pages']['revision'],last_checked_blob=scan['pages']['replay_blob'],already_notified_previous_poll=True,repeat_notification=False,approval_received=False)
pr=read(oldcase/'publication-proof.json')
w['recovery_validation'].update(current_publication=h['publisher'],latest_poll_checkpoint=str(CASE),preceding_checkpoint=str(oldcase/'publication-proof.json'),verified_revision=pr['revision'],watch_blob=pr['watch_blob'],final_watch_copy_to_verify_separately=True)
p=C/'instruction-watch.json.tmp'
p.write_text(json.dumps(w,indent=2,ensure_ascii=False)+'\n')
os.replace(p,C/'instruction-watch.json')
(CASE/'live-capture-sample.json').write_text(json.dumps(h['live_capture_sample'],indent=2)+'\n')
(CASE/'branch-review.json').write_text(json.dumps({'poll_start':start,'total':len(newrefs),'new_branches':newbranches,'removed_branches':removed,'changed_refs':{k:{'before':oldrefs[k],'after':v} for k,v in newrefs.items() if oldrefs[k]!=v},'complete':True},indent=2)+'\n')
print(json.dumps({'poll_start':start,'comments_since':scan['comments_since'],'next_comment_scan_since':w['next_comment_scan_since'],'result':w['result'],'completed':h['state']['completed'],'source_unchanged':True,'watch_bytes':(C/'instruction-watch.json').stat().st_size,'next_check':w['next_check']}))
