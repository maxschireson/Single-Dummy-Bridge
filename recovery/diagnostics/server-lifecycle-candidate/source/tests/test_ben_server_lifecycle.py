import json,sys,socket,tempfile,unittest,time
from pathlib import Path
from concurrent.futures.process import BrokenProcessPool
from ops.ben_server_lifecycle import BenServer
from ops.ben_board_executor import BenBoardExecutor
from tests.test_ben_board_executor import initialize,job
class TestServer(unittest.TestCase):
 def factory(self,folder,created):
  def make():
   with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
   b=BenServer(folder,command=[sys.executable,'-m','http.server',str(port),'--bind','127.0.0.1'],cwd=folder,url=f'http://127.0.0.1:{port}',timeout=5);created.append(b);return b
  return make
 def test_replaced_and_reaped(self):
  with tempfile.TemporaryDirectory() as d:
   created=[]
   with BenBoardExecutor(d,initialize,(),self.factory(d,created)) as pool:
    pool.submit(job,'ok').result(30);pool.submit(job,'ok').result(30)
   self.assertEqual(len(created),2);self.assertTrue(all(x.process is None for x in created))
   events=[json.loads(l) for p in Path(d).rglob('*.jsonl') for l in p.read_text().splitlines()]
   self.assertEqual(len({x['pid'] for x in events if x['event']=='server-start'}),2)
   self.assertTrue(all(x['intentional_stop'] for x in events if x['event']=='server-exit'))
 def test_server_loss_rejects_successful_worker(self):
  with tempfile.TemporaryDirectory() as d:
   created=[]
   with BenBoardExecutor(d,initialize,(),self.factory(d,created)) as pool:
    f=pool.submit(job,'wait');created[0].process.kill();created[0].process.wait()
    with self.assertRaises(BrokenProcessPool):f.result(30)
   events=[json.loads(l) for p in Path(d).rglob('*.jsonl') for l in p.read_text().splitlines()]
   self.assertEqual([x['unexpected_exitcode'] for x in events if x['event']=='server-exit'],[-9])
 def test_startup_failure(self):
  with tempfile.TemporaryDirectory() as d:
   b=BenServer(d,[sys.executable,'-c','raise SystemExit(7)'],d,timeout=2)
   with self.assertRaises(RuntimeError):b.start()
   self.assertIsNone(b.process)
if __name__=='__main__':unittest.main()
