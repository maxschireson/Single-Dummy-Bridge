from concurrent.futures import ThreadPoolExecutor
import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bridge_harness.core import Game
from bridge_harness.corpus import generate
from bridge_harness.dds import DDS
from bridge_harness.dds_cache import PositionCache, position_key
from bridge_harness.sampling import Sampler
from bridge_harness.players import PIMCPlayer


def position(ply=28):
    g = Game(next(generate(1,seed=871)))
    rng = random.Random(19)
    for _ in range(ply):
        g.play(rng.choice(g.observation().legal))
    o = g.observation()
    worlds = [Sampler(o).draw(rng) for _ in range(5)]
    return o,worlds


class CacheTests(unittest.TestCase):
    def test_new_players_cache_by_default_and_can_disable(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'XDG_CACHE_HOME':tmp}):
            os.environ.pop('BRIDGE_DDS_CACHE',None)
            player = PIMCPlayer(2)
            try:
                self.assertIsNotNone(player.dds.cache)
                self.assertTrue((Path(tmp)/'single-dummy-bridge/dds-positions.sqlite').exists())
                snapshot=Path(tmp)/'snapshot.sqlite'
                player.dds.cache.backup(snapshot)
                self.assertTrue(snapshot.exists())
            finally:
                player.close()
            os.environ['BRIDGE_DDS_CACHE']=''
            player=PIMCPlayer(2)
            self.assertIsNone(player.dds.cache)
            player.close()

    def test_persistent_all_moves_hits_and_mixed_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'cache.sqlite'
            for ply in (0,28,29,30,31,48):
                o,worlds = position(ply)
                plain = DDS(cache_path='')
                cached = DDS(cache_path=path)
                args = (o.contract.trump,o.leader,o.trick)
                try:
                    expected = [plain.solve(w,*args)[0] for w in worlds]
                    cached.solve_batch(worlds[:2],*args)
                    actual = cached.solve_batch(worlds+worlds[:1],*args)
                    self.assertEqual([x[0] for x in actual],expected+expected[:1])
                    self.assertEqual(actual[0][1],0)
                    cached.close()
                    cached = DDS(cache_path=path)
                    with patch.object(cached,'_solve_batch_native',side_effect=AssertionError('Cache miss')):
                        again = cached.solve_batch(worlds,*args)
                    self.assertEqual([x[0] for x in again],expected)
                    self.assertTrue(all(n==0 for _,n in again))
                    self.assertEqual(cached.native_solves,0)
                    self.assertEqual(cached.solve(worlds[0],*args)[0],expected[0])
                finally:
                    plain.close()
                    cached.close()

    def test_invalid_batch_cannot_bypass_validation_via_hits(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = DDS(cache_path=Path(tmp)/'c.sqlite')
            o,worlds = position(28)
            args = (o.contract.trump,o.leader,o.trick)
            try:
                w = worlds[0]
                d.solve_batch([w],*args)
                bad = [list(h) for h in w]
                bad[0][0],bad[1][0] = bad[1][0],bad[0][0]
                with patch.object(d,'_solve_batch_native',side_effect=AssertionError('Searched invalid batch')):
                    with self.assertRaisesRegex(ValueError,'Fixed hand'):
                        d.solve_batch([w,bad],*args,fixed_seats=[0])
                    bad[0].pop()
                    with self.assertRaisesRegex(ValueError,'counts'):
                        d.solve_batch([w,bad],*args)
            finally:
                d.close()

    def test_keys_include_strain_leader_partial_trick(self):
        o,worlds = position(28)
        w = worlds[0]
        a = position_key(DDS._deal(w,0,0,()))
        self.assertNotEqual(a,position_key(DDS._deal(w,1,0,())))
        self.assertNotEqual(a,position_key(DDS._deal(w,0,1,())))
        self.assertEqual(a,position_key(DDS._deal([list(reversed(h)) for h in w],0,0,())))
        h = [list(x) for x in w]
        card = h[0].pop()
        self.assertNotEqual(a,position_key(DDS._deal(h,0,0,((0,card),))))

    def test_solver_namespaces_and_conflicting_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lib1,lib2 = root/'one',root/'two'
            lib1.write_bytes(b'one');lib2.write_bytes(b'two')
            a,b = PositionCache(root/'c.sqlite',lib1),PositionCache(root/'c.sqlite',lib2)
            try:
                a.put_many([(b'key',{3:4})])
                self.assertEqual(b.get_many([b'key']),{})
                with self.assertRaisesRegex(ValueError,'Conflicting'):
                    a.put_many([(b'key',{3:5})])
                self.assertEqual(a.get_many([b'key']),{b'key':{3:4}})
            finally:
                a.close();b.close()

    def test_separate_workers_share_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'c.sqlite'
            DDS(cache_path=path).close()
            o,worlds = position(28)
            def work(_):
                d = DDS(cache_path=path)
                try:
                    return [r[0] for r in d.solve_batch(worlds,o.contract.trump,o.leader,o.trick)]
                finally:
                    d.close()
            with ThreadPoolExecutor(max_workers=2) as pool:
                a,b = list(pool.map(work,range(2)))
            self.assertEqual(a,b)


if __name__ == '__main__':
    unittest.main()
