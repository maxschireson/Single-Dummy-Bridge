import unittest
from ops.global_tracking import build_tracking, play_equivalents, learning_metric


class GlobalTrackingTests(unittest.TestCase):
    def baseline(self):
        return dict(schema='bridge-global-tracking-v1', training={k: dict(value=0) for k in ('bidding', 'play')},
                    policy_audit_lines=dict(value=2), audit_runs=[dict(id='old', lines=2)])

    def test_deals_are_deduplicated_across_models_and_splits(self):
        result = build_tracking(self.baseline(), dict(training_datasets=[
            dict(domain='play', families=dict(a='train', b='validation')),
            dict(domain='play', families=dict(a='train', c='train', d='test'))],
            training_history_complete=dict(play=True)))
        self.assertEqual(result['training']['play']['value'], 2)

    def test_refresh_does_not_count_receipts_twice(self):
        ledger = dict(audit_runs=[dict(id='new', receipts=[dict(index=0, deviations=3), dict(index=0, deviations=3), dict(index=1, deviations=0)])])
        first = build_tracking(self.baseline(), ledger)
        second = build_tracking(first, ledger)
        self.assertEqual(second['policy_audit_lines']['value'], 5)

    def test_conflicting_receipts_and_regression_fail(self):
        with self.assertRaises(ValueError):
            build_tracking(self.baseline(), dict(audit_runs=[dict(id='old', receipts=[dict(index=0, deviations=1)])]))
        with self.assertRaises(ValueError):
            build_tracking(self.baseline(), dict(audit_runs=[dict(id='x', receipts=[dict(index=0, deviations=1), dict(index=0, deviations=2)])]))

    def test_search_budget_and_partial_audits(self):
        for samples, expected in [(16, .5), (32, 1), (64, 2)]:
            self.assertEqual(play_equivalents([dict(samples=samples, main_tables=2, fork_plies=0)]), expected)
        self.assertEqual(play_equivalents([dict(samples=32, main_tables=2, fork_plies=26)]), 1.25)

    def test_gain_and_uncertainty_share_normalization(self):
        e = dict(samples=32, boards=500, gain_imps_per_board=.2, gain_ci95=[-.1, .5])
        self.assertEqual(learning_metric(e, 1000), dict(value=.0002, ci95=[-.0001, .0005]))
        self.assertIsNone(learning_metric(None, 1000))
        with self.assertRaises(ValueError):
            learning_metric(dict(e, samples=16), 1000)

    def test_model_training_counts_preserve_scope_and_unknowns(self):
        model = dict(parameters=12, component='Policy', sha256='checkpoint',
                     decisions_seen=dict(value=100, kind='decisions', scope='latest_fit', coverage='exact'))
        result = build_tracking(self.baseline(), dict(models=[model]))
        self.assertEqual(result['models'][0]['decisions_seen']['value'], 100)
        model['decisions_seen']['kind'] = 'unseen-card observations'
        self.assertEqual(build_tracking(self.baseline(), dict(models=[model]))['models'][0]['decisions_seen']['kind'], 'unseen-card observations')
        model['decisions_seen'].update(value=None, coverage='pending')
        self.assertIsNone(build_tracking(self.baseline(), dict(models=[model]))['models'][0]['decisions_seen']['value'])
        for value in [-1, True, 1.5]:
            model['decisions_seen'].update(value=value, coverage='exact')
            with self.assertRaises(ValueError):
                build_tracking(self.baseline(), dict(models=[model]))
        model['decisions_seen'].update(value=0, coverage='pending')
        with self.assertRaises(ValueError):
            build_tracking(self.baseline(), dict(models=[model]))


if __name__ == '__main__':
    unittest.main()
