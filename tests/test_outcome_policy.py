import unittest
from dataclasses import asdict, replace
import numpy as np
from bridge_harness.auction_policy import encode_decision, public_extra
from bridge_harness.core import Board, Contract, Game, symbol
from bridge_harness.training import input_tensors
from bridge_harness.policy_selector import INPUT_KEYS
from scripts.prepare_outcome_policy import encode_many


class OutcomePolicyTests(unittest.TestCase):
    def test_matchpoint_readout_rewards_wins_and_half_ties(self):
        from bridge_harness.outcome_distribution import matchpoint_values
        reference=np.zeros((1,14));reference[0,9]=1
        p=np.zeros((1,3,14));p[0,0,8]=1;p[0,1,9]=1;p[0,2,10]=1
        np.testing.assert_allclose(matchpoint_values(p,reference),[[0,.5,1]])
        mixed=np.arange(1,15,dtype=float)[None,:];mixed/=mixed.sum()
        np.testing.assert_allclose(matchpoint_values(mixed[:,None,:],mixed),[[.5]])

    def test_distribution_context_and_probabilities_match_observable_position(self):
        import tempfile
        from pathlib import Path
        from bridge_harness.outcome_distribution import (public_context,build_distribution_model,
            export_distribution,DistributionWeights)
        from bridge_harness.core import vulnerable
        board=Board('test',tuple(tuple(range(i,52,4)) for i in range(4)),Contract(4,'H',0,1),vulnerability='Both')
        game=Game(board)
        for ply in range(20):
            o=game.observation()
            d=dict(samples=32,near_tie=.125,
                behavior_probabilities={symbol(c):1/len(o.legal) for c in o.legal},
                estimates={symbol(c):{'utility':8 if o.actor%2==0 else -8} for c in o.legal})
            x,_=encode_decision(o,d);ct=public_context(x['state'])
            self.assertEqual(ct['ply'][0],ply)
            self.assertEqual(ct['declaring'][0],o.actor%2==0)
            self.assertEqual(ct['level'][0],4);self.assertEqual(ct['strain'][0],1)
            self.assertEqual(ct['doubled'][0],1);self.assertTrue(ct['vulnerable'][0])
            expected=o.declarer_tricks if o.actor%2==0 else ply//4-o.declarer_tricks
            self.assertEqual(ct['already'][0],expected)
            game.play(o.legal[0])
        model=build_distribution_model(x['state'].shape[-1],x['actions'].shape[-1])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'model.npz';export_distribution(model,path,0.)
            p=DistributionWeights(path).probabilities(x)
            from bridge_harness.mixed_arena import selector
            self.assertIsInstance(selector(path),DistributionWeights)
        np.testing.assert_allclose(p.sum(-1),1,atol=1e-7)
        self.assertTrue((p[...,ct['remaining'][0]+1:]==0).all())

    def test_self_reference_protects_doubled_undertrick_and_has_zero_self_gain(self):
        from bridge_harness.outcome_distribution import self_reference_values,imp_payoffs
        board=Board('test',tuple(tuple(range(i,52,4)) for i in range(4)),Contract(4,'H',0,1),vulnerability='Both')
        game=Game(board);game.play(game.observation().legal[0])
        o=game.observation()  # Dummy: declaring partnership, no completed tricks.
        d=dict(samples=32,near_tie=.125,
            behavior_probabilities={symbol(c):1/len(o.legal) for c in o.legal},
            estimates={symbol(c):{'utility':9} for c in o.legal})
        x,_=encode_decision(o,d)
        p=np.zeros((1,2,14));p[0,0,9]=.99;p[0,0,10]=.01
        p[0,1,8]=.85;p[0,1,10]=.15
        value,reference=self_reference_values(p,x['state'],np.ones((1,2)))
        np.testing.assert_allclose(reference,p[:,0],atol=1e-7)
        self.assertAlmostEqual(value[0,0],0.,places=6)
        self.assertLess(value[0,1],0.)
        # A reference fixed at making can reverse this preference: the user's
        # proposed distribution corrects that specific undertrick failure.
        fixed=(p*imp_payoffs(x['state'])[:,None,:]).sum(-1)
        self.assertGreater(fixed[0,1],fixed[0,0])

    def test_vectorized_training_features_match_deployment_across_trick_boundaries(self):
        board=Board('test',tuple(tuple(range(i,52,4)) for i in range(4)),
            Contract(3,'N',0),0,'None',('1N','PASS','3N','PASS','PASS','PASS'),auction_source='ben')
        game=Game(board)
        observations=[];details=[];expected=[];cards=[];extras=[]
        for _ in range(35):
            o=game.observation()
            d=dict(samples=32,near_tie=.125,
                proposal_probabilities={symbol(c):1/len(o.legal) for c in o.legal},
                estimates={symbol(c):{'utility':8 if o.actor%2==o.contract.declarer%2 else -8} for c in o.legal})
            x,c=encode_decision(o,d)
            expected.append(x);cards.append(c[0]);extras.append(public_extra(o,32,.125))
            observations.append({k:v for k,v in input_tensors(asdict(o)).items() if k in INPUT_KEYS})
            details.append(d)
            game.play(o.legal[0])
        x,c=encode_many(observations,details)
        x['state']=np.concatenate([x['state'],np.stack([e[2] for e in extras])],axis=1)
        x['calls']=np.stack([e[0] for e in extras]);x['seats']=np.stack([e[1] for e in extras])
        for k in x:
            np.testing.assert_array_equal(x[k],np.concatenate([e[k] for e in expected]))
        np.testing.assert_array_equal(c,np.stack(cards))

    def test_outcome_and_audit_labels_cannot_enter_encoder(self):
        board=Board('test',tuple(tuple(range(i,52,4)) for i in range(4)),Contract(3,'N',0))
        o=Game(board).observation()
        a={k:v for k,v in input_tensors(asdict(o)).items() if k in INPUT_KEYS}
        d=dict(behavior_probabilities={symbol(c):1/len(o.legal) for c in o.legal},
               estimates={symbol(c):{'utility':-8} for c in o.legal})
        baseline,cards=encode_many([a],[d])
        d.update(gain_imps=24,final_tricks=13,hidden_hands=board.hands)
        result,changed=encode_many([a],[d])
        for k in baseline:np.testing.assert_array_equal(baseline[k],result[k])
        np.testing.assert_array_equal(cards,changed)


if __name__=='__main__':unittest.main()
