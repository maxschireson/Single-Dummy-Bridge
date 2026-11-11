from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import load
from bridge_harness.loop_registry import sha,source_hash
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest
from ops.retarget_gen6_ben import prepare
from tests.test_gen6_launch import source_run


class RetargetTests(unittest.TestCase):
    def test_only_unplayed_families_continue_and_actors_are_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);source=tmp/'source';m=source_run(source)
            for key,samples in [('6-32',32),('6-256',256)]:
                spec=deepcopy(m['bots']['5RZ32']);spec.pop('identity');spec.update(id=key,samples=samples,engine='gen6');spec['identity']=digest(spec);m['bots'][key]=spec
            m.update(variant='6',source_sha256=source_hash(),model_note='Gen6',interpretation='Test',
                     pair_weights={'6-32~5RZ32':8,'6-32~6-256':3,'6-32~ben':3,'6-32~3':2,'6-32~2':2,'6-32~1':2})
            m.pop('identity');m['identity']=digest(m);atomic_json(source/'manifest.json',m)
            boards=list(load(source/'corpus.jsonl'));episode=source/'episodes/000000.json.gz';atomic_json(episode,dict(saved='unchanged'),compressed=True)
            before=episode.read_bytes();atomic_json(source/'receipts/000000.json',dict(index=0,manifest_identity=m['identity'],family=deal_key(boards[0].hands,True),episode_sha256=sha(episode)))
            n=prepare(tmp/'new',source);verify_generation(tmp/'new',n)
            self.assertEqual(n['target'],5);self.assertEqual(n['source_completed'],1)
            self.assertEqual(n['bots'],m['bots']);self.assertEqual(n['pair_weights']['6-256~ben'],3)
            self.assertNotIn('6-32~ben',n['pair_weights']);self.assertEqual(n['audit_references']['6-256'],'3')
            self.assertEqual(json.loads((tmp/'new/source-indices.json').read_text()),[1,2,3,4,5])
            self.assertEqual(episode.read_bytes(),before)
            self.assertNotIn(boards[0].id,{b.id for b in load(tmp/'new/corpus.jsonl')})
            with self.assertRaises(ValueError):prepare(tmp/'new',source)


if __name__=='__main__':unittest.main()
