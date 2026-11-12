"""Gen 9 interfaces I3 and I6: the player model a bot is handed, and experience as additive statistics."""
import itertools
import json
import random
import unittest

from bridge_harness import experience as xp
from bridge_harness.player_model import PlayerModel, resolve


def board_delta(player, i, rng):
    """A made-up board's statistics, one of each kind."""
    spots = rng.choice([2, 3, 4])
    return xp.delta(player, f'cohort/{i}/table-0', {
        'bid.nt_range': xp.count(agree=rng.randint(0, 2), deviate=rng.randint(0, 1)),
        'bid.nt_range.miss': xp.hist([rng.randint(-2, 3) for _ in range(rng.randint(0, 3))]),
        'card.count': xp.count(**{f'hit/{spots}': rng.randint(0, 1), f'all/{spots}': 1}),
        'play.info': xp.moment([0., .5, 1.], [0., rng.random(), rng.random()]),
        'profile': xp.loglik(house=-rng.random(), precision=-3 * rng.random(), unknown=-2.),
    })


def close(a, b, tol=1e-9):
    """Equal up to rounding: floating-point sums depend on the order of addition."""
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(close(a[k], b[k], tol) for k in a)
    if isinstance(a, (list, tuple)):
        return isinstance(b, (list, tuple)) and len(a) == len(b) and all(close(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        return abs(a - b) <= tol
    return a == b


class Algebra(unittest.TestCase):
    def test_any_order_gives_the_same_store(self):
        rng = random.Random(5)
        deltas = [board_delta('ben', i, rng) for i in range(6)]
        stores = []
        for order in itertools.islice(itertools.permutations(deltas), 0, 720, 37):
            s = xp.empty('ben')
            for d in order:
                s = xp.add(s, d)
            stores.append(s)
        self.assertTrue(all(close(s, stores[0]) for s in stores))
        self.assertEqual(stores[0]['boards'], 6)
        self.assertEqual(stores[0]['stats']['play.info']['n'], 6.)

    def test_a_board_counts_once(self):
        rng = random.Random(1)
        d = board_delta('ben', 0, rng)
        once = xp.add(xp.empty('ben'), d)
        self.assertIs(xp.add(once, d), once)
        self.assertEqual(once['boards'], 1)

    def test_split_stores_merge_to_the_whole(self):
        rng = random.Random(2)
        deltas = [board_delta('ben', i, rng) for i in range(8)]
        whole, left, right = xp.empty('ben'), xp.empty('ben'), xp.empty('ben')
        for i, d in enumerate(deltas):
            whole = xp.add(whole, d)
            if i % 2:
                left = xp.add(left, d)
            else:
                right = xp.add(right, d)
        self.assertTrue(close(xp.merge(left, right), whole))
        self.assertTrue(close(xp.merge(right, left), whole))
        with self.assertRaises(ValueError):
            xp.merge(whole, left)                   # they share boards

    def test_histograms_align(self):
        a, b = xp.hist([2, 3, 3]), xp.hist([-1, 0])
        m = xp.merge_stat(a, b)
        self.assertEqual((m['lo'], m['bins']), (-1, [1., 1., 0., 1., 2.]))
        self.assertEqual(xp.merge_stat(xp.hist([]), a), a)

    def test_refusals(self):
        with self.assertRaises(ValueError):
            xp.merge_stat(xp.count(a=1), xp.hist([1]))
        with self.assertRaises(ValueError):
            xp.merge_stat(xp.moment([0, 1], [1, 2]), xp.moment([0, 2], [1, 2]))
        with self.assertRaises(ValueError):
            xp.merge_stat(xp.loglik(a=-1., b=-2.), xp.loglik(a=-1.))
        with self.assertRaises(ValueError):
            xp.add(xp.empty('ben'), board_delta('gib', 0, random.Random(0)))
        store = xp.add(xp.empty('ben'), board_delta('ben', 0, random.Random(0)))
        with self.assertRaises(ValueError):
            xp.add(xp.snapshot(store, 'epoch-1'), board_delta('ben', 1, random.Random(0)))

    def test_snapshot_is_separate_and_json(self):
        store = xp.add(xp.empty('ben'), board_delta('ben', 0, random.Random(0)))
        snap = xp.snapshot(store, 'epoch-1')
        self.assertNotIn('applied', snap)
        snap['stats']['bid.nt_range']['n']['agree'] = 99.
        self.assertNotEqual(store['stats']['bid.nt_range']['n']['agree'], 99.)
        self.assertEqual(xp.check(json.loads(json.dumps(snap)))['snapshot'], 'epoch-1')


class Estimators(unittest.TestCase):
    def test_rate_moves_from_the_prior_to_the_data(self):
        self.assertAlmostEqual(xp.rate(None, 'agree', no='deviate', prior=(19., 1.)), .95)
        few = xp.rate(xp.count(agree=2, deviate=2), 'agree', no='deviate', prior=(19., 1.))
        many = xp.rate(xp.count(agree=500, deviate=500), 'agree', no='deviate', prior=(19., 1.))
        self.assertGreater(few, .85)
        self.assertAlmostEqual(many, .5, delta=.01)
        self.assertAlmostEqual(xp.rate(xp.count(hit=3, all=4), 'hit', total='all', prior=(1., 1.)), 4 / 6)

    def test_honesty_allows_for_the_number_of_choices(self):
        rng = random.Random(3)
        for true_h in (0., .5, .9):
            tallies = {}
            for _ in range(4000):
                n = rng.choice([2, 2, 3, 4])
                honest = rng.random() < true_h
                hit = honest or rng.randrange(n) == 0          # a dishonest card is a random one of the n
                tallies[f'all/{n}'] = tallies.get(f'all/{n}', 0) + 1
                tallies[f'hit/{n}'] = tallies.get(f'hit/{n}', 0) + hit
            self.assertAlmostEqual(xp.choice_honesty(xp.count(**tallies), prior=(1., 1.)), true_h, delta=.04)
        self.assertAlmostEqual(xp.choice_honesty(None, prior=(3., 1.)), .75, delta=.001)

    def test_posterior_over_profiles(self):
        prior = {'house': .5, 'precision': .3, 'unknown': .2}
        self.assertEqual(xp.posterior(None, prior), prior)
        stat = dict(kind='loglik', n=20., ll={'house': -40., 'precision': -25., 'unknown': -34.})
        p = xp.posterior(stat, prior)
        self.assertGreater(p['precision'], .99)
        self.assertAlmostEqual(sum(p.values()), 1.)
        floored = xp.posterior(stat, prior, floor=.03)
        self.assertGreaterEqual(min(floored.values()), .01 - 1e-12)
        self.assertLess(xp.posterior(stat, prior, temper=.1)['precision'], p['precision'])
        with self.assertRaises(ValueError):
            xp.posterior(dict(kind='loglik', n=1., ll={'house': -1.}), prior)

    def test_grid_best_shrinks_to_the_prior(self):
        stat = dict(kind='moment', grid=[0., .3, 1.], n=4., sum=[0., 1.2, 4.0], sumsq=[0., 1., 5.])
        self.assertEqual(xp.grid_best(stat)[0], 1.)
        best, means = xp.grid_best(stat, prior_mean=[0., .5, -.5], prior_n=100.)
        self.assertEqual(best, .3)
        self.assertEqual(len(means), 3)


class Models(unittest.TestCase):
    def test_plain_model_is_the_default(self):
        m = PlayerModel('ben')
        self.assertTrue(m.plain)
        self.assertEqual(m.profiles, ((None, 1.),))
        self.assertEqual(m.boards, 0)
        self.assertIsNone(m.stat('card.count'))

    def test_profiles_are_normalised_and_checked(self):
        m = PlayerModel('p', profiles={'precision-a': .7, 'unknown': .3})
        self.assertEqual(m.profile_ids(), ('precision-a', None))
        self.assertFalse(m.plain)
        with self.assertRaises(ValueError):
            PlayerModel('p', profiles={'a': .7, 'b': .7})
        with self.assertRaises(ValueError):
            PlayerModel('p', profiles=[('a', .5), ('a', .5)])
        with self.assertRaises(ValueError):
            PlayerModel('p', kind='friend')

    def test_round_trip_and_experience(self):
        store = xp.add(xp.empty('ben'), board_delta('ben', 0, random.Random(0)))
        m = PlayerModel('ben', 'outside', {'house-gen6': .8, 'unknown': .2}, carding={'count': 'standard'},
                        experience=xp.snapshot(store, 'epoch-3'))
        again = PlayerModel.from_dict(json.loads(json.dumps(m.to_dict())))
        self.assertEqual(again, m)
        self.assertEqual((m.boards, m.snapshot), (1, 'epoch-3'))
        self.assertEqual(m.stat('play.info')['grid'], [0., .5, 1.])
        with self.assertRaises(ValueError):
            PlayerModel('ben', experience=store)               # the live store is not a snapshot

    def test_resolve(self):
        models = {'ben': {'kind': 'outside', 'carding': {'count': 'standard'}}, '*': {'kind': 'unknown', 'profiles': {'unknown': 1.}}}
        self.assertEqual(resolve('ben', models).carding, {'count': 'standard'})
        self.assertEqual(resolve('ben', models).id, 'ben')
        self.assertEqual(resolve('7s-32', models).id, '7s-32')
        self.assertTrue(resolve('7s-32').plain)
        self.assertTrue(resolve(None).plain)
        m = PlayerModel('x')
        self.assertIs(resolve(m, models), m)


if __name__ == '__main__':
    unittest.main()
