#!/usr/bin/env python3
"""Measure BEN's production HTTP path on the same fixed bidding requests."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen
from urllib.parse import urlencode


def main():
    p=argparse.ArgumentParser()
    for k in ('ben-dir','ben-python','config','requests','out'):p.add_argument('--'+k,required=True)
    p.add_argument('--port',type=int,default=8099)
    p.add_argument('--limit',type=int,default=3)
    args=p.parse_args()
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    requests=json.loads(Path(args.requests).read_text())[:args.limit]
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1')
    with (out/'server.log').open('x') as log:
        server=subprocess.Popen([args.ben_python,'-u','src/gameapi.py','--config',str(Path(args.config).resolve()),'--host','127.0.0.1','--port',str(args.port),'--nolimit','true','--record','false'],cwd=args.ben_dir,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            base=f'http://127.0.0.1:{args.port}'
            for _ in range(120):
                if server.poll() is not None:raise RuntimeError('BEN exited')
                try:
                    with urlopen(base,timeout=1) as response:response.read()
                    break
                except OSError:time.sleep(.5)
            for i,request in enumerate(requests):
                params={k:v for k,v in request.items() if k!='id'}
                params.update(matchtype='IMP',details='true')
                t=time.perf_counter()
                with urlopen(base+'/bid?'+urlencode(params),timeout=600) as response:result=json.load(response)
                record=dict(request=request,response=result,seconds=time.perf_counter()-t)
                (out/f'{i:03d}-{request["id"]}.json').write_text(json.dumps(record,indent=2)+'\n')
                print(request['id'],record['seconds'],result.get('bid'),flush=True)
        finally:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait()

if __name__=='__main__':main()
