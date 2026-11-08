#!/usr/bin/env python3
"""Start local BEN, freeze its auctions, and play a paired integration match.

Use a separate BEN checkout/venv; heavyweight model files are not in this project.
"""
import argparse
import configparser
import hashlib
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
    p.add_argument("--out",default="results/ben_integration")
    args=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    ben=Path(args.ben_dir).resolve();python=Path(args.ben_python).absolute()
    out=(root/args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    config=configparser.ConfigParser(interpolation=None)
    config.read(ben/'src/config/default_api.conf')
    # Portable BEN neural/DDS configuration; do not require proprietary Windows engines.
    for sec in config:
        for key in config[sec]:
            if key in {'use_bba','consult_bba','use_bba_rollout','use_bba_to_count_aces',
                       'use_suitc','pimc_use_declaring','pimc_use_defending',
                       'ace_use_declaring','ace_use_defending'}:
                config[sec][key]='False'
    cfg=out/'ben.conf'
    with cfg.open('w') as f:config.write(f)
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ben,text=True).strip()
    label=f"BEN {revision}; portable neural/DDS; config SHA256 {hashlib.sha256(cfg.read_bytes()).hexdigest()}"
    (out/'ben_version.txt').write_text(label+'\n')
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1')
    with (out/'ben_server.log').open('w') as log:
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
            source=out/'source.jsonl';frozen=out/'frozen.jsonl';results=out/'match.jsonl'
            run('generate','--count',args.count,'--seed',419,'--out',source)
            run('freeze-auctions',source,frozen,'--ben-url',url)
            run('match',frozen,'--mode','partnership','--candidate','pimc','--baseline','ben',
                '--samples','8','--ben-url',url,'--ben-label',label,'--board-timeout','600','--out',results)
            run('replay',results)
        finally:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait()


if __name__=='__main__':main()
