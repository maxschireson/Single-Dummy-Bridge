"""bridge_harness.play_head: the per-player head on the policy net (E9-14)."""
from pathlib import Path
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.play_head import PlayHead, _Entries, _objective, choice_log_likelihood, fit_cv, fit_head, penalty_scales  # noqa: E402

CAPSULE = Path(os.environ.get('GEN7_CAPSULE', '/home/claude/data/g7a1/recovery'))


def synthetic(n=400, dim=16, seed=0):
    rng = np.random.default_rng(seed)
    d = np.maximum(rng.normal(size=(n, 4, dim)), 0)
    W, b = rng.normal(size=(dim, 13)) * .3, rng.normal(size=13) * .1
    legal = rng.random((n, 52)) < .4
    legal[np.arange(n), rng.integers(0, 52, n)] = True
    legal[np.arange(n), rng.integers(0, 52, n)] = True
    return rng, d, W, b, legal


def sample(head, d, legal, W, b, rng):
    p = np.exp(head.log_policy(d, legal, W, b))
    K = np.zeros_like(legal)
    for j in range(len(d)):
        K[j, rng.choice(52, p=p[j])] = True
    return K


def test_gradient_matches_finite_differences():
    rng, d, W, b, legal = synthetic(60, 6)
    K = sample(PlayHead.identity(6), d, legal, W, b, rng)
    K |= legal & (rng.random(legal.shape) < .1)                  # some choices are classes of cards
    v = PlayHead.identity(6).vector() + rng.normal(size=1 + 6 + 13 + 6) * .1
    scale = penalty_scales(d, W)
    f, g = _objective(v, d, legal, K, W, b, 3., scale, 6, np.ones(len(d)))
    num = np.zeros_like(v)
    for k in range(len(v)):
        e = np.zeros_like(v)
        e[k] = 1e-6
        num[k] = (_objective(v + e, d, legal, K, W, b, 3., scale, 6, np.ones(len(d)))[0]
                  - _objective(v - e, d, legal, K, W, b, 3., scale, 6, np.ones(len(d)))[0]) / 2e-6
    assert np.allclose(g, num, rtol=1e-4, atol=1e-4)
    ent = _Entries(d, legal, K, W, b)                              # the sparse form used by the fit is the same function
    fs, gs = ent.objective(v, 3., scale)
    assert np.isclose(f, fs) and np.allclose(g, gs)


def test_identity_head_is_the_net():
    rng, d, W, b, legal = synthetic(20, 8)
    lp = PlayHead.identity(8).log_policy(d, legal, W, b)
    z = np.where(legal, (d @ W + b).reshape(20, 52), -np.inf)
    ref = z - np.logaddexp.reduce(z, axis=1, keepdims=True)
    assert np.allclose(lp[legal], ref[legal])


def test_fit_recovers_a_player_who_differs_and_leaves_one_who_does_not():
    rng, d, W, b, legal = synthetic(3000, 12, seed=1)
    true = PlayHead(1.6, np.zeros(12), np.linspace(-1, 1, 13), np.zeros(12))
    K = sample(true, d, legal, W, b, rng)
    groups = np.arange(len(d)) // 10
    tr, te = groups % 5 != 0, groups % 5 == 0
    head, cv = fit_cv(d[tr], legal[tr], K[tr], groups[tr], W, b)
    gain = (choice_log_likelihood(head, d[te], legal[te], K[te], W, b) - choice_log_likelihood(PlayHead.identity(12), d[te], legal[te], K[te], W, b)).mean()
    best = (choice_log_likelihood(true, d[te], legal[te], K[te], W, b) - choice_log_likelihood(PlayHead.identity(12), d[te], legal[te], K[te], W, b)).mean()
    assert gain > .6 * best > 0
    same = sample(PlayHead.identity(12), d, legal, W, b, rng)       # a player the net already describes
    h0, _ = fit_cv(d[tr], legal[tr], same[tr], groups[tr], W, b)
    change = (choice_log_likelihood(h0, d[te], legal[te], same[te], W, b) - choice_log_likelihood(PlayHead.identity(12), d[te], legal[te], same[te], W, b)).mean()
    assert abs(change) < .01


def test_strong_penalty_keeps_the_net():
    rng, d, W, b, legal = synthetic(200, 8)
    K = sample(PlayHead(2., np.ones(8), np.zeros(13), np.zeros(8)), d, legal, W, b, rng)
    h = fit_head(d, legal, K, W, b, lam=1e7)
    assert abs(h.tau - 1) < 1e-3 and np.abs(h.u).max() < 1e-3


BEN = Path(os.environ.get('BEN_FEEDS', '/home/claude/data/ben'))


@pytest.mark.skipif(not (CAPSULE / 'manifest.json').exists() or not BEN.exists(), reason='needs the Gen 7 capsule and a BEN feed')
def test_decoder_state_reproduces_the_net():
    import glob
    import json
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
    from gen9_ben_reading import ben_tables, load
    from bridge_harness.core import Game, card
    from bridge_harness.gen7 import Gen7Player
    from bridge_harness.play_head import decoder_state, policy_column
    m = json.loads((CAPSULE / 'manifest.json').read_text())
    p = Gen7Player(m['bots']['7s-32'], str(CAPSULE))
    feed = sorted(glob.glob(str(BEN / '*' / 'recovery' / 'episodes')))[0]
    path, key, _, _ = ben_tables([feed])[0]
    board, actions, _ = load(path, key)
    game = Game(board)
    for a in actions[:5]:
        game.play(card(a['card']))
    o = game.observation()
    batch = {k: v[None] for k, v in p.net.encode(o).items()}
    d, logits = decoder_state(p.net.params, batch)
    ref = p.net.log_policy_arrays(batch)
    legal = np.asarray(batch['legal'])
    lp = logits - np.logaddexp.reduce(np.where(legal, logits, -np.inf), axis=1, keepdims=True)
    assert legal.sum() > 1 and np.allclose(lp[legal], ref[legal], atol=1e-4)
    W, b = policy_column(p.net.params)
    assert np.allclose(PlayHead.identity(d.shape[2]).log_policy(d, legal, W, b)[legal], ref[legal], atol=1e-4)
