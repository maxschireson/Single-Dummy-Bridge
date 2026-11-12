import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('promote_belief',Path(__file__).resolve().parents[1]/'ops/promote_belief_on_predictions.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class PredictionPromotionTests(unittest.TestCase):
    def setUp(self):
        self.before={source:{view:dict(nll=1.,accuracy=.5,uncertain_card_labels=100)}
            for source,view in [('play','all'),('bidding','complete_auction'),('ben','complete_auction')]}
        self.after=copy.deepcopy(self.before)
        for rows in self.after.values():
            for row in rows.values():row.update(nll=.99,accuracy=.51)

    def test_promotes_without_play_results(self):
        self.assertTrue(module.prediction_gate(self.before,self.after)['promote'])

    def test_requires_both_metrics(self):
        for rows in self.after.values():
            for row in rows.values():row['accuracy']=.49
        self.assertFalse(module.prediction_gate(self.before,self.after)['promote'])
        for rows in self.after.values():
            for row in rows.values():row.update(nll=1.01,accuracy=.51)
        self.assertFalse(module.prediction_gate(self.before,self.after)['promote'])

    def test_rejects_mismatched_labels_and_invalid_metrics(self):
        self.after['play']['all']['uncertain_card_labels']=99
        with self.assertRaises(ValueError):module.prediction_gate(self.before,self.after)
        self.after['play']['all'].update(uncertain_card_labels=100,nll=float('nan'))
        with self.assertRaises(ValueError):module.prediction_gate(self.before,self.after)
