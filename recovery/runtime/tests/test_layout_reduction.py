import itertools
import random
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np

from bridge_harness.layout_reduction import ReductionConfig, cluster_layouts, calibrate_weights, feature_mean, pack
from bridge_harness.layout_geometry import encode
from bridge_harness.bidding_sampling import WeightedSampler
from bridge_harness.core import Board, Game
from bridge_harness.players import PIMCPlayer


class LayoutReductionTests(unittest.TestCase):
    def test_cluster_mass_counts_duplicate_draws_without_discarding_any(self):
        x=np.array([[1.,0.]]*5 + [[0.,1.]]*2 + [[1.,1.]])
        ix,w,d=cluster_layouts(x, 3)
        self.assertEqual(len(set(ix)),3)
        np.testing.assert_allclose(sorted(w),[1/8,2/8,5/8])
        self.assertEqual(d['clusters'],3)
        self.assertEqual(len(cluster_layouts(x,3,tolerance=2)[0]),1)

    def test_calibration_corrects_pool_frequency_using_external_expectation(self):
        pool=np.array([[0.]]*9+[[1.]])
        ix=np.array([0,9]);prior=np.array([.9,.1])
        w,d=calibrate_weights(pool,ix,np.array([.7]),prior,ridge=0.)
        self.assertTrue(d['success']);np.testing.assert_allclose(w,[.3,.7],atol=1e-6)
        self.assertGreater(w[1],prior[1])
        self.assertAlmostEqual(float(w.sum()),1.)

    def test_unreachable_moment_remains_nonnegative_and_is_reported(self):
        w,d=calibrate_weights(np.array([[0.],[1.]]),[0,1],np.array([2.]),[.5,.5],ridge=0.)
        self.assertTrue((w>=0).all());self.assertAlmostEqual(w.sum(),1.)
        self.assertGreater(d['standardized_moment_mse_after'],0.)
        self.assertFalse(d['target_in_selected_hull_approximately'])

    def test_exact_sampler_feature_mean_matches_enumerated_legal_worlds(self):
        # Four unseen cards across two 2-card hands; all other cards are public.
        cards=(35,36,37,51); known=((0,1),(2,3),None,None)
        unseen=set(cards);visible=set(sum((list(h) for h in known if h is not None),[]))
        played=sorted(set(range(52))-unseen-visible)
        history=tuple((s, c) for s,row in enumerate(np.array(played).reshape(4,11)) for c in row)
        # Keep each public trick in one suit to avoid imposing accidental voids.
        o=SimpleNamespace(known_hands=known,history=history,actor=0)
        # The tiny enumeration checks the sampler's actual allowed assignments,
        # including any voids inferred from this synthetic public history.
        logits=np.zeros((52,4));logits[37,2]=1.1;logits[51,3]=.6
        # Supply a consistent no-void base with the desired remaining capacities.
        base=SimpleNamespace(unknown=(2,3),caps=(2,2),suits=tuple(tuple(c for c in cards if c//13==s) for s in range(4)),allowed=((True,True),)*4)
        with patch('bridge_harness.bidding_sampling.Sampler',return_value=base): sampler=WeightedSampler(o,logits)
        worlds=[];mass=[]
        for a in itertools.combinations(cards,2):
            b=tuple(c for c in cards if c not in a);worlds.append((known[0],known[1],a,b))
            mass.append(np.exp(sum(logits[c,2] for c in a)+sum(logits[c,3] for c in b)))
        mass=np.array(mass);mass/=mass.sum()
        raw=np.stack([pack(w,4,0,()) for w in worlds]);fixed=np.tile([1,1,0,0],(len(worlds),1))
        np.testing.assert_allclose(feature_mean(sampler,o),mass@encode(raw,fixed),atol=1e-12)

    def test_size_schedule(self):
        c=ReductionConfig()
        self.assertEqual(c.schedule(13)[:2],(128,32));self.assertIsNone(c.schedule(8))
        self.assertEqual(ReductionConfig(medium_enabled=True).schedule(8)[:2],(64,16))
        self.assertIsNone(c.schedule(6))

    def test_weighted_player_uses_calibrated_values_for_defender(self):
        from bridge_harness.core import hand_text, symbol
        deck=list(range(52));random.Random(19).shuffle(deck)
        board=Board.from_dict(dict(id='weighted',hands=[hand_text(deck[i*13:(i+1)*13]) for i in range(4)],contract='3N',declarer='N',dealer='N',vulnerability='None'))
        o=Game(board).observation()
        class FakeDDS:
            def __init__(self,*a,**kw):self.n=0;self.scores=[]
            def close(self):pass
            def cache_stats(self):return dict(native_solves=self.n,hits=0,duplicate_worlds=0)
            def solve_batch(self,worlds,*a,**kw):
                self.n+=len(worlds)
                self.scores=[{c:(sum(h[(c%3)])%7)+(c%4) for c in o.legal} for h in worlds]
                return [(q,0) for q in self.scores]
        with patch('bridge_harness.dds.DDS',FakeDDS):
            player=PIMCPlayer(objective='tricks',sampler_factory=lambda obs:WeightedSampler(obs),layout_reduction=dict(large_pool=24,large_budget=6))
            decision=player.choose(o,random.Random(71));d=decision.details
            weights=np.array(d['layout_reduction']['actual_weights'])
            self.assertAlmostEqual(weights.sum(),1.)
            self.assertLessEqual(d['samples'],6)
            for c in o.legal:
                expected=float(weights@np.array([q[c]-13 for q in player.dds.scores]))
                self.assertAlmostEqual(d['estimates'][symbol(c)]['utility'],expected)
                self.assertIsNone(d['estimates'][symbol(c)]['utility_stderr'])

    def test_disabled_and_small_position_paths_do_not_change_rng_or_decision(self):
        # Fake DDS lets the integration test inspect draws and weighted means.
        class FakeDDS:
            def __init__(self,*a,**kw):self.n=0
            def close(self):pass
            def cache_stats(self):return dict(native_solves=self.n,hits=0,duplicate_worlds=0)
            def solve_batch(self,worlds,trump,leader,trick,fixed_seats=()):
                self.n+=len(worlds)
                return [({c: int(37 in h[1])+(c%3) for c in o.legal},0) for h in worlds]
        deck=list(range(52));random.Random(4).shuffle(deck)
        from bridge_harness.core import hand_text
        b=Board.from_dict(dict(id='test',hands=[hand_text(deck[i*13:(i+1)*13]) for i in range(4)],contract='3N',declarer='N',dealer='N',vulnerability='None'))
        game=Game(b)
        while len(game.history)<20:game.play(game.observation().legal[0])
        o=game.observation()
        with patch('bridge_harness.dds.DDS',FakeDDS):
            p=PIMCPlayer(samples=8);q=PIMCPlayer(samples=8,layout_reduction={})
            a=random.Random(8);b=random.Random(8)
            da=p.choose(o,a);db=q.choose(o,b)
            self.assertEqual(da,db);self.assertEqual(a.getstate(),b.getstate())


if __name__=='__main__':unittest.main()
