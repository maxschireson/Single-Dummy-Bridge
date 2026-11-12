"""Protect score orientation, frozen inputs and hidden-information boundaries."""
from copy import deepcopy
from dataclasses import replace
import unittest

from bridge_harness.core import SEATS, hand_text, imps, symbol
from bridge_harness.corpus import generate
from bridge_harness.players import BenPlayer, Decision
from bridge_harness.report import trick_difference
from bridge_harness.runner import play_table
from scripts.evaluate_three_engines import validate


class RecordedPlayer:
    def __init__(self, ben=False): self.ben = ben

    def choose(self, o, rng):
        if len(o.legal) == 1: return Decision(o.legal[0], dict(forced=True))
        if self.ben:
            params = dict(hand=hand_text(o.original_hand(o.controller)), seat=SEATS[o.controller],
                          dealer=SEATS[o.dealer], vul=o.vulnerability,
                          ctx=BenPlayer.context(o.auction), matchtype='IMP', details='false')
            if o.history:
                params.update(dummy=hand_text(o.original_hand(o.contract.dummy)),
                              played=''.join(symbol(c) for _, c in o.history), format='false')
            details = dict(request=params, endpoint='play' if o.history else 'lead')
        else:
            details = dict(samples=32, dds_calls=32, batch=True, objective='tricks')
        return Decision(rng.choice(o.legal), details)


def fixture(declarer):
    b = next(generate(1, 20261119))
    b = replace(b, contract=replace(b.contract, declarer=declarer))
    players = {'ben': RecordedPlayer(True), 'uniform32': RecordedPlayer()}
    assignments = [['ben', 'uniform32']*2, ['uniform32', 'ben']*2]
    tables = [play_table(b, a, players, 17) for a in assignments]
    score_difference = tables[0]['ns_score']-tables[1]['ns_score']
    r = dict(board=b.to_dict(), status='ok', assignments=assignments, tables=tables,
             config=dict(mode='partnership', seed=17, candidate='ben', baseline='uniform32',
                         samples=32, objective='tricks', batch=True, near_tie=.125),
             score_difference=score_difference, imps=imps(score_difference))
    return b, r


class ThreeEngineAuditTests(unittest.TestCase):
    def test_both_declarer_orientations_and_complete_information_audit(self):
        for declarer in (0, 1):
            b, r = fixture(declarer)
            validate(r, b, 17, 'ben', 'uniform32')
            ben_table = 0 if declarer == 0 else 1
            expected = r['tables'][ben_table]['declarer_tricks'] - r['tables'][1-ben_table]['declarer_tricks']
            self.assertEqual(trick_difference(r), expected)

    def test_hidden_dummy_on_opening_lead_is_rejected(self):
        b, r = fixture(1)
        first = r['tables'][0]['actions'][0]
        self.assertEqual(first['player'], 'ben')
        first['request']['dummy'] = hand_text(b.hands[b.contract.dummy])
        with self.assertRaisesRegex(ValueError, 'incorrect information'):
            validate(r, b, 17, 'ben', 'uniform32')

    def test_changed_context_budget_and_score_are_rejected(self):
        b, r = fixture(0)
        other = replace(b, vulnerability='Both' if b.vulnerability != 'Both' else 'None')
        with self.assertRaisesRegex(ValueError, 'Changed deal'):
            validate(r, other, 17, 'ben', 'uniform32')
        changed = deepcopy(r)
        changed['config']['samples'] = 8
        with self.assertRaisesRegex(ValueError, 'setting'):
            validate(changed, b, 17, 'ben', 'uniform32')
        changed = deepcopy(r)
        changed['score_difference'] += 10
        with self.assertRaisesRegex(ValueError, 'oriented score'):
            validate(changed, b, 17, 'ben', 'uniform32')


if __name__ == '__main__': unittest.main()
