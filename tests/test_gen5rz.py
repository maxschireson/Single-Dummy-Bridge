from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch
from bridge_harness.core import Game,card,symbol
from bridge_harness.corpus import generate,save
from bridge_harness.loop_registry import sha,source_hash
from bridge_harness.mixed_arena import ArenaPlayer
from bridge_harness.training import digest
from ops.prepare_gen5rz import load_plan,make_bots,prepare,PAIR_WEIGHTS

def old_bots():
    bots={}
    for key in ['5R32','5R192','5-32','4b','3','2','1','ben']:
        spec=dict(id=key,samples=192 if key=='5R192' else 16 if key=='ben' else 32,near_tie=.125,exploration=0.,artifact_sha256={},policy='fake.npz')
        if key.startswith('5R'):spec['layout_reduction']=dict(large_pool=4*spec['samples'],large_budget=spec['samples'])
        spec['identity']=digest(spec);bots[key]=spec
    return bots

class Gen5RZTests(unittest.TestCase):
    def test_watchdog_keeps_training_python_when_operator_uses_system_python(self):
        import os
        from types import SimpleNamespace
        from ops.watch_gen5 import launch
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);python=root/'python';python.touch()
            with patch.dict(os.environ,{},clear=True),patch('ops.watch_gen5.DEFAULT_PYTHON',python),patch('ops.watch_gen5.sys.executable','/system/python'),patch('ops.watch_gen5.subprocess.Popen',return_value=SimpleNamespace(pid=123)) as start:
                launch(root,'process.json',['ops/gen5_runtime.py'],'log')
            self.assertEqual(start.call_args.args[0][0],str(python))
            self.assertEqual(start.call_args.kwargs['env']['BRIDGE_ARENA_PYTHON'],str(python))

    def test_exact_allocation_and_unchanged_other_ratios(self):
        plan=load_plan();n=sum(plan['pair_weights'].values());self.assertEqual(n,370)
        self.assertEqual(Fraction(PAIR_WEIGHTS['5R32~5-32'],n),Fraction(1,5))
        self.assertEqual(Fraction(PAIR_WEIGHTS['5RZ32~5R32'],n),Fraction(3,10))
        previous=json.loads((Path(__file__).resolve().parents[1]/'configs/round5r.json').read_text())['pair_weights']
        for pair,weight in previous.items():
            if pair!='5R32~5-32':self.assertEqual(Fraction(PAIR_WEIGHTS[pair],n),Fraction(weight,37)*Fraction(1,2))

    def test_z_changes_only_identity_and_zero_policy_margin(self):
        old=old_bots();bots=make_bots(dict(bots=old),load_plan())
        for key,spec in old.items():self.assertEqual(bots[key],spec)
        z=deepcopy(bots['5RZ32']);r=deepcopy(bots['5R32'])
        self.assertEqual(z['near_tie'],0.);self.assertEqual(z['samples'],32)
        self.assertEqual(z.pop('policy_role'),'pimc-ties-only')
        for key in ['id','identity','near_tie']:z.pop(key);r.pop(key)
        self.assertEqual(z,r)

    def test_all_pairs_keep_budgets_bidders_and_swapped_seats(self):
        from bridge_harness.gen5_arena import run_board
        from ops.gen5_runtime import validate
        from tests.test_gen5r import Toy
        plan=load_plan();bots=make_bots(dict(bots=old_bots()),plan);board=next(generate(1,428))
        for pair in PAIR_WEIGHTS:
            used=[]
            def factory(spec,root,reference=None):used.append((spec['id'],spec['samples']));return Toy(spec,root,reference)
            m=dict(identity='fixture',roster=plan['roster'],target=1,seed=11,bots=bots,pair_schedule=[pair],
                audit_references={'5RZ32':'3','5R32':'3','5R192':'3'},common_bidder='5R32',
                audit=dict(probability=0,multiplier=1,max_depth=0,max_forks=0),ben_audit=dict(probability=0,multiplier=1,max_depth=0,max_forks=0))
            with patch('bridge_harness.gen5_arena.auction',lambda b,actors:(b,[])):
                r=run_board('.',m,board.to_dict(),0,{key:object() for key in bots},player_factory=factory)
            validate(r,m,0);a,b=pair.split('~')
            self.assertEqual(used,[(a,bots[a]['samples']),(b,bots[b]['samples'])]);self.assertEqual(r['bidding']['common/0']['bidders'],['5R32']*4)

    def test_policy_breaks_exact_ties_but_cannot_override_pimc_winner(self):
        game=Game(next(generate(1,419)))
        for _ in range(16):game.play(sorted(game.observation().legal)[0])
        o=game.observation();best,lower,tie=sorted(o.legal)[:3]
        class FakeDDS:
            tied=True
            def __init__(self,*a,**kw):self.n=0
            def close(self):pass
            def cache_stats(self):return dict(native_solves=self.n,hits=0,duplicate_worlds=0)
            def solve_batch(self,worlds,*a,**kw):
                self.n+=len(worlds);out=[]
                for i in range(len(worlds)):
                    values={c:8 if c==best or c==tie and self.tied else 8 if c==lower and i<len(worlds)-1 else 7 if c in [lower,tie] else 0 for c in o.legal}
                    out.append((values,0))
                return out
        class Policy:
            calls=0
            def choose(self,o,d,rng):
                self.calls+=1;values={card(c):100 if card(c)==lower else 10 if card(c)==tie else 0 for c,p in d['behavior_probabilities'].items() if p>0}
                return max(values,key=values.get),values
        bots=make_bots(dict(bots=old_bots()),load_plan())
        for key,expected in [('5R32',lower),('5RZ32',tie)]:
            policy=Policy()
            with patch('bridge_harness.dds.DDS',FakeDDS),patch('bridge_harness.mixed_arena.selector',return_value=policy):
                player=ArenaPlayer(bots[key],'.');decision=player.choose(o,random.Random(17));player.close()
            self.assertEqual(decision.card,expected);self.assertEqual(policy.calls,1)
            if key=='5RZ32':self.assertEqual(decision.details['selected_pimc_gap'],0.)
            else:self.assertGreater(decision.details['selected_pimc_gap'],0.)
        FakeDDS.tied=False;policy=Policy()
        with patch('bridge_harness.dds.DDS',FakeDDS),patch('bridge_harness.mixed_arena.selector',return_value=policy):
            player=ArenaPlayer(bots['5RZ32'],'.');decision=player.choose(o,random.Random(17));player.close()
        self.assertEqual(decision.card,best);self.assertEqual(policy.calls,0)

    def test_handoff_preserves_completed_source_and_only_uses_unplayed(self):
        from bridge_harness.bidding_env import deal_key
        from bridge_harness.selfplay import atomic_json
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'old';source.mkdir();dest=Path(td)/'new'
            for name in ['assets','artifacts','episodes','receipts','failures']:(source/name).mkdir()
            boards=list(generate(80,423));save(boards,source/'corpus.jsonl')
            m=dict(variant='5R',bots=old_bots(),target=80,corpus='corpus.jsonl',corpus_sha256=sha(source/'corpus.jsonl'),source_sha256=source_hash(),audit=dict(probability=0,multiplier=1,max_depth=0,max_forks=0),ben_audit=dict(probability=0,multiplier=1,max_depth=0,max_forks=0),bidding_conditions=['common','native'])
            m['identity']=digest(m);atomic_json(source/'manifest.json',m)
            with self.assertRaisesRegex(ValueError,'Drain'):prepare(dest,source)
            (source/'STOP').touch();(source/'WATCHDOG_STOP').touch()
            episode=source/'episodes/000007.json.gz';episode.write_bytes(b'completed source record retained')
            atomic_json(source/'receipts/000007.json',dict(index=7,family=deal_key(boards[7].hands,True),manifest_identity=m['identity'],episode_sha256=sha(episode)))
            before={p:p.read_bytes() for p in source.rglob('*') if p.is_file()};new=prepare(dest,source)
            self.assertEqual(new['target'],79);self.assertNotIn(7,json.loads((dest/'source-indices.json').read_text()))
            for path,content in before.items():self.assertEqual(path.read_bytes(),content)
            self.assertEqual(new['pair_weights'],PAIR_WEIGHTS)
            with self.assertRaisesRegex(ValueError,'overwrite'):prepare(dest,source)

if __name__=='__main__':unittest.main()
