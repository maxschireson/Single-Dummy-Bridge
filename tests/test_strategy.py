# SPDX-License-Identifier: Apache-2.0
"""Independent policy enumeration, executable witnesses, and information boundaries."""
from dataclasses import replace
from itertools import combinations
import json
from pathlib import Path
import random
import unittest

from bridge_harness.core import Contract, Game, card
from bridge_harness.corpus import generate
from bridge_harness.dds import DDS
from bridge_harness.players import GreedyPlayer
from bridge_harness.rollout import PolicyPlanner, ViewPolicy, execute_plan, observation_at
from bridge_harness.sampling import Sampler
from bridge_harness.strategy import AlphaMu, Position, SearchLimit, evaluate_policy, validate_worlds


def endings(seed, cards=2, count=3, declarer=2, leader=2):
    rng = random.Random(seed)
    deck = rng.sample(range(52), 4 * cards)
    hands = [tuple(sorted(deck[s * cards:(s + 1) * cards])) for s in range(4)]
    hidden = [s for s in range(4) if s % 2 != declarer % 2]
    pool = hands[hidden[0]] + hands[hidden[1]]
    splits = list(combinations(pool, cards))
    rng.shuffle(splits)
    worlds = []
    for split in splits[:count]:
        h = list(hands)
        h[hidden[0]], h[hidden[1]] = tuple(sorted(split)), tuple(sorted(set(pool) - set(split)))
        worlds.append(Position(tuple(h), leader, tricks=13 - cards))
    return worlds


class Unassigned(Exception):
    def __init__(self, history, legal):
        self.history, self.legal = history, legal


def enumerate_policies(worlds, contract, utility):
    """Independent reference: assign action variables, evaluate full strategies.

    No Pareto backups or vector min products. Find the next unassigned reachable
    information set, enumerate every legal assignment, then evaluate all worlds.
    Deliberately restricted to tiny games; unsuitable as the production solver.
    """
    policy, results = {}, set()
    def value(p, history):
        if p.done:
            return utility(p.tricks)
        if p.actor % 2 == contract.declarer % 2:
            if history not in policy:
                raise Unassigned(history, p.legal())
            c = policy[history]
            return value(p.play(c, contract.trump, contract.declarer), history + (c,))
        return min(value(p.play(c, contract.trump, contract.declarer), history + (c,)) for c in p.legal())
    def assign():
        try:
            results.add(tuple(value(p, ()) for p in worlds))
        except Unassigned as missing:
            for c in missing.legal:
                policy[missing.history] = c
                assign()
            del policy[missing.history]
    assign()
    return {v for v in results if not any(u != v and all(a >= b for a, b in zip(u, v)) for u in results)}


def late_observation(seed=5, cards=3):
    b = next(generate(1, seed=seed))
    g, rng = Game(b), random.Random(seed + 1)
    while len(g.history) < 52 - cards * 4 or g.actor % 2 != b.contract.declarer % 2:
        g.play(rng.choice(g.observation().legal))
    return g


class StrategyTests(unittest.TestCase):
    def test_exact_against_independent_policy_enumeration(self):
        for seed in range(20):
            contract = Contract(7, 'NSHDC'[seed % 5], seed % 4)
            worlds = endings(seed, declarer=contract.declarer, leader=contract.declarer)
            solver = AlphaMu(contract, 'tricks' if seed % 2 else 'make')
            result = solver.solve(worlds, [1, 2, 3])
            expected = enumerate_policies(worlds, contract, solver.utility)
            self.assertEqual({e.values for e in result.front}, expected, seed)
            self.assertTrue(result.executable)
            for e in result.front:
                self.assertEqual(e.values, tuple(evaluate_policy(p, e.policy, contract, solver.utility) for p in result.worlds))

    def test_three_card_policy_witnesses(self):
        for seed in range(12):
            solver = AlphaMu(Contract(6, 'NSHDC'[seed % 5], 2), 'score')
            r = solver.solve(endings(seed + 50, 3, 4), [1, 2, 3, 4])
            for e in r.front:
                self.assertEqual(e.values, tuple(evaluate_policy(p, e.policy, solver.contract, solver.utility) for p in r.worlds))
            reverse = solver.solve(tuple(reversed(r.worlds)), tuple(reversed(r.weights)))
            self.assertAlmostEqual(r.value, reverse.value)

    def test_validation(self):
        worlds = endings(4)
        bad = replace(worlds[0], hands=(worlds[0].hands[0],) * 4)
        for ws, weights in (([], []), ([bad], [1]), (worlds, [1]), (worlds, [0, 0, 0]),
                            (worlds, [1, -1, 2]), (worlds, [1, float('nan'), 2])):
            with self.assertRaises(ValueError):
                validate_worlds(ws, weights, 2)
        with self.assertRaises(ValueError):
            validate_worlds([worlds[0], replace(worlds[1], leader=1)], [1, 1], 2)
        w, weights = validate_worlds([worlds[0], worlds[0], worlds[1]], [1, 2, 3], 2)
        self.assertEqual(len(w), 2)
        self.assertEqual(weights, (0.5, 0.5))
        with self.assertRaises(SearchLimit):
            AlphaMu(Contract(7, 'N', 2), max_nodes=1).solve(worlds)

    def test_position_matches_real_game(self):
        for b in generate(8, seed=23):
            g, rng = Game(b), random.Random(8)
            while not g.done:
                o = g.observation()
                p = Position(tuple(tuple(sorted(h)) for h in g.hands), g.leader, tuple(g.trick), g.declarer_tricks)
                self.assertEqual(observation_at(p, tuple(g.history), o), o)
                c = rng.choice(o.legal)
                q = p.play(c, b.contract.trump, b.contract.declarer)
                g.play(c)
                self.assertEqual(q.hands, tuple(tuple(sorted(h)) for h in g.hands))
                self.assertEqual(q.tricks, g.declarer_tricks)
                self.assertEqual(q.trick, tuple(g.trick))

    def test_rollout_value_is_executable(self):
        for seed in range(4):
            g = late_observation(seed + 15, 4)
            o, rng = g.observation(), random.Random(seed)
            sampler = Sampler(o)
            worlds = [Position(sampler.draw(rng), o.leader, o.trick, o.declarer_tricks) for _ in range(4)]
            fallback, model = ViewPolicy(), ViewPolicy()
            plan = PolicyPlanner(fallback, model, decisions=2).plan(o, worlds, [1, 2, 3, 4], 'tricks')
            actual = sum(w * execute_plan(plan, p, o, model, lambda t: t) for w, p in zip([.1, .2, .3, .4], worlds))
            self.assertAlmostEqual(plan.value, actual)
            self.assertIn(plan.choose(o), o.legal)
            for view, c in plan.actions.items():
                self.assertIn(c, view.legal)
            fallback.close(); model.close()

    def test_defender_view_hides_declarer_and_partner(self):
        g = late_observation(61, 5)
        o = g.observation()
        p = Position(tuple(tuple(sorted(h)) for h in g.hands), g.leader, tuple(g.trick), g.declarer_tricks)
        # Advance legally to a defender node.
        history = o.history
        while p.actor % 2 == o.contract.declarer % 2:
            c = p.legal()[0]; history += ((p.actor, c),)
            p = p.play(c, o.contract.trump, o.contract.declarer)
        view = observation_at(p, history, o)
        hidden = [s for s in range(4) if view.known_hands[s] is None]
        h = list(p.hands)
        a, b = hidden
        if h[a] and h[b]:
            x, y = h[a][0], h[b][0]
            h[a] = tuple(sorted((set(h[a]) - {x}) | {y}))
            h[b] = tuple(sorted((set(h[b]) - {y}) | {x}))
            other = replace(p, hands=tuple(h))
            self.assertEqual(view, observation_at(other, history, o))
            policy = ViewPolicy()
            self.assertEqual(policy.choose(view), policy.choose(observation_at(other, history, o)))
            self.assertIsNone(view.known_hands[o.contract.declarer])
            self.assertIn(o.contract.declarer, Sampler(view).unknown)
            policy.close()


class StrategyDDSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.dds = DDS()
        except RuntimeError as e:
            raise unittest.SkipTest(str(e))

    @classmethod
    def tearDownClass(cls):
        cls.dds.close()

    def test_saved_fusion_counterexamples(self):
        for name in ('strategy_fusion', 'unresolved_guess'):
            fixture = json.loads((Path(__file__).parent / 'fixtures' / (name + '.json')).read_text())
            worlds = [Position(tuple(tuple(card(c) for c in h) for h in w['hands']), w['leader'], tricks=w['tricks']) for w in fixture['example']]
            solver = AlphaMu(Contract(6, fixture['strain'], 2), 'tricks', dds=self.dds)
            self.assertEqual(solver.solve(worlds).value, fixture['exact'])
            self.assertEqual(solver.solve(worlds, max_plies=1).value, fixture['pimc'])
            chosen = card(fixture['pimc_card'])
            after = [p.play(chosen, solver.contract.trump, 2) for p in worlds]
            self.assertEqual(solver.solve(after).value, fixture['pimc_root_achievable'])

    def test_budget_fallback_restores_pimc_random_stream(self):
        from bridge_harness.rollout import AlphaMuPlayer
        from bridge_harness.players import PIMCPlayer
        for seed in range(10, 40):
            g = late_observation(seed, 3)
            if len(g.observation().legal) > 1:
                break
        o = g.observation()
        player, baseline = AlphaMuPlayer(4, 'tricks', seconds=1e-12), PIMCPlayer(4, 'tricks')
        try:
            a, b = player.choose(o, random.Random(91)), baseline.choose(o, random.Random(91))
            self.assertEqual(a.details.get('alpha_mu_fallback'), 'budget_exhausted')
            self.assertEqual(a.card, b.card)
            self.assertEqual(a.details['estimates'], b.details['estimates'])
        finally:
            player.close(); baseline.close()

    def test_pimc_horizon_and_single_world_exact(self):
        for seed in range(25):
            contract = Contract(6, 'NSHDC'[seed % 5], seed % 4)
            worlds = endings(seed + 100, 3, 4, contract.declarer, contract.declarer)
            solver = AlphaMu(contract, 'tricks', dds=self.dds)
            horizon = solver.solve(worlds, max_plies=1)
            expected = {}
            for p in worlds:
                values, _ = self.dds.solve(p.hands, contract.trump, p.leader, p.trick)
                for c, v in values.items():
                    expected[c] = expected.get(c, 0) + (p.tricks + v) / len(worlds)
            self.assertAlmostEqual(horizon.value, max(expected.values()))
            self.assertFalse(horizon.executable)
            exact = solver.solve(worlds)
            self.assertLessEqual(exact.value, horizon.value + 1e-9)
            one = solver.solve([worlds[0]])
            values, _ = self.dds.solve(worlds[0].hands, contract.trump, worlds[0].leader, worlds[0].trick)
            self.assertEqual(one.value, worlds[0].tricks + max(values.values()))

    def test_pimc_and_alpha_mu_share_early_random_stream(self):
        from bridge_harness.runner import run_pair, replay
        for b in generate(3, seed=79):
            r = run_pair(b, dict(candidate='alphamu', baseline='pimc', common='greedy', samples=4, objective='tricks'))
            self.assertEqual(r['status'], 'ok')
            replay(r)
            for a, z in zip(r['tables'][0]['actions'], r['tables'][1]['actions']):
                if a.get('strategy_action') == 'alpha_mu_plan':
                    break
                self.assertEqual(a['card'], z['card'])

    def test_committed_strategy_and_self_match(self):
        from bridge_harness.runner import run_pair, replay
        for spec in ('strategy', 'alphamu', 'continuation'):
            r = run_pair(next(generate(1, seed=85)), dict(candidate=spec, baseline=spec, common='greedy', samples=4, objective='tricks'))
            self.assertEqual(r['status'], 'ok')
            self.assertEqual(r['score_difference'], 0)
            replay(r)
            if spec == 'strategy':
                plans = [a for a in r['tables'][0]['actions'] if 'strategy_value' in a]
                self.assertEqual(len(plans), 1)

    def test_pimc_tail_uses_legitimate_views(self):
        g = late_observation(8, 2)
        o = g.observation(); rng = random.Random(4)
        worlds = [Position(Sampler(o).draw(rng), o.leader, o.trick, o.declarer_tricks) for _ in range(3)]
        fallback, model = ViewPolicy('pimc', 2, 'tricks'), ViewPolicy('pimc', 2, 'tricks')
        try:
            plan = PolicyPlanner(fallback, model, 1).plan(o, worlds, objective='tricks')
            self.assertAlmostEqual(plan.value, sum(execute_plan(plan, p, o, model, lambda t: t) for p in worlds) / 3)
            self.assertGreater(plan.stats['dds_calls'], 0)
        finally:
            fallback.close(); model.close()


if __name__ == '__main__':
    unittest.main()
