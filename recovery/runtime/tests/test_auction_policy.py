import random
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
import numpy as np
from bridge_harness.core import Board, Contract, Game, symbol
from bridge_harness.auction_policy import (encode_decision, public_extra, build_model,
    restore_parent, export_weights, AuctionSelectorWeights)
from bridge_harness.policy_selector import build_model as old_model, SelectorWeights


class AuctionPolicyTests(unittest.TestCase):
    def board(self):
        return Board('test',tuple(tuple(range(i,52,4)) for i in range(4)),
            Contract(3,'N',0),0,'None',('1N','PASS','3N','PASS','PASS','PASS'),auction_source='ben')

    def details(self,o):
        return {'samples':32,'near_tie':.125,
            'behavior_probabilities':{symbol(c):1/len(o.legal) for c in o.legal},
            'estimates':{symbol(c):{'utility':8 if o.actor%2==o.contract.declarer%2 else -8} for c in o.legal}}

    def test_direct_auction_changes_inputs_hidden_cards_do_not(self):
        b=self.board();o=Game(b).observation();d=self.details(o);x,_=encode_decision(o,d)
        other=replace(b,auction=('3N','PASS','PASS','PASS'))
        y,_=encode_decision(Game(other).observation(),d)
        self.assertFalse(np.array_equal(x['calls'],y['calls']))
        h=list(b.hands);h[0],h[2]=h[2],h[0]
        z,_=encode_decision(Game(replace(b,hands=tuple(h))).observation(),d)
        for k in x:np.testing.assert_array_equal(x[k],z[k])
        d.update(owner_target=list(range(52)),imps=24,final_tricks=13)
        z,_=encode_decision(o,d)
        for k in x:np.testing.assert_array_equal(x[k],z[k])

    def test_rotation_and_synthetic_mask(self):
        b=self.board();g=Game(b)
        for _ in range(7):g.play(g.observation().legal[0])
        r=Game(replace(b,hands=b.hands[-1:]+b.hands[:-1],dealer=1,contract=replace(b.contract,declarer=1)))
        for _,c in g.history:r.play(c)
        o=g.observation();d=self.details(o);x,_=encode_decision(o,d);y,_=encode_decision(r.observation(),d)
        for k in x:np.testing.assert_array_equal(x[k],y[k])
        calls,seats,_=public_extra(o,32,.125,synthetic=True)
        self.assertTrue((calls==0).all());self.assertTrue((seats==4).all())

    def test_parent_preservation_and_trained_export(self):
        import tensorflow as tf
        from bridge_harness.auction_policy import LAYERS
        tf.keras.utils.set_random_seed(4)
        o=Game(self.board()).observation();x,_=encode_decision(o,self.details(o))
        state_size=x['state'].shape[-1];action_size=x['actions'].shape[-1]
        old=old_model(state_size-59,action_size)
        # Nonzero action weights ensure the preservation test is meaningful.
        w,b=old.get_layer('action_score').get_weights();w[:]=.03;old.get_layer('action_score').set_weights([w,b])
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'old.npz';z={}
            for name in LAYERS:z[name+'_kernel'],z[name+'_bias']=old.get_layer(name).get_weights()
            np.savez(p,**z);model=build_model(state_size,action_size);restore_parent(model,p)
            q=Path(folder)/'new.npz';export_weights(model,q)
            np.testing.assert_allclose(AuctionSelectorWeights(q).predict(x),SelectorWeights(p).predict(dict(x,state=x['state'][:,:state_size-59])),atol=1e-6)
            w,b=model.get_layer('state_hidden').get_weights();w[-384:]=.03;model.get_layer('state_hidden').set_weights([w,b])
            export_weights(model,q);raw=model({k:x[k] for k in ('state','actions','calls','seats')})
            scores=raw['score'].numpy()[...,0];scores-=(scores*x['mask']).sum(1,keepdims=True)/x['mask'].sum(1,keepdims=True)
            np.testing.assert_allclose(AuctionSelectorWeights(q).predict(x),x['q']+raw['value'].numpy()+scores,atol=2e-6)
            from bridge_harness.fork_policy import ForkAdvantageWeights
            with np.load(q) as loaded:weights={key:loaded[key] for key in loaded.files}
            np.savez(q,**weights,imp_linear_coef=np.arange(9,dtype='float32')/10)
            imp=ForkAdvantageWeights(q)
            advantage=imp.advantages(x,np.array([0]))
            self.assertEqual(advantage[0,0],0.)
            swapped=imp.advantages(x,np.array([1]))
            self.assertAlmostEqual(float(advantage[0,1]),-float(swapped[0,0]),places=6)


if __name__=='__main__':unittest.main()
