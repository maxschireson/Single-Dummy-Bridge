"""Independent development-only warm-start/schedule ablation; exact resume."""
import argparse, datetime, fcntl, json, os, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.selfplay import atomic_json

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--run', type=Path, required=True)
    root = ap.parse_args().run.resolve()
    lock = (root/'supervisor.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    plan = json.loads((root/'plan.json').read_text())
    deadline = datetime.datetime.fromisoformat(plan['deadline_utc']).timestamp()
    env = {**os.environ, 'OPENBLAS_NUM_THREADS':'1', 'OMP_NUM_THREADS':'1', 'TF_CPP_MIN_LOG_LEVEL':'3'}
    def status(stage, **kw):
        atomic_json(root/'status.json', dict(stage=stage, updated=time.time(), **kw))
    while time.time() < deadline:
        pilot = json.loads(Path(plan['wait_for_status']).read_text())
        if pilot.get('stage') == 'complete': break
        status('waiting_for_effort_replication'); time.sleep(10)
    for job in plan['jobs']:
        out = Path(job['config']).parent
        while time.time() < deadline:
            complete = (out/'result.json').exists()
            if complete and (out/'joint.json').exists(): break
            with (out/'writer.lock').open('a+') as h:
                try: fcntl.flock(h, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    status('existing_writer', job=job['name']); time.sleep(10); continue
            cmd = ['scripts/score_belief_joint.py', '--model', str(out/'best.npz'), '--data', plan['data'], '--out', str(out/'joint.json')] if complete else ['scripts/train_belief_lab.py', '--config', job['config']]
            with (root/'pipeline.log').open('a', buffering=1) as log:
                proc = subprocess.Popen([sys.executable, '-u', *cmd], stdout=log, stderr=log, env=env)
                while True:
                    status('score' if complete else 'fit', job=job['name'])
                    try: rc = proc.wait(timeout=10); break
                    except subprocess.TimeoutExpired:
                        if time.time() > deadline + 120:
                            proc.terminate()
                            try: proc.wait(timeout=20)
                            except subprocess.TimeoutExpired: proc.kill(); proc.wait()
                            status('deadline'); return
                if rc:
                    status('error', job=job['name'], exit_code=rc); return
        if time.time() >= deadline: status('deadline'); return
    status('complete', test_evaluated=False, promoted=False)

if __name__ == '__main__': main()
