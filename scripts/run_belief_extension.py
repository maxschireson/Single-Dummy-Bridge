#!/usr/bin/env python3
"""Queue 500 fresh belief-control pairs after total-improvement play, before BEN."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.evaluate_frozen_comparisons import atomic, read, read_episode, sha, settings, validate_run, exclusive
from bridge_harness.core import Board
from bridge_harness.training import digest
from bridge_harness.runner import replay
from bridge_harness.report import summarize

def combined(base,extension,new_count):
    records=[];ids=set()
    for root,count in [(base,500),(extension,new_count)]:
        _,boards=validate_run(root)
        audit=read(root/f'strict/audit-{count}.json')
        assert audit['independent_deals']==count and audit['complete_games']==2*count
        for b in boards[:count]:
            did=digest(b.hands);assert did not in ids;ids.add(did)
            r=read_episode(root/'strict/episodes'/f'{did}.json.gz')
            assert r['status']=='ok' and r['board']==b.to_dict() and r['config']==settings(root,'strict')
            assert all(t['complete'] and t['plies']==52 for t in replay(r))
            records.append(r)
    result=summarize(sorted(records,key=lambda r:digest(Board.from_dict(r['board']).hands)))
    assert result['independent_clusters']==result['completed_pairs']==500+new_count
    result.update(analysis='follow-up pooled estimate after data-dependent extension; nominal 95% intervals, not a predeclared 1000-deal test',
                  original_pairs=500,new_pairs=new_count,original_summary_sha256=sha(base/'strict/summary-500.json'),
                  new_summary_sha256=sha(extension/f'strict/summary-{new_count}.json'))
    atomic(extension/f'combined/summary-{500+new_count}.json',result)
    atomic(extension/f'combined/audit-{500+new_count}.json',dict(independent_deals=len(ids),complete_games=2*len(ids),
        original_deals_disjoint=True,legal_replay=True,prior_full_audits_verified=True,source_sha256=sha(__file__)))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True)
    p.add_argument('--extension',type=Path,required=True);a=p.parse_args();base=a.base.resolve();ext=a.extension.resolve()
    with exclusive(ext/'sequence.lock'):
        validate_run(base);validate_run(ext)
        while not (base/'blind/audit-500.json').exists():
            atomic(ext/'sequence-status.json',dict(status='waiting_for_total_comparison',updated_unix=time.time()))
            time.sleep(30)
        completed=read(base/'blind/audit-500.json');assert completed['independent_deals']==500
        resource=Path(read(base/'ben-runtime.json')['resource_lock']).open('a')
        try:
            while True:
                try:fcntl.flock(resource,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:
                    atomic(ext/'sequence-status.json',dict(status='waiting_for_existing_BEN_resource',updated_unix=time.time()))
                    time.sleep(30)
            atomic(ext/'sequence-status.json',dict(status='running_extension',updated_unix=time.time()))
            with (ext/'sequence-play.log').open('a') as log:
                proc=subprocess.Popen([sys.executable,'-u',str(ROOT/'scripts/evaluate_frozen_comparisons.py'),
                    '--run',str(ext),'--mode','play','--opponent','strict','--workers','4'],cwd=ROOT,
                    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),stdout=log,stderr=subprocess.STDOUT,
                    pass_fds=(resource.fileno(),))
                while True:
                    if (ext/'strict/audit-200.json').exists() and not (ext/'combined/summary-700.json').exists():combined(base,ext,200)
                    try:rc=proc.wait(timeout=30);break
                    except subprocess.TimeoutExpired:pass
            if rc:
                atomic(ext/'sequence-status.json',dict(status='extension_failed',returncode=rc,updated_unix=time.time()))
                raise RuntimeError(f'Extension worker exited {rc}; preserve records and inspect log')
            combined(base,ext,200);combined(base,ext,500)
            atomic(ext/'sequence-status.json',dict(status='audited',new_pairs=500,combined_pairs=1000,updated_unix=time.time()))
        finally:resource.close()

if __name__=='__main__':main()
