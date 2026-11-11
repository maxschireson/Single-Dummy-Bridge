import sys,tempfile,pathlib,socket,json,time
sys.path.insert(0,"/workspace/scratch/c7932514d17d/gen6-ben-server-recycled")
from ops.ben_server_lifecycle import BenServer
with tempfile.TemporaryDirectory() as d:
 r=pathlib.Path(d);(r/'diagnostics').mkdir()
 def port():
  with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
 p=port();s=BenServer(r,command=[sys.executable,'-m','http.server',str(p),'--bind','127.0.0.1'],cwd=d,url=f'http://127.0.0.1:{p}/',timeout=5).start();assert s.stop() is None
 p=port();s=BenServer(r,command=[sys.executable,'-m','http.server',str(p),'--bind','127.0.0.1'],cwd=d,url=f'http://127.0.0.1:{p}/',timeout=5).start();s.process.kill();s.process.wait();assert s.stop()==-9
 p=port();s=BenServer(r,command=[sys.executable,'-c','raise SystemExit(7)'],cwd=d,url=f'http://127.0.0.1:{p}/',timeout=5)
 try:s.start();raise AssertionError('startup accepted')
 except RuntimeError as e:assert '7' in str(e)
 rows=[json.loads(l) for f in (r/'diagnostics').glob('ben-server-*.jsonl') for l in f.read_text().splitlines()];assert any(x.get('unexpected_exitcode')==-9 for x in rows);assert any(x.get('unexpected_exitcode')==7 for x in rows)
 print(json.dumps({'passed':3,'cases':['intentional_stop','SIGKILL_telemetry','startup_exit7']}))
