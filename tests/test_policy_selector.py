import random
import unittest
from dataclasses import replace
import numpy as np

from bridge_harness.core import Game
from bridge_harness.corpus import generate
from bridge_harness.training import input_tensors, observation_dict
from bridge_harness.belief_model import permute_observation
from bridge_harness.policy_selector import encode, INPUT_KEYS


def fixture(ply):
    g=Game(next(generate(1,93213)));rng=random.Random(831)
    while len(g.history)<ply:g.play(rng.choice(g.observation().legal))
    o=g.observation();a={k:v[None] for k,v in input_tensors(observation_dict(o)).items()}
    p=np.zeros((1,52),np.float32);u=np.full((1,52),np.nan,np.float32)
    p[0,list(o.legal)]=1/len(o.legal)
    declaring=o.actor%2==o.contract.declarer%2
    # Pretend all actions estimate 8 final declarer tricks.
    u[0,list(o.legal)]=8 if declaring else -8
    return o,a,p,u


class PolicySelectorTests(unittest.TestCase):
    def test_final_to_remaining_partnership_tricks(self):
        roles=set()
        for ply in range(1,30):
            o,a,p,u=fixture(ply);x,c=encode(a,p,u)
            decl=o.actor%2==o.contract.declarer%2;roles.add(decl)
            expected=8-o.declarer_tricks if decl else 5-(ply//4-o.declarer_tricks)
            np.testing.assert_allclose(x['q'][x['mask']>0],expected)
        self.assertEqual(roles,{False,True})

    def test_suit_permutation_preserves_action_identity_and_local_features(self):
        _,a,p,u=fixture(0);x,c=encode(a,p,u);y,d=encode(a,p,u,np.array([3,1,0,2]))
        for ci in range(int(x['mask'].sum())):
            dj=int(np.flatnonzero((d[0]==c[0,ci])&(y['mask'][0]>0))[0])
            np.testing.assert_array_equal(x['actions'][0,ci],y['actions'][0,dj])
            self.assertEqual(x['q'][0,ci],y['q'][0,dj])

    def test_seat_rotation_is_exactly_invariant(self):
        _,a,p,u=fixture(7);x,c=encode(a,p,u)
        b,_,_=permute_observation(a,1,np.arange(4));y,d=encode(b,p,u)
        for key in x:np.testing.assert_allclose(x[key],y[key])
        np.testing.assert_array_equal(c,d)

    def test_privileged_fields_cannot_affect_features(self):
        _,a,p,u=fixture(5);x,c=encode(a,p,u)
        a.update(owner_target=np.ones((1,52)),return_target=np.array([999]),action_target=np.array([50]))
        y,d=encode(a,p,u)
        for key in x:np.testing.assert_array_equal(x[key],y[key])

    def test_invalid_support_rejected(self):
        _,a,p,u=fixture(0);p*=0
        with self.assertRaises(ValueError):encode(a,p,u)

    def test_repeated_display_ids_are_distinct_deal_clusters(self):
        from bridge_harness.report import summarize
        boards=list(generate(2,8319));boards[1]=replace(boards[1],id=boards[0].id)
        records=[dict(board=b.to_dict(),config={'mode':'partnership'},status='ok',imps=0,first_difference=None,
            tables=[dict(declarer_tricks=6,ns_score=0,actions=[]) for _ in range(2)]) for b in boards]
        self.assertEqual(summarize(records)['independent_clusters'],2)


if __name__=='__main__':unittest.main()
