#!/usr/bin/env python3
"""Start local BEN, freeze its auctions, and play a paired integration match.

Use a separate BEN checkout/venv; heavyweight model files are not in this project.
"""
import argparse
import configparser
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ben-dir",required=True)
    p.add_argument("--ben-python",required=True)
    p.add_argument("--port",type=int,default=8085)
    p.add_argument("--count",type=int,default=4)
    p.add_argument("--deal-seed",type=int,default=419)
    p.add_argument("--decision-seed",type=int,default=731)
    p.add_argument("--samples",type=int,default=32)
    p.add_argument("--objective",choices=("score","tricks","make"),default="tricks")
    p.add_argument("--near-tie",type=float,default=0.125)
    p.add_argument("--board-timeout",type=float,default=600)
    p.add_argument("--http-timeout",type=float,default=600)
    p.add_argument("--ben-dds-threads",type=int,default=2)
    p.add_argument("--resume",action="store_true")
    p.add_argument("--out",default="results/ben_integration")
    args=p.parse_args()
    if args.count < 1 or args.samples < 1 or args.near_tie < 0:
        p.error("Count/samples must be positive and near-tie nonnegative")
    root=Path(__file__).resolve().parents[1]
    ben=Path(args.ben_dir).resolve();python=Path(args.ben_python).absolute()
    out=(root/args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()) and not args.resume:
        p.error("Output directory must be empty; completed experiments are never overwritten")
    config=configparser.ConfigParser(interpolation=None)
    config.read(ben/'src/config/default_api.conf')
    if not config.has_section('dds'):
        config.add_section('dds')
    config['dds']['dds_max_threads']=str(args.ben_dds_threads)
    # Portable BEN neural/DDS configuration; do not require proprietary Windows engines.
    for sec in config:
        for key in config[sec]:
            if key in {'use_bba','consult_bba','use_bba_rollout','use_bba_to_count_aces',
                       'use_suitc','pimc_use_declaring','pimc_use_defending',
                       'ace_use_declaring','ace_use_defending'}:
                config[sec][key]='False'
    cfg=out/'ben.conf'
    buffer=io.StringIO();config.write(buffer)
    if args.resume and cfg.exists() and cfg.read_text()!=buffer.getvalue():
        p.error("Resume BEN configuration differs from saved configuration")
    if not cfg.exists():cfg.write_text(buffer.getvalue())
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ben,text=True).strip()
    label=f"BEN {revision}; portable neural/DDS; config SHA256 {hashlib.sha256(cfg.read_bytes()).hexdigest()}"
    version_file=out/'ben_version.txt'
    if args.resume and version_file.exists() and version_file.read_text()!=label+'\n':
        p.error("Resume BEN version differs")
    if not version_file.exists():version_file.write_text(label+'\n')
    # Reserve the deals before obtaining any outcomes. Keep this manifest outside
    # training; future collectors must exclude these full original-hand hashes.
    sys.path.insert(0,str(root))
    from bridge_harness.corpus import generate, save
    from bridge_harness.training import digest
    from dataclasses import replace
    boards=[replace(b,id=f"{args.deal_seed}-{b.id}")
            for b in generate(args.count,args.deal_seed)]
    source=out/'source.jsonl';frozen=out/'frozen.jsonl';results=out/'match.jsonl'
    if source.exists():
        from bridge_harness.corpus import load
        if [b.to_dict() for b in load(source)]!=[b.to_dict() for b in boards]:
            p.error("Resume source deals differ")
    else:save(boards,source)
    manifest=dict(purpose="held-out BEN card-play calibration; exclude from training",
        deal_seed=args.deal_seed, decision_seed=args.decision_seed,
        independent_deals=len(boards), deal_ids=[digest(b.hands) for b in boards],
        samples=args.samples, objective=args.objective, near_tie=args.near_tie,
        batch=True, ben=label, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        harness_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    manifest_path=out/'manifest.json'
    if manifest_path.exists():
        previous=json.loads(manifest_path.read_text())
        for key in ('deal_seed','decision_seed','independent_deals','deal_ids','samples',
                    'objective','near_tie','batch','ben','source_sha256'):
            if previous.get(key)!=manifest[key]:p.error(f"Resume manifest differs: {key}")
    else:manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    with (out/'invocations.jsonl').open('a') as f:
        f.write(json.dumps(dict(started_unix=time.time(),arguments=vars(args),
            harness_commit=manifest['harness_commit'],script_sha256=manifest['script_sha256']))+'\n')
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1')
    with (out/'ben_server.log').open('a') as log:
        server=subprocess.Popen([str(python),'-u','src/gameapi.py','--config',str(cfg),
            '--host','127.0.0.1','--port',str(args.port),'--nolimit','true','--record','false'],cwd=ben,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            url=f'http://127.0.0.1:{args.port}'
            ready=False
            for _ in range(120):
                if server.poll() is not None:raise RuntimeError(f'BEN exited; see {log.name}')
                try:
                    with urlopen(url,timeout=1) as response:response.read()
                    ready=True;break
                except OSError:time.sleep(.5)
            if not ready:raise TimeoutError('BEN startup deadline')
            def run(*args):
                subprocess.run([sys.executable,'-m','bridge_harness',*map(str,args)],cwd=root,check=True)
            resume=['--resume'] if args.resume else []
            run('freeze-auctions',source,frozen,'--ben-url',url,'--timeout',args.http_timeout,*resume)
            run('match',frozen,'--mode','partnership','--candidate','pimc','--baseline','ben',
                '--samples',args.samples,'--objective',args.objective,'--near-tie',args.near_tie,
                '--seed',args.decision_seed,'--ben-url',url,'--ben-label',label,
                '--timeout',args.http_timeout,'--board-timeout',args.board_timeout,'--out',results,*resume)
            run('replay',results)
        finally:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait()


if __name__=='__main__':main()
