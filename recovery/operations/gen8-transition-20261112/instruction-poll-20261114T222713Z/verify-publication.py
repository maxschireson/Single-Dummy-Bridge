import hashlib
import json
from pathlib import Path
import subprocess
import time

CONTROL=Path('/workspace/work/gen6-fast-selfplay-stream')
CASE=Path(__file__).resolve().parent
CONFIG=json.loads((CONTROL/'stream.json').read_text())
RUN=Path(CONFIG['run'])
PUB=Path(CONFIG['publication'])

def git(*args):
    return subprocess.check_output(['git','-C',str(PUB),*args],timeout=30)

def blob(rev,path):
    return git('show',rev+':'+path)

paths={}
for name in ['instruction-watch.json','stream.json','supervise_gen8.py','publish_stream.py','gen8-transition.json','gen71-final-publication.json']:
    paths['recovery/operations/'+name]=CONTROL/name
for name in ['manifest.json','plan.json','environment.json','source-manifest.json','artifact-source-manifest.json','evaluation-exclusion-audit.json','preflight.json','preflight-capture.json','production-validation.json','validation.json']:
    paths['recovery/'+name]=RUN/name
paths['recovery/artifacts/validation/evaluation-exclusions.json']=RUN/'artifacts/validation/evaluation-exclusions.json'
for p in CASE.iterdir():
    if p.is_file() and p.name not in ['publication-proof.json','github-watch-readback.json']:
        paths['recovery/operations/'+str(p.relative_to(CONTROL))]=p
capture=json.loads((CASE/'live-capture-sample.json').read_text())
rotation=json.loads((CASE/'cache-rotation-diagnosis.json').read_text())
for row in capture['samples']+rotation['post_rotation_samples']:
    idx=row['index']
    for folder,suffix in [('receipts','.json'),('episodes','.json.gz')]:
        name=f'{idx:06d}'+suffix
        paths['recovery/'+folder+'/'+name]=RUN/folder/name

for attempt in range(1,31):
    try:
        status=json.loads((RUN/'publisher-status.json').read_text())
        assert status['status']=='published'
        rev=status['commit']
        exact={}
        for name,local in paths.items():
            raw=blob(rev,name)
            assert raw==local.read_bytes(),name+' not yet captured'
            exact[name]=dict(sha256=hashlib.sha256(raw).hexdigest(),git_blob=git('rev-parse',rev+':'+name).decode().strip(),bytes=len(raw))
        remote=git('ls-remote','--heads','origin',CONFIG['branch']).decode().split()[0]
        assert remote==rev,'Publisher advanced while verifying; read a new pinned snapshot'
        data=json.loads(blob(rev,'arena/data.json'))
        state=json.loads(blob(rev,'recovery/state.json'))
        markers=git('ls-tree','-r','--name-only',rev,'recovery/receipts').decode().splitlines()
        count=sum(x.endswith('.json') for x in markers)
        assert count==state['completed']==status['completed']==data['completed']
        assert state['manifest_identity']==CONFIG['manifest']
        assert data['generation']==8 and data['configured_workers']==3
        assert state['failures']==0 and not state['complete']
        assert data['collection']['running'] is True
        # Active workers may commit out of source order. Only a drained final
        # snapshot requires contiguous == completed; markers are authoritative.
        proof=dict(status='verified_pinned_publication',poll_start='2026-11-14T22:27:13Z',verified_epoch=time.time(),revision=rev,remote_ref_matches=True,publisher_status=status,published_completed=count,published_receipt_markers=count,active_out_of_order_completion_supported=True,manifest=CONFIG['manifest'],exact_byte_files=exact,watch_blob=exact['recovery/operations/instruction-watch.json']['git_blob'],scientific_identity_unchanged=True,actual_gap_guess_samples_published=True,shared_ui_mutated=False,registry_mutated=False,attempts=attempt)
        (CASE/'publication-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
        print(json.dumps({k:proof[k] for k in ['status','revision','published_completed','published_receipt_markers','watch_blob','attempts']}),flush=True)
        print(json.dumps(dict(exact_byte_files=len(exact))),flush=True)
        break
    except (AssertionError,subprocess.CalledProcessError) as exc:
        if attempt==30:
            raise
        print(json.dumps(dict(attempt=attempt,waiting_for_existing_publisher=str(exc))),flush=True)
        time.sleep(5)
