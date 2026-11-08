# SPDX-License-Identifier: Apache-2.0
from dataclasses import replace
from itertools import permutations
import random
import unittest
from bridge_harness.core import Contract
from bridge_harness.partitions import EndingDomain, certify_domain
from bridge_harness.strategy import AlphaMu
from scripts.count_ending_symmetries import counts
from test_strategy import endings


class PartitionTests(unittest.TestCase):
    def test_reweight_complete_frontier_and_subsupport(self):
        domain=EndingDomain(endings(881,3,1)[0],2)
        cert,_=certify_domain(domain,Contract(6,'N',2))
        self.assertEqual(len(cert.worlds),20)
        rng=random.Random(93)
        for _ in range(10):
            weights=[rng.randrange(4) for w in cert.worlds]
            chosen=cert.best(weights)
            expected=AlphaMu(cert.contract,'tricks').solve(cert.worlds,weights).value
            self.assertAlmostEqual(chosen.partition.weighted_value(weights),expected)
        for s in cert.strategies:
            with self.assertRaises(ValueError):s.partition.value(replace(cert.worlds[0],leader=1))

    def test_single_card_suit_orbits_by_enumeration(self):
        nt=set();trump=set()
        for seq in permutations(range(4)):
            for a in range(5):
                for b in range(a,5):
                    for c in range(b,5):
                        suits=(seq[:a],seq[a:b],seq[b:c],seq[c:])
                        nt.add(tuple(sorted(suits)))
                        trump.add((suits[0],tuple(sorted(suits[1:]))))
        r=counts(1)
        self.assertEqual(r['no_trump'],len(nt));self.assertEqual(r['one_canonical_trump'],len(trump))
        self.assertEqual(counts(4)['raw_fixed_strain_fixed_leader'],653534134886878245000)

if __name__=='__main__':unittest.main()
