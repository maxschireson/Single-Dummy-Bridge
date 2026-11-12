import hashlib,json,shutil,subprocess,time
from pathlib import Path

work=Path('/workspace/work');sp=work/'bridge-gen8-transition-state.json';t=json.loads(sp.read_text());old=t['initial_descriptor'];source=Path(t['new_source']);run=Path(t['new_run']);pub=Path(t['new_publication']);m=json.loads((run/'manifest.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):
    p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(v,indent=2)+'\n');tmp.replace(p)
def git(*args):return subprocess.check_output(['git','-C',str(pub),*args],text=True).strip()
assert t['new_manifest']==m['identity'] and m['target']==16036 and t['old_completed']==2189 and not pub.exists()
pub.mkdir();git('init','-b',t['branch']);git('remote','add','origin','https://github.com/maxschireson/Single-Dummy-Bridge.git')
for k in ('user.name','user.email'):git('config',k,subprocess.check_output(['git','-C',str(source),'config',k],text=True).strip())
git('config','credential.helper','!gh auth git-credential');git('config','http.postBuffer','524288000')
backup=pub/'recovery';backup.mkdir()
for folder in ('bridge_harness','ops','scripts','configs','native','tests','docs'):
    shutil.copytree(source/folder,backup/'runtime'/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for name in ('LICENSE','CREDITS.md','AGENTS.md','README.md'):shutil.copy2(source/name,backup/'runtime'/name)
for folder in ('gen7-policy-v4.1-2026-11-12','gen8-system-scorer-v1-2026-11-12'):
    shutil.copytree(source/'models/cardplay'/folder,backup/'runtime/models/cardplay'/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
shutil.copy2(source/'configs/round8-19bbdce5.json',run/'plan.json')
shutil.copy2(Path(old['run'])/'runtime-requirements.txt',run/'runtime-requirements.txt')
histories=list(old['history'])+[dict(run=old['run'],source=old['source'],publication=old['publication'],branch=old['branch'],manifest=old['manifest'],completed=t['old_completed'],revision=t['old_final_revision'],status='permanently_retired')]
for h in histories:
    dest=backup/'history'/h['manifest'];dest.mkdir(parents=True)
    for name in ('manifest.json','state.json','retirement.json','statistics-policy.json','instruction-watch.json','environment.json'):
        if (Path(h['run'])/name).exists():shutil.copy2(Path(h['run'])/name,dest/name)
    write(dest/'publication.json',dict(branch=h['branch'],revision=h['revision'],completed=h['completed'],raw_records='All episodes, receipts, artifacts and frozen runtime remain in this pinned full predecessor feed; never restart it'))
write(backup/'history-index.json',dict(stream_id=old['stream_id'],initial_target=25000,history=histories,current_manifest=m['identity'],current_target=m['target']))
environment=dict(source_branch='ops/gen8-19bbdce5-20261112',source_commit=m['source_commit'],source_base=t['source_base'],source_sha256=m['source_sha256'],runtime_sha256=m['runtime_sha256'],
    auxiliary_runtime_sha256={str(p.relative_to(source)):sha(p) for p in [source/'ops/watch_gen5.py',source/'ops/publish_gen5.py',source/'ops/export_gen5.py',source/'bridge_harness/libbridge_dds.so']},
    manifest_identity=m['identity'],python=str(work/'bridge-venv/bin/python'),source=str(source),run=str(run),publication=str(pub),publication_branch=t['branch'],history=histories,initial_target=25000,remaining_target=m['target'],normal_workers=3,ben_workers_active=0,
    model_policy_sha256=m['bots']['8s-32']['artifact_sha256']['gen7_policy'],system_scorer_sha256=m['bots']['8s-32']['artifact_sha256']['system_scorer'],
    metadata_note='Explicit generation8 and common/native metadata; inherited internal exporter variant6. Released actors and weights match792c4cb exactly. Anchor restoration adds only requested missing catalog actors; no catalog deals imported. Legacy heartbeat has unused worker/BEN slots.',
    authority=t['authority'],evaluation_exclusions=m['evaluation_exclusions'],restored_anchors=m['restored_actors'],epoch=time.time())
write(run/'environment.json',environment)
recovery=f'''# Owned stream19bbdce5: Gen8 recovery

Manifest `{m['identity']}`, feed `{t['branch']}`.
Frozen source `ops/gen8-19bbdce5-20261112` at `{m['source_commit']}`, based on authorized
Gen8 `792c4cb3f647ec71273f0cc57d95be1d0a0a5954`. Never pull into this running checkout.
The preparation-only extension restores missing requested frozen actors from an archived catalog;
it never overrides retained actors, changes player/model settings or imports another pool's deals.

Authority: Max16:11UTC and the operator16:24UTC on12November2026 explicitly instruct all
collectors, including19bbdce5, to switch. The five matchups and exact released models are
from the open `configs/round8-candidate.json`. Three normal workers; no BEN service.
Common/native auctions,50% tie audits, gap forks and guess capture remain enabled.
Every declared system is carried in the records; `systems:NS|EW` is the auction source.

Both predecessors are permanently STOP/WATCHDOG_STOP/PUBLISH_STOP. Gen6 ended at6775;
Gen7.1 ended at2189 on `{t['old_final_revision']}`. Their full feeds, immutable manifests,
models, runtimes and every completed episode/receipt are pinned in `history-index.json`.
Never restart them. Accounting:6775+2189+16036=25000 original fresh families.
The Gen8 corpus is precisely the unplayed Gen7.1 families; no fresh top-up or other producer pool.
The34092-family union at transfer/v41-training-families-union-20261112:fccbbd8 is excluded
and retained with SHA256 `{m['evaluation_exclusions']['sha256']}`.

For recovery restore `runtime` verbatim as source and recovery metadata/artifacts/episodes/receipts
as the run; create empty failures/episodes/receipts directories when Git omitted an empty folder.
Verify the generation, source, runtime and model hashes before considering restart. Inspect fresh
processes, locks, heartbeat, preserved failures and this stream's descriptor first; dated reports
are not liveness evidence. Use the environment's Python, set BRIDGE_ARENA_PYTHON and BLAS/OpenMP/
TensorFlow thread counts to1 and XDG_CACHE_HOME to a writable workspace cache. Use one publisher
checkout and buffered Git HTTP transport (`http.postBuffer524288000`). No credentials in logs.

Drain with STOP and WATCHDOG_STOP; wait for in-flight work and both locks. Preserve every
episode and receipt, stop the publisher with PUBLISH_STOP, then call its publish function directly
for the last snapshot after its process exits. A diagnosed failure blocks unchanged restart.
Code/models/settings changes need another immutable, validated successor with retained history.
The watchdog rotates only the disposable DDS memoization cache after a graceful drain.
'''
(run/'RECOVERY.md').write_text(recovery)
diagnosis=dict(initial_prepare='Missing5RZ32 and1; source cohort had intentionally pruned these actors.',resolution='Imported exact canonical actors54591b0880b1 and5ba471c0a612 from capture8833c62, all shared actors and model hashes verified; no deals imported.',initial_test_failure='Default DDS cache resolved outside the writable workspace; production run never started.',test_resolution='Full suite rerun with XDG_CACHE_HOME under /workspace.',plan_copy_failure='A JSON round trip changed numeric types and actor hashes; identity guard refused preparation.',plan_resolution='Plan regenerated from authoritative bytes through Python, exact release identities verified before a run was created.',production_failures=0)
write(run/'preparation-diagnosis.json',diagnosis)
write(run/'handoff.json',dict(status='awaiting_real_model_preflight',stream_id=old['stream_id'],registry_key=old['registry_key'],manifest=m['identity'],run=str(run),source=str(source),publication=str(pub),branch=t['branch'],target=m['target'],history=histories,epoch=time.time()))
write(run/'launch.json',json.loads((run/'handoff.json').read_text()))
t.update(status='gen8_preflight_in_progress',epoch=time.time());write(sp,t)
print(json.dumps(dict(publication=str(pub),manifest=m['identity'],history_completed=[h['completed'] for h in histories],target=m['target'])))
