import sys, tempfile, unittest
sys.path.insert(0, '/workspace/scratch/c7932514d17d/gen6-ben-server-recycled')
from ops.ben_board_executor import BenBoardExecutor
from concurrent.futures.process import BrokenProcessPool
from tests.test_ben_board_executor import initialize, job
class Server:
 def __init__(self, code):self.code=code;self.started=False;self.stopped=False
 def start(self):self.started=True;return self
 def stop(self):self.stopped=True;return self.code
class Test(unittest.TestCase):
 def test_result_requires_server_health(self):
  for code in (None,0,7,-9):
   with self.subTest(code=code), tempfile.TemporaryDirectory() as d:
    s=Server(code)
    with BenBoardExecutor(d,initialize,(),server_factory=lambda:s) as pool:
     f=pool.submit(job,'ok')
     if code is None:self.assertEqual(len(f.result(timeout=30)[1]),2000000)
     else:
      with self.assertRaises(BrokenProcessPool):f.result(timeout=30)
    self.assertTrue(s.started and s.stopped)
if __name__=='__main__':unittest.main()
