import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import run_belief_extension as extension

class ExtensionTests(unittest.TestCase):
    def test_queued_extension_does_not_start_before_total_audit(self):
        with tempfile.TemporaryDirectory() as name:
            base=Path(name)/'base';out=Path(name)/'extension';base.mkdir();out.mkdir()
            with patch('sys.argv',['queue','--base',str(base),'--extension',str(out)]), \
                 patch.object(extension,'validate_run'), \
                 patch.object(extension.time,'sleep',side_effect=InterruptedError('test stop')), \
                 patch.object(extension.subprocess,'Popen') as launch:
                with self.assertRaises(InterruptedError):extension.main()
                launch.assert_not_called()
            self.assertEqual(json.loads((out/'sequence-status.json').read_text())['status'],'waiting_for_total_comparison')

if __name__=='__main__':unittest.main()
