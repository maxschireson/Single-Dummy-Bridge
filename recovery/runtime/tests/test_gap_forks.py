"""Gap forks and guess-size logging (docs/gen7_data_capture_2026-11-11.md).

No engine, model or DDS is needed: the players below fabricate search estimates.
"""
import itertools
import random
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bridge_harness.core import SEATS, symbol
from bridge_harness.corpus import generate
from bridge_harness.fork_audit import (ForkBudget, GapForks, GAP_SELECTION, audited_gain, collect_board,
                                       gap_eligible, gap_picks, stream)
from bridge_harness.gen5_arena import run_board
from bridge_harness.gen6 import Gen6Player
from bridge_harness.players import Decision
from ops.gen5_runtime import validate
from ops.prepare_gen6 import gap_fork_block

GAPS = [0., 0., .1, .3, .45, .8, 1.5]      # two tied best cards, then cards in every band


class GapToy:
    """A stand-in for a Gen 6 search decision: lowest card, fabricated estimates, a tied reference."""
    def __init__(self, spec=None, root=None, reference=None):
        pass

    def choose(self, o, rng):
        cards = sorted(o.legal)
        if len(cards) == 1:
            return Decision(cards[0], {'forced': True})
        estimates = {symbol(c): dict(utility=-g, utility_stderr=None, gap_to_best=g, gap_stderr=None, declarer_tricks=0.)
                     for c, g in zip(cards, GAPS + [2.] * 13)}
        return Decision(cards[0], dict(gen6=dict(source='toy'), estimates=estimates, reference_card=symbol(cards[1])))

    def close(self):
        pass


ASSIGNMENTS = ['candidate', 'opponent', 'candidate', 'opponent']


def collect(seed=901, gap=None, board_seed=611):
    board = next(generate(1, board_seed))
    budget = ForkBudget(probability=.5, multiplier=1000, max_depth=2, max_forks=64)
    players = {'candidate': GapToy(), 'opponent': GapToy()}
    return board, budget, collect_board(board, players, ASSIGNMENTS, seed, budget, {}, **({} if gap is None else {'gap': gap}))


def cards(table):
    return [a['card'] for a in table['actions']]


def audit_view(record):
    keys = ('parent_table', 'ply', 'actor', 'depth', 'candidate_card', 'reference_card', 'candidate_table',
            'reference_table', 'gain_imps', 'identical_action', 'selection')
    return [tuple(a[k] for k in keys) for a in record['audits']]


class GapForkTests(unittest.TestCase):
    def test_bands_and_settings(self):
        g = GapForks(per_band=2, bands=[.125, .5])
        self.assertEqual([g.band(x) for x in (.03125, .125, .15625, .5, .53125, 3.)], [0, 0, 1, 1, 2, 2])
        self.assertEqual(GapForks(bands=[.25]).band(1.), 1)
        for bad in (dict(per_band=-1), dict(bands=[.5, .125]), dict(bands=[0., .5]), dict(max_cpu_share=-1), dict(bands=[.5, .5])):
            with self.assertRaises(ValueError):
                GapForks(**bad)

    def test_root_and_audits_are_identical_with_and_without_gap_forks(self):
        _, _, plain = collect()
        _, _, off = collect(gap=GapForks(per_band=0))
        _, budget, on = collect(gap=GapForks(per_band=2, max_cpu_share=1e9))
        for record in (plain, off):
            self.assertNotIn('gap_forks', record)
            self.assertNotIn('gap_cpu', record['compute'])
            self.assertFalse(any('fork_kind' in t for t in record['tables']))
        self.assertTrue(plain['audits'] and any(not a['identical_action'] for a in plain['audits']))
        for record in (off, on):
            self.assertEqual(audit_view(record), audit_view(plain))
            self.assertEqual([cards(t) for t in record['tables'][:len(plain['tables'])]], [cards(t) for t in plain['tables']])
        # Gap forks are appended after every audit table and never charge the audit budget.
        extra = on['tables'][len(plain['tables']):]
        self.assertTrue(extra and all(t.get('fork_kind') == 'gap' and t['depth'] == 1 for t in extra))
        self.assertFalse(any('fork_kind' in t for t in on['tables'][:len(plain['tables'])]))
        self.assertAlmostEqual(budget.branch_cpu, sum(t['cpu_seconds'] for t in on['tables'][1:len(plain['tables'])]))
        self.assertAlmostEqual(on['compute']['gap_cpu'], sum(t['cpu_seconds'] for t in extra))

    def test_each_gap_fork_is_one_forced_inferior_card_then_the_same_players(self):
        config = GapForks(per_band=2, max_cpu_share=1e9)
        board, _, record = collect(gap=config)
        root = record['tables'][0]
        events = record['gap_forks']
        self.assertEqual(len(events), 6)                      # three bands, two decisions each
        self.assertEqual(len({(e['ply'], e['forced_card']) for e in events}), len(events))
        per_band = {}
        for e in events:
            per_band[e['band']] = per_band.get(e['band'], 0) + 1
            action = root['actions'][e['ply']]
            fork = record['tables'][e['fork_table']]
            self.assertTrue(gap_eligible(action))
            self.assertEqual((e['parent_table'], e['selection'], e['chosen_card']), (0, GAP_SELECTION, action['card']))
            self.assertNotEqual(e['forced_card'], action['card'])
            self.assertEqual(e['estimated_gap'], action['estimates'][e['forced_card']]['gap_to_best'])
            self.assertGreater(e['estimated_gap'], 0)
            self.assertEqual(config.band(e['estimated_gap']), e['band'])
            self.assertEqual(e['actor'], SEATS.index(action['seat']))
            self.assertAlmostEqual(e['propensity'], min(1., config.per_band / e['decisions_in_band']) / e['cards_in_band'])
            # The fork: recorded prefix, the forced card, then ordinary decisions with no audit draw.
            self.assertEqual(cards(fork)[:e['ply']], cards(root)[:e['ply']])
            self.assertTrue(all(a.get('replayed_prefix') for a in fork['actions'][:e['ply']]))
            self.assertTrue(all(set(a) == {'ply', 'seat', 'controller', 'player', 'card', 'replayed_prefix'}
                                for a in fork['actions'][:e['ply']]))      # bare cards: details stay in the root
            forced = fork['actions'][e['ply']]
            self.assertTrue(forced['counterfactual_forced'])
            self.assertEqual(forced['card'], e['forced_card'])
            self.assertFalse(any('audit_draw' in a for a in fork['actions'][e['ply'] + 1:]))
            self.assertEqual(fork['node'], f"root/gap/{e['ply']}/{e['forced_card']}")
            # Realized cost is root minus fork, from the side of the seat that played the card.
            self.assertEqual(e['realized_cost_imps'], audited_gain(root['ns_score'], fork['ns_score'], e['actor']))
            declaring = e['actor'] % 2 == board.contract.declarer % 2
            side = lambda t: t['declarer_tricks'] if declaring else 13 - t['declarer_tricks']
            self.assertEqual(e['realized_cost_tricks'], side(root) - side(fork))
        self.assertEqual(per_band, {0: 2, 1: 2, 2: 2})
        # Both partnerships' Gen 6 decisions are eligible, not only the candidate's.
        eligible_players = {a['player'] for a in root['actions'] if gap_eligible(a)}
        self.assertEqual(eligible_players, {'candidate', 'opponent'})

    def test_draw_is_reproducible_and_uses_only_its_own_stream(self):
        _, _, a = collect(gap=GapForks(per_band=2, max_cpu_share=1e9))
        _, _, b = collect(gap=GapForks(per_band=2, max_cpu_share=1e9))
        view = lambda r: [(e['ply'], e['forced_card'], e['band'], e['fork_table']) for e in r['gap_forks']]
        self.assertEqual(view(a), view(b))
        self.assertEqual([cards(t) for t in a['tables']], [cards(t) for t in b['tables']])
        actions = a['tables'][0]['actions']
        config = GapForks(per_band=2)
        again = gap_picks(actions, config, stream(901, 'gap-fork', a['family'], 'root'))
        self.assertEqual([(p['ply'], p['forced_card']) for p in again], [(e['ply'], e['forced_card']) for e in a['gap_forks']])
        other = gap_picks(actions, config, stream(902, 'gap-fork', a['family'], 'root'))
        self.assertNotEqual([(p['ply'], p['forced_card']) for p in again], [(p['ply'], p['forced_card']) for p in other])

    def test_ineligible_actions(self):
        base = dict(ply=3, card='S2', gen6=dict(source='toy'), estimates={'S2': dict(gap_to_best=0.), 'S3': dict(gap_to_best=.25)})
        self.assertTrue(gap_eligible(base))
        for change in (dict(replayed_prefix=True), dict(counterfactual_forced=True), dict(forced=True), dict(gen6=None),
                       dict(estimates={'S2': dict(gap_to_best=0.), 'S3': dict(gap_to_best=0.)}), dict(estimates=None)):
            self.assertFalse(gap_eligible(dict(base, **change)), change)
        # A card the selector chose is never forked to, even if the search ranked it below the best.
        chosen_below_best = dict(base, card='S3')
        picks = gap_picks([chosen_below_best], GapForks(per_band=2), random.Random(1))
        self.assertEqual(picks, [])

    def test_budget_stop_is_recorded_not_silent(self):
        clock = itertools.count()
        with patch('bridge_harness.fork_audit.time.process_time', lambda: float(next(clock))):
            _, _, record = collect(gap=GapForks(per_band=2, max_cpu_share=0.))
        skips = [s for s in record['budget_skips'] if s['reason'] == 'gap-fork-budget']
        self.assertEqual(len(record['gap_forks']), 1)          # the first fork always runs
        self.assertEqual(len(skips), 5)
        self.assertTrue(all(s['selection'] == GAP_SELECTION and 'propensity' in s and 'band' in s for s in skips))

    def test_run_board_reads_the_manifest_and_skips_ben(self):
        board = next(generate(1, 343))
        bots = {k: dict(id=k, identity=k) for k in ('6-32', '5RZ32')}
        bots['ben'] = dict(id='ben', identity='ben', engine='ben')
        for pair, expect in (('6-32~5RZ32', True), ('6-32~ben', False)):
            for settings in (dict(per_band=2, bands=[.125, .5], max_cpu_share=1e9), None, dict(per_band=0)):
                m = dict(identity='test', roster=['6-32', '5RZ32', 'ben'], target=1, seed=11, bots=bots, pair_schedule=[pair],
                         audit_references={'6-32': '5RZ32'}, common_bidder='6-32',
                         audit=dict(probability=.5, multiplier=1000, max_depth=1, max_forks=8),
                         ben_audit=dict(probability=0, multiplier=1, max_depth=0, max_forks=0))
                if settings is not None:
                    m['gap_fork'] = settings
                with patch('bridge_harness.gen5_arena.auction', lambda b, actors: (b, [])):
                    r = run_board('.', m, board.to_dict(), 0, {k: object() for k in bots}, player_factory=GapToy)
                validate(r, m, 0)
                active = expect and settings is not None and settings['per_band'] > 0
                self.assertEqual('gap_cpu' in r, active, (pair, settings))
                for table in r['unique_tables'].values():
                    self.assertEqual('gap_forks' in table, active)
                    if active:
                        self.assertTrue(table['gap_forks'])
                if active:
                    self.assertEqual(r['gap_fork_count'], sum(len(t['gap_forks']) for t in r['unique_tables'].values()))

    def test_plan_block(self):
        self.assertIsNone(gap_fork_block({}))
        self.assertEqual(gap_fork_block({'gap_fork': {'per_band': 3, 'bands': [.25]}}),
                         dict(per_band=3, bands=[.25], max_cpu_share=1.5))
        for bad in ({'rate': 1.}, {'per_band': -2}, {'bands': [.5, .125]}):
            with self.assertRaises((ValueError, TypeError)):
                gap_fork_block({'gap_fork': bad})


def observation(actor, legal, declarer_tricks=0, plies=0):
    return SimpleNamespace(actor=actor, legal=tuple(legal), declarer_tricks=declarer_tricks, history=((0, 0),) * plies,
                           contract=SimpleNamespace(declarer=0))


def decide(o, solved, weights, near_tie=0.):
    stats = dict(native_solves=0, hits=0, duplicate_worlds=0)
    return Gen6Player.search_decision(SimpleNamespace(near_tie=near_tie), o, random.Random(5),
                                      [(v, 1) for v in solved], weights, stats, stats, {})


class GuessSizeTests(unittest.TestCase):
    def test_two_way_guess(self):
        a, b = 3, 17
        for actor in (0, 1):                                  # declaring side, then a defender
            d = decide(observation(actor, (a, b)), [{a: 10, b: 9}, {a: 9, b: 10}], [.5, .5]).details
            self.assertAlmostEqual(d['guess_size'], .5)
            self.assertAlmostEqual(d['estimates'][symbol(a)]['best_share'], .5)
            self.assertAlmostEqual(d['estimates'][symbol(b)]['best_share'], .5)
            self.assertAlmostEqual(d['layout_best_utility'] - d['guess_size'], max(e['utility'] for e in d['estimates'].values()))

    def test_no_guess_when_one_card_is_best_everywhere(self):
        a, b = 3, 17
        d = decide(observation(0, (a, b)), [{a: 10, b: 9}, {a: 8, b: 8}, {a: 7, b: 5}], [.2, .3, .5]).details
        self.assertEqual(d['guess_size'], 0.)
        self.assertAlmostEqual(d['estimates'][symbol(a)]['best_share'], 1.)
        self.assertAlmostEqual(d['estimates'][symbol(b)]['best_share'], .3)

    def test_logging_changes_neither_the_choice_nor_the_existing_estimates(self):
        rng = random.Random(77)
        for _ in range(200):
            legal = rng.sample(range(52), rng.randint(2, 6))
            actor = rng.randrange(4)
            plies = 4 * rng.randrange(6)
            remaining = 13 - plies // 4
            taken = rng.randint(0, plies // 4)
            layouts = rng.randint(1, 8)
            solved = [{c: rng.randint(0, remaining) for c in legal} for _ in range(layouts)]
            raw = [rng.random() + .01 for _ in range(layouts)]
            weights = [w / sum(raw) for w in raw]
            o = observation(actor, legal, taken, plies)
            result = decide(o, solved, weights)
            # The previous implementation, restated.
            declaring = actor % 2 == 0
            means = {c: 0. for c in legal}
            for values, w in zip(solved, weights):
                for c, t in values.items():
                    total = taken + (t if declaring else remaining - t)
                    means[c] += float(w) * (total if declaring else -total)
            best = max(means.values())
            eligible = sorted(c for c, v in means.items() if best - v <= 1e-9)
            self.assertEqual(result.card, random.Random(5).choice(eligible))
            d = result.details
            for c in legal:
                self.assertEqual(d['estimates'][symbol(c)]['utility'], means[c])
                self.assertEqual(d['estimates'][symbol(c)]['gap_to_best'], best - means[c])
                self.assertTrue(0. <= d['estimates'][symbol(c)]['best_share'] <= 1. + 1e-9)
            self.assertGreaterEqual(d['guess_size'], 0.)
            self.assertGreaterEqual(sum(e['best_share'] for e in d['estimates'].values()), 1. - 1e-9)
            spread = max(max(v.values()) - min(v.values()) for v in solved)
            self.assertLessEqual(d['guess_size'], spread + 1e-9)


if __name__ == '__main__':
    unittest.main()
