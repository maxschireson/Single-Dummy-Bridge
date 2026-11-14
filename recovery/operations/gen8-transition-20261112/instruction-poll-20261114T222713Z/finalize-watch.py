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
initial=read(CASE/'health-before.json')
a=read(CASE/'automation-state.json')
research=read(CASE/'research-commit-review.json')
s=read(C/'stream.json')
assert s['seed']==6586995816951042092
assert (C/'stream.json').read_bytes()==(CASE/'stream-before.json').read_bytes()
assert (C/'instruction-watch.json').read_bytes()==(CASE/'instruction-watch-before.json').read_bytes()
assert w['next_comment_scan_since']==scan['comments_since']
assert scan['branch_scan']['complete'] and scan['branch_scan']['pages'][-1]<100
oldrefs=w['watched_source_refs']
newrefs=scan['refs']
branch=read(CASE/'branch-review.json')
assert set(newrefs)-set(oldrefs)=={row['branch'] for row in branch['reviewed_new_branches']}
assert not set(oldrefs)-set(newrefs)
assert all(row['applied'] is False for row in branch['reviewed_new_branches'])
for path,sha in scan['main_files'].items():
    assert w['file_revisions'][path]==sha,(path,sha)
for path,sha in scan['source_files'].items():
    assert w['source_file_revisions']['paths'][path]==sha,(path,sha)
assert {r['key']:r for r in scan['pages']['owned_entries']}=={r['key']:r for r in w['registry_review']['owned_entries']}
oldcase=Path(w['scan_evidence_path']).parent
oldscan=read(oldcase/'github-scan.json')
for path,value in scan['versioned_plans'].items():
    if path in oldscan['versioned_plans']:
        assert value['sha']==oldscan['versioned_plans'][path]['sha'],path
    else:
        assert path=='configs/round9-genx-stu-r4c.json'
        assert value['adopted_by_this_stream'] is False
        assert value['sha']=='b0fb4004ab450246274fc6bc6e1cd12deb2860e1'
assert scan['coordination']['new_entries_since_prior_poll']==len(scan['coordination']['board_commits'])
assert scan['coordination']['blob']!=oldscan['coordination']['blob']
assert scan['coordination']['new_entries_since_prior_poll']==17
assert scan['performance_proposal']['head']==oldscan['performance_proposal']['head']
assert scan['generation_cleanup']['head']==oldscan['generation_cleanup']['head']
rotation=read(CASE/'cache-rotation-diagnosis.json')
assert h['same_pids_as_initial_check'] and h['cache_rotation_diagnosed_in_this_poll']
assert rotation['old_collector_pid']==w['health']['pids']['collector']
assert rotation['new_collector_pid']==h['pids']['collector']
assert not rotation['requires_attention'] and not rotation['failures_cleared'] and not rotation['manual_restart']
assert h['pids']==initial['pids']
assert h['cache_rotation']==rotation['journal']
assert len(h['all_lineage_locks'])==18
assert len(scan['comments']['issue_comments'])==33 and not scan['comments']['review_comments']
assert {row['issue_number'] for row in scan['comments']['issue_comments']}=={35,37,38,39,40,41,42,43,44}
assert read(CASE/'stu-efficiency-scope-review.json')['owned_collection_instruction_changed'] is False
assert not read(CASE/'commit-comments.json')['comments']
assert all(not scan['comments'][k] for k in ['reviews32','reviews34','reviews33','reviews35','reviews36','reviews37','reviews38','reviews40','reviews41','reviews42','reviews43','reviews45'])
assert h['live_capture_sample']['actual_capture_observed']
assert h['state']['completed']<s['target'] and not h['state']['complete']
for name,lock in h['all_lineage_locks'].items():
    expected={'.writer.lock':h['pids']['collector'],'.watchdog.lock':h['pids']['supervisor'],'.publisher.lock':h['pids']['publisher']}[Path(name).name]
    assert lock['owner_pid']==(expected if lock['current'] else None)
start=scan['poll_start']
w['previous_check']={'checked_at':w['checked_at'],'scan_evidence_path':w['scan_evidence_path']}
w['checked_at']=start
w['checked_epoch']=datetime.datetime.fromisoformat(start.replace('Z','+00:00')).timestamp()
w['completed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')
w['comments_since']=scan['comments_since']
w['next_comment_scan_since']=start
w['result']=scan['result']
w['collection_action']='Continue the same immutable Gen8 cohort. Healthy three-normal/zero-BEN collection, existing owner/locks and DDS guard retained. No manual restart, failure clearance, source/settings/model/worker/cache change, new cohort, training, promotion, registry or shared UI mutation.'
w['notification']='quiet: no current applicable collection instruction changed and no new blocker or completion'
w['instruction_changes']=[]
w['watched_source_refs']=newrefs
w['checked_paths']=list(dict.fromkeys(w['checked_paths']+[v['path'] for v in scan['checked_files'].values()]))
w['scan_evidence_path']=str(CASE/'github-scan.json')
w['stream_manifest']=s['manifest']
w['health']=h
w['comment_scan']={'poll_start':start,'comments_since':scan['comments_since'],'next_comment_scan_since':start,'new_issue_comments':scan['comments']['issue_comments'],'new_review_comments':[],'new_review_submissions':[],'new_commit_comments':[],'complete':True}
w['new_issue_comments']=scan['comments']['issue_comments']
w['new_review_comments']=[]
w['recent_issues']=scan['issues']
w['recent_prs']=scan['recent_prs']
w['automation_context'].update(a)
w['automation_context'].update(evidence=str(CASE/'automation-state.json'),changed_this_poll=False,schedule_preserved=True)
w['next_check']=a['next_run_time']
w['registry_review'].update(revision=scan['pages']['revision'],blob=scan['pages']['registry_blob'],owned_entries=scan['pages']['owned_entries'],disposition='All six owned entries and retired pins unchanged; no registry edit.')
w['coordination_review'].update(read(CASE/'coordination-review.json'))
w['source_file_revisions']={'ref':newrefs['feature/gen8-prototype-20261112'],'paths':scan['source_files']}
w['poll_checkpoint_note']='Comments scan anchored to poll START, not finish. Verify exact final watch/recovery bytes through the existing publisher; pinned proof saved separately in this case.'
w['completion_status']={'completed':h['state']['completed'],'target':s['target'],'complete':False,'source_budget_only':True,'gen71_comparison_gate_enabled':False,'selfplay_launch_enabled':False}
w['stu_scope_review']['latest_poll_review']={'poll_start':start,'revision':research['revision'],'commits':research['commits'],'scope':research['scope'],'disposition':research['disposition'],'applied':False,'evidence':str(CASE/'research-commit-review.json')}
w['latest_scope_review']={'revision':scan['coordination']['revision'],'blob':scan['coordination']['blob'],'entry':scan['coordination']['latest_entry'],'scope':scan['coordination']['scope'],'disposition':scan['coordination']['disposition'],'continuing_authority':scan['coordination']['continuing_general_authority'],'current_effect':'Continue immutable Gen8 source792c4cb, manifestcd98, approved five-pair mix, three normal/zero BEN, target18283, original training exclusions and disabled legacy gates. Gen9 cohort-sync/BEN-loader maintenance is Azure4-scoped; USBC scoring and fixed-deal tests remain research, test-only and never trained on. No local cache/source/settings/worker change or data import.'}
peer=read(CASE/'genx-stu-peer-review.json')
assert w['genx_stu_peer_review']['registration']['entry']['cohort']==peer['registration']['entry']['cohort']
w['genx_stu_peer_review'].update(peer)
assert peer['archived_previous_genx']['registration']['retired'] is True
assert peer['archived_previous_genx']['state']['completed']==719
assert 'round4c' in peer['registration']['authority']
w['genx_stu_peer_review']['queued_status']='Registered and running on Azure4; dated pinned snapshot '+str(peer['state']['completed'])+'/4000, zero failures. Read-only; no peer operation.'
w['research_disposition']=research['disposition']
w['future_gen9_review']['latest_genx_operational_review']={'poll_start':start,'registered':True,'registration_key':peer['registration']['entry']['key'],'feed_revision':peer['feed_revision'],'manifest':peer['registration']['entry']['cohort'],'source_commit':peer['current_branch_revision'],'completed':peer['state']['completed'],'target':4000,'failures':peer['state']['failures'],'adopted_by_this_stream':False,'evidence':str(CASE/'genx-stu-peer-review.json')}
w['performance_proposal_review']['applied']=False
w['performance_proposal_review']['latest_poll_review']={'number':34,'head':scan['performance_proposal']['head'],'state':scan['performance_proposal']['state'],'merged':scan['performance_proposal']['merged'],'reviews':[],'frozen_source_retained':True,'conditional_bf16_guidance_applies':False,'current_runtime_has_no_bf16_path':True}
w['publisher_retry_review']['latest_poll_recheck']={'poll_start':start,'current_publisher':h['publisher'],'disposition':'Earlier retry and its unconfirmed cause preserved. Current publication fresh; no manual restart, push or configuration change.'}
w['shared_reporting_review']['latest_poll_review']={'revision':scan['pages']['revision'],'index_blob':scan['pages']['index_blob'],'replay_blob':scan['pages']['replay_blob'],'shared_ui_mutated':False,'known_replay_blocker_unchanged':True,'ladder_mount_preserved':True}
for b in w['blockers']:
    if b.get('path')=='arena/replays/common.js':
        b.update(last_checked_revision=scan['pages']['revision'],last_checked_blob=scan['pages']['replay_blob'],already_notified_previous_poll=True,repeat_notification=False,approval_received=False)
pr=read(oldcase/'publication-proof.json')
w['recovery_validation'].update(current_publication=h['publisher'],latest_poll_checkpoint=str(CASE),preceding_checkpoint=str(oldcase/'publication-proof.json'),verified_revision=pr['revision'],watch_blob=pr['watch_blob'],final_watch_copy_to_verify_separately=True)
w['reviewed_new_branches'].setdefault('history',[]).append({'poll_start':start,'branches':branch['reviewed_new_branches'],'evidence':str(CASE/'branch-review.json'),'owned_stream_changed':False})
ownership=read(CASE/'ownership-review.json')
assert ownership['strict_source_hash_check_retained'] and not ownership['source_amendments_file_exists']
assert (Path(s['run'])/'source-amendments.json').exists() is False
amend=read(CASE/'source-amendment-scope-review.json')
assert amend['applied'] is False and amend['local_guard_retained']
assert isinstance(w['source_adoption_review'],dict)
w['source_adoption_review']['latest_source_amendment_scope_review']=amend
w['performance_proposal_review']['latest_stu_bf16_bucket_review']=read(CASE/'performance-scope-review.json')
w['host_resource_review']['latest_peer_source_amendment_review']={'poll_start':start,'revision':amend['revision'],'applied':False,'current_source_strict_guard_retained':True,'local_amendments_file_exists':False,'evidence':str(CASE/'source-amendment-scope-review.json')}
w['latest_mail_channel_review']=read(CASE/'mail-channel-review.json')
human=read(CASE/'human-training-scope-review.json')
assert human['applied_to_this_stream'] is False and not human['datasets_or_models_downloaded'] and not human['local_training'] and not human['local_corpus_changed']
w['latest_human_training_scope_review']=human
w['stu_scope_review']['latest_human_training_scope_review']=human
w['performance_proposal_review']['latest_stu_performance_scope_review']=read(CASE/'performance-scope-review.json')
w['future_training_exclusion_scope']={'poll_start':start,'requirement':'Any future new cohort excludes complete pinned training-family membership of ALL released models, including human/bot/replay experiment families if released. Current frozen list/proofs remain unchanged; seed or row counts are not membership evidence.','evidence':str(CASE/'human-training-scope-review.json')}
assert peer['state']['manifest_identity']==peer['registration']['entry']['cohort'] and peer['state']['failures']==0
w['stu_scope_review']['latest_versioned_research_plan_review']={'poll_start':start,'revision':research['revision'],'blob':research['research_plan_blob'],'status':research['research_plan_status'],'scope':'Stu H05/V1 validation, optional new variable persona IDs for Loop/g9/server and accepted corrected d82/4951 research screens/BEN. Explicit expanded research authority does not adopt a primary actor/source or change this frozen stream.','applied':False,'evidence':str(CASE/'research-commit-review.json')}
w['stu_scope_review']['latest_human_table_rule_review']={'poll_start':start,**human['latest_human_table_rule'],'evidence':str(CASE/'human-training-scope-review.json')}
w['stu_scope_review']['latest_genx_r4c_scope_review']={'poll_start':start,'source_commit':peer['current_branch_revision'],'feed_revision':peer['feed_revision'],'manifest':peer['registration']['entry']['cohort'],'adopted_on_azure4':True,'adopted_by_this_stream':False,'r3_retired_at':719,'complete_released_training_membership_verified_here':False,'evidence':str(CASE/'genx-stu-peer-review.json')}
w['stu_scope_review']['latest_sidplay_scope_review']=read(CASE/'sidplay-scope-review.json')
w['messages_sent']=False
assert w['health']['pids']['collector']==335661
assert len(w['cache_rotation_history'])==14
assert w['last_diagnosed_cache_rotation']==read(CASE/'instruction-watch-before.json')['last_diagnosed_cache_rotation']
assert w['cache_rotation_history']==read(CASE/'instruction-watch-before.json')['cache_rotation_history']
assert len(w['watched_source_refs'])==361
assert w['genx_stu_peer_review']['registration']['entry']['key']=='gen9genxstu4cazure4'
assert w['genx_stu_peer_review']['adopted_by_this_stream'] is False
w['stu_scope_review']['latest_round4_net_selection_review']=read(CASE/'round4-net-selection-review.json')
w['layout_budget_research_review']=read(CASE/'layout-budget-scope-review.json')
assert w['layout_budget_research_review']['adopted_by_this_stream'] is False
assert w['stu_scope_review']['latest_round4_net_selection_review']['applied_to_this_stream'] is False
assert 'prior_round3_review' in w['genx_stu_peer_review']
w['stu_scope_review']['latest_collection_vs_testing_review']=read(CASE/'stu-collection-scope-review.json')
assert w['stu_scope_review']['latest_collection_vs_testing_review']['owned_adoption'] is False
assert w['last_diagnosed_cache_rotation']['completed']==5432
w['stu_scope_review']['latest_efficiency_scope_review']=read(CASE/'stu-efficiency-scope-review.json')
w['stu_scope_review']['latest_harvesting_scope_review']=read(CASE/'harvesting-scope-review.json')
w['stu_scope_review']['latest_rollout_experiment_scope_review']=read(CASE/'rollout-experiment-scope-review.json')
assert w['stu_scope_review']['latest_efficiency_scope_review']['applied'] is False
assert w['stu_scope_review']['latest_harvesting_scope_review']['applied'] is False
assert w['stu_scope_review']['latest_rollout_experiment_scope_review']['applied'] is False
assert len(w['comment_scan']['new_issue_comments'])==33
w['tracked_file_branches']=read(CASE/'tracked-file-branches.json')['branches']
w['stu_scope_review']['latest_bid_style_scope_review']=read(CASE/'bid-style-scope-review.json')
assert w['stu_scope_review']['latest_bid_style_scope_review']['applied'] is False
w['tracked_file_branches']=read(CASE/'tracked-file-branches.json')['branches']
assert len(w['tracked_file_branches'])==54
rotation_summary={**rotation['journal'],'new_collector_pid':rotation['new_collector_pid'],'previous_collector_pid':rotation['old_collector_pid'],'diagnosed':True,'evidence':str(CASE/'cache-rotation-diagnosis.json'),'requires_attention':False}
w['last_diagnosed_cache_rotation']=rotation_summary
if not any(isinstance(x,dict) and x.get('epoch')==rotation_summary['epoch'] for x in w['cache_rotation_history']):
    w['cache_rotation_history'].append(rotation_summary)
w['observed_operational_events'].append({'type':'authorized_disposable_dds_cache_rotation','poll_start':start,'completed':rotation['drain_completed'],'old_pid':rotation['old_collector_pid'],'new_pid':rotation['new_collector_pid'],'diagnosed':True,'manual_restart':False,'requires_attention':False,'evidence':str(CASE/'cache-rotation-diagnosis.json')})
w['operational_guard_review']['latest_cache_rotation_review']={'poll_start':start,'completed':rotation['drain_completed'],'guard_sha256':rotation['guard_sha256'],'pre_rotation_records_verified':rotation['pre_rotation_records_verified'],'drain_snapshot_records_verified':rotation['drain_snapshot_records_verified'],'frozen_scientific_files_verified':rotation['frozen_scientific_files_verified'],'all_current_receipt_episode_pairs_verified':rotation['all_current_receipt_episode_pairs_verified'],'post_rotation_replay_and_capture_verified':True,'evidence':str(CASE/'cache-rotation-diagnosis.json'),'failures_cleared':False,'manual_restart':False}
w['stu_scope_review']['latest_validation_v1_scope_review']=read(CASE/'validation-v1-scope-review.json')
w['stu_scope_review']['latest_research_traffic_scope_review']=read(CASE/'research-traffic-scope-review.json')
w['latest_comments_scope_review']={'poll_start':start,'comment_ids':[r['id'] for r in scan['comments']['issue_comments']],'issue_numbers':sorted({r['issue_number'] for r in scan['comments']['issue_comments']}),'scope':'Current scoped Stu persona, V1, H05, P03/P04 and traffic updates; corrected experimental source has explicit larger R4c/BEN research authority but no production adoption or primary transition.','applied_to_this_stream':False,'evidence':str(CASE/'stu-efficiency-scope-review.json')}
w['collection_action']='Verified unchanged exact-token DDS-only supervisor rotation at5820 (314336 exited,335661 owns writer), preserving777 science files and all audited records. Final-count publication already carries new heartbeat; journal/guard plus contiguous receipts establish drain. Resumed replay/score/hash/systems/capture passed. No manual restart, failure clearance, source/model/settings/corpus/worker/guard change, training, promotion, registry/shared UI or peer mutation.'
w['latest_scope_review']['current_effect']='Continue frozen Gen8 source792c4cb, manifestcd98, five-pair main mix, three normal/zero BEN, target18283, immutable34092-family exclusions, disabled legacy gates and strict source guard. DDS-only rotation5820 verified; old owner314336 exited,335661 owns writer; final-count recovery has new heartbeat and was not rewritten. Max personality capability is posted to Loop/g9 source owners with new SidVariable/Gen8Variable IDs, no existing official actor/plan change or job launch. Corrected d82/4951 new-identity experimental R4c/BEN screens have current explicit throughput authority; old7c evidence remains invalid, no production promotion. H05/V1/P03/P04/traffic updates are scoped to other owners; V1 protects future Stu training, not a rewrite of this arena exclusions. No local source/model/budget/fork/worker/guard change, training, BEN/self-play opening, peer command/message or shared UI/registry mutation. Preserve all records/history and require complete ALL-released-model training exclusions for future owned cohorts.'
assert len(w['cache_rotation_history'])==15
assert w['cache_rotation_history'][:-1]==read(CASE/'instruction-watch-before.json')['cache_rotation_history']
assert w['last_diagnosed_cache_rotation']['completed']==5820
assert not w['stu_scope_review']['latest_validation_v1_scope_review']['applied']
p=C/'instruction-watch.json.tmp'
p.write_text(json.dumps(w,indent=2,ensure_ascii=False)+'\n')
os.replace(p,C/'instruction-watch.json')
assert read(C/'stream.json')['seed']==6586995816951042092
(CASE/'live-capture-sample.json').write_text(json.dumps(h['live_capture_sample'],indent=2)+'\n')
print(json.dumps({'poll_start':start,'comments_since':scan['comments_since'],'next_comment_scan_since':w['next_comment_scan_since'],'result':w['result'],'completed':h['state']['completed'],'source_unchanged':True,'watch_bytes':(C/'instruction-watch.json').stat().st_size,'next_check':w['next_check']}))
