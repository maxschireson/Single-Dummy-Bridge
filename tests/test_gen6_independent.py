from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import load
from bridge_harness.loop_registry import sha
from bridge_harness.mixed_arena import verify_generation
from ops.prepare_gen6_independent import prepare
from tests.test_gen6_launch import source_run


class IndependentTests(unittest.TestCase):
    def test_fresh_cohort_excludes_published_families_and_preserves_actors(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);source=tmp/'source';old=source_run(source)
            shutil.copyfile(source/'corpus.jsonl',source/'published-corpus.jsonl')
            plan=json.loads((Path(__file__).resolve().parents[1]/'configs/round6.json').read_text())
            plan.update(launch_enabled=True,pending=[],authorized_engine_commit='717cd87',
                        lead_state_bidder_sha256=old['bots']['5RZ32']['artifact_sha256']['bidding'])
            files={}
            for role,entry in plan['artifacts'].items():
                f=tmp/(role+'.bin');f.write_bytes(role.encode());entry['sha256']=sha(f);files[entry['file']]=f
            plan_path=tmp/'plan.json';plan_path.write_text(json.dumps(plan))
            with patch('ops.prepare_gen6_independent.release_file',side_effect=lambda e:files[e['file']]):
                m=prepare(tmp/'run',source,source/'manifest.json',plan_path,count=20,seed=5)
                verify_generation(tmp/'run',m)
                self.assertTrue(m['independent_cohort']);self.assertEqual(m['target'],20)
                families={deal_key(b.hands,True) for b in load(tmp/'run/corpus.jsonl')}
                original={deal_key(b.hands,True) for b in load(source/'published-corpus.jsonl')}
                self.assertEqual(len(families),20);self.assertFalse(families&original)
                for key,spec in old['bots'].items():self.assertEqual(m['bots'][key],spec)
                self.assertEqual(m['artifact_source_manifest_identity'],old['identity'])
                with self.assertRaises(ValueError):prepare(tmp/'run',source,source/'manifest.json',plan_path,count=20,seed=5)


if __name__=='__main__':unittest.main()
