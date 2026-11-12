from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bridge_harness.gen5r import load_plan,make_bots,PAIR_WEIGHTS
from bridge_harness.gen5_arena import run_board
from bridge_harness.corpus import generate,save
from bridge_harness.players import Decision
from bridge_harness.loop_registry import sha
from bridge_harness.training import digest
from ops.gen5_runtime import validate
from ops.prepare_gen5r import prepare

def source_manifest():
    bots={}
    for k in ('5','5-32','4b','3','2','1','ben'):
        spec=dict(id=k,samples=192 if k=='5' else 16 if k=='ben' else 32,
                  artifact_sha256={},near_tie=.125,exploration=0)
        spec['identity']=digest(spec);bots[k]=spec
    return dict(bots=bots)

class Toy:
    def __init__(self,spec,root,reference=None):self.spec=spec
    def choose(self,o,rng):return Decision(sorted(o.legal)[0],{})
    def close(self):pass

class Gen5RTests(unittest.TestCase):
    def test_finalizing_old_run_keeps_its_runtime_unchanged(self):
        from ops.publish_gen5 import snapshot_runtime
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'old';source.mkdir();backup=Path(td)/'backup'
            (source/'manifest.json').write_text(json.dumps({'source_sha256':'older-frozen-source'}))
            with self.assertRaisesRegex(ValueError,'another cohort'):snapshot_runtime(source,backup)
            runtime=backup/'runtime/bridge_harness';runtime.mkdir(parents=True)
            (runtime/'players.py').write_bytes(b'frozen original player')
            before={p.relative_to(backup):p.read_bytes() for p in backup.rglob('*') if p.is_file()}
            self.assertFalse(snapshot_runtime(source,backup))
            self.assertEqual(before,{p.relative_to(backup):p.read_bytes() for p in backup.rglob('*') if p.is_file()})

    def test_allocation_and_scaled_budgets(self):
        plan=load_plan();bots=make_bots(source_manifest(),plan)
        self.assertEqual(sum(PAIR_WEIGHTS.values()),40)
        self.assertEqual(PAIR_WEIGHTS['5R32~5R192'],PAIR_WEIGHTS['5R32~5-32'])
        for key,budget in [('5R32',32),('5R192',192)]:
            self.assertEqual(bots[key]['samples'],budget)
            self.assertEqual(bots[key]['layout_reduction']['large_pool'],4*budget)
            self.assertEqual(bots[key]['layout_reduction']['large_budget'],budget)
            self.assertFalse(bots[key]['layout_reduction']['medium_enabled'])
        self.assertEqual(bots['5-32'],source_manifest()['bots']['5-32'])
        self.assertNotIn('layout_reduction',bots['5-32'])
        self.assertNotEqual(bots['5R32']['identity'],bots['5-32']['identity'])

    def test_every_pair_uses_requested_actors_and_common_bidder(self):
        plan=load_plan();bots=make_bots(source_manifest(),plan);board=next(generate(1,384))
        for pair in PAIR_WEIGHTS:
            used=[]
            def factory(spec,root,reference=None):
                used.append(spec['id']);return Toy(spec,root,reference)
            m=dict(identity='fixture',roster=plan['roster'],target=1,seed=11,bots=bots,
                pair_schedule=[pair],audit_references={'5R32':'3','5R192':'3'},common_bidder='5R32',
                audit=dict(probability=0,multiplier=1,max_depth=0,max_forks=0),
                ben_audit=dict(probability=0,multiplier=1,max_depth=0,max_forks=0))
            with patch('bridge_harness.gen5_arena.auction',lambda b,actors:(b,[])):
                r=run_board('.',m,board.to_dict(),0,{k:object() for k in bots},player_factory=factory)
            validate(r,m,0)
            self.assertEqual(used,pair.split('~'))
            self.assertEqual(r['bidding']['common/0']['bidders'],['5R32']*4)
            self.assertEqual(r['regimes']['common']['tables'],r['regimes']['native']['tables'])

    def test_takeover_preserves_old_and_excludes_completed_deals(self):
        from bridge_harness.bidding_env import deal_key
        from bridge_harness.selfplay import atomic_json
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'old';source.mkdir();dest=Path(td)/'new'
            for folder in ('assets','artifacts','episodes','receipts','failures'): (source/folder).mkdir()
            boards=list(generate(80,331));save(boards,source/'corpus.jsonl')
            m=dict(source_manifest(),corpus='corpus.jsonl',corpus_sha256=sha(source/'corpus.jsonl'),target=80,
                   audit=dict(probability=0,multiplier=1,max_depth=0,max_forks=0),
                   ben_audit=dict(probability=0,multiplier=1,max_depth=0,max_forks=0),bidding_conditions=['common','native'])
            m['identity']=digest(m);atomic_json(source/'manifest.json',m)
            with self.assertRaisesRegex(ValueError,'Drain'):prepare(dest,source)
            (source/'STOP').touch();(source/'WATCHDOG_STOP').touch()
            episode=source/'episodes/000007.json.gz';episode.write_bytes(b'preserved completed record')
            atomic_json(source/'receipts/000007.json',dict(index=7,family=deal_key(boards[7].hands,True),manifest_identity=m['identity'],episode_sha256=sha(episode)))
            before={str(p.relative_to(source)):p.read_bytes() for p in source.rglob('*') if p.is_file()}
            n=prepare(dest,source)
            self.assertEqual(n['target'],79);self.assertEqual(n['source_completed'],1)
            self.assertNotIn(7,json.loads((dest/'source-indices.json').read_text()))
            self.assertEqual(Counter(n['pair_schedule']),PAIR_WEIGHTS)
            for path,raw in before.items():self.assertEqual((source/path).read_bytes(),raw)
            with self.assertRaisesRegex(ValueError,'overwrite'):prepare(dest,source)

if __name__=='__main__':unittest.main()
