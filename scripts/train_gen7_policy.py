#!/usr/bin/env python3
"""Train the Gen 7 policy net on the set made by scripts/gen7_build_dataset.py.

  python scripts/train_gen7_policy.py --data data.npz --out run_dir [--kind suit|mlp] [--epochs 8]
                                      [--augment none|cards|all] [--patience 0]
                                      [--fraction 1.0] [--seed 0]

Targets: the card Gen 6 played (policy head), Gen 6's gap for every legal card (gap head),
the holder of each unseen card and the final tricks. Deals are split by family in the data
file; --fraction keeps that share of the training deals, for the learning curve.

--augment relabels the four suits of a training position (card play is the same game under
any relabelling as long as the trump suit moves with it). The auction is not: a 2C response
to 1NT says nothing about clubs. 'cards' therefore blanks the auction of a relabelled
position and leaves --identity of the positions untouched, auction included; 'all' relabels
the auction's suit bids too. Held-out positions are never relabelled.
Writes policy.npz (NumPy weights for bridge_harness.gen7_net.PolicyNet) and metrics.json.
Needs jax and optax; inference needs neither.
"""
import argparse
from itertools import permutations
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.gen7_net import BANK_KEYS, CARD_FEATURES, INPUTS, N_GLOBAL, SEAT_SHOWN, SUIT_INPUT, forward

KINDS = {'mlp': 0, 'suit': 1}
PHASES = ('lead', 'tricks 1-4', 'tricks 5-8', 'tricks 9-13')
PERMS = np.array(list(permutations(range(4))), np.int64)        # PERMS[0] is the identity
CARD_KEYS = ('state', 'order', 'legal', 'gap', 'owner')


def relabel(b, perm, auction='permute'):
    """The same positions with suit perm[i, s] of each moved to suit s (cards are 13 * suit + rank).

    auction: 'permute' moves the suit bids with the suits; 'blank' removes the auction of every
    row whose suits actually moved.
    """
    n = len(perm)
    rows = np.arange(n)
    index = (perm[:, :, None] * 13 + np.arange(13)[None, None, :]).reshape(n, 52)
    out = dict(b)
    for k in CARD_KEYS:
        if k in b:
            out[k] = np.take_along_axis(b[k], index, axis=1)
    if 'card' in b:
        out['card'] = np.argsort(perm, axis=1)[rows, b['card'] // 13] * 13 + b['card'] % 13
    ctx = b['ctx'].copy()
    ctx[:, :4] = np.take_along_axis(b['ctx'][:, :4], perm, axis=1)
    out['ctx'] = ctx
    calls = b['auction'].reshape(n, 4, -1)
    moved = (perm != np.arange(4)).any(axis=1)
    if auction == 'blank':
        calls = np.where(moved[:, None, None], 0, calls).astype(calls.dtype)
    else:
        bids = calls[:, :, 3:].reshape(n, 4, 7, 5)              # strain order C D H S N; suit s is strain 3 - s
        source = np.concatenate([3 - perm[:, ::-1], np.full((n, 1), 4)], axis=1)
        bids = np.take_along_axis(bids, np.broadcast_to(source[:, None, None, :], bids.shape), axis=3)
        calls = np.concatenate([calls[:, :, :3], bids.reshape(n, 4, 35)], axis=2)
    out['auction'] = calls.reshape(n, -1)
    shown = b['shown'].reshape(n, 4, SEAT_SHOWN)                # what the calls show is about suits, so it moves with them
    by_suit = np.take_along_axis(shown[:, :, :16].reshape(n, 4, 4, 4), np.broadcast_to(perm[:, None, None, :], (n, 4, 4, 4)), axis=3)
    out['shown'] = np.concatenate([by_suit.reshape(n, 4, 16), shown[:, :, 16:]], axis=2).reshape(n, -1)
    return out


def init(kind, rng, width):
    def dense(a, b):
        return (rng.standard_normal((a, b)) * np.sqrt(2. / a)).astype(np.float32), np.zeros(b, np.float32)
    g = N_GLOBAL
    p = {}
    if kind == 0:
        sizes = [52 * CARD_FEATURES + g, width, width, width // 2]
        for i in range(3):
            p[f'w{i}'], p[f'b{i}'] = dense(sizes[i], sizes[i + 1])
        p['w_out'], p['b_out'] = dense(sizes[3], 261)
    else:
        e, t = width // 4, width
        p['ws0'], p['bs0'] = dense(SUIT_INPUT, 2 * e)
        p['ws1'], p['bs1'] = dense(2 * e, e)
        p['wt0'], p['bt0'] = dense(4 * e + g, t)
        p['wt1'], p['bt1'] = dense(t, 3 * t // 4)
        p['wd0'], p['bd0'] = dense(e + 3 * t // 4 + 4, 2 * e)
        p['wd1'], p['bd1'] = dense(2 * e, 65)
        p['wk'], p['bk'] = dense(3 * t // 4, 1)
    return p


def phase_of(ply):
    trick = ply // 4 + 1
    return np.where(ply == 0, 0, np.where(trick <= 4, 1, np.where(trick <= 8, 2, 3)))


def evaluate(predict, data, index, batch=4096):
    """Scores of the policy and gap heads against what Gen 6 did, on the rows in `index`."""
    logp, gap_hat = [], []
    for i in range(0, len(index), batch):
        rows = index[i:i + batch]
        out = predict({k: data[k][rows] for k in INPUTS})
        logp.append(np.asarray(out[0]))
        gap_hat.append(np.asarray(out[1]))
    logp, gap_hat = np.concatenate(logp), np.concatenate(gap_hat)
    legal = data['legal'][index]
    gap = data['gap'][index].astype(np.float32)
    meta = data['meta'][index]
    chosen, n = meta[:, 0], len(index)
    rows = np.arange(n)
    pick = logp.argmax(1)
    pick_q = np.where(legal, gap_hat, 1e9).argmin(1)
    tied = legal & (gap <= 1e-9)
    lowest = legal.argmax(1)                                    # the lowest spade, else heart, ...: a fixed dumb rule
    cols = dict(nll=-logp[rows, chosen], uniform_nll=np.log(legal.sum(1)), tie_nll=np.log(tied.sum(1)),
                agree=pick == chosen, in_best=tied[rows, pick], regret=gap[rows, pick], regret_gap_head=gap[rows, pick_q],
                regret_random=(gap * legal).sum(1) / legal.sum(1), regret_lowest=gap[rows, lowest])
    def summary(mask):
        return dict(n=int(mask.sum()), **{k: round(float(v[mask].mean()), 4) for k, v in cols.items()})
    phase = phase_of(meta[:, 3])
    declaring = meta[:, 6] < 2
    return dict(all=summary(np.ones(n, bool)), root_tables=summary(meta[:, 2] == 0),
                by_phase={PHASES[i]: summary(phase == i) for i in range(4) if (phase == i).any()},
                declaring=summary(declaring), defending=summary(~declaring))


def main():
    import jax
    import jax.numpy as jnp
    import optax
    p = argparse.ArgumentParser()
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--kind', choices=list(KINDS), default='suit')
    p.add_argument('--width', type=int, default=512)
    p.add_argument('--epochs', type=int, default=8)
    p.add_argument('--batch', type=int, default=512)
    p.add_argument('--lr', type=float, default=2e-3)
    p.add_argument('--fraction', type=float, default=1.)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--augment', choices=('none', 'cards', 'all'), default='none')
    p.add_argument('--identity', type=float, default=.5, help="with --augment cards: share of positions left as recorded")
    p.add_argument('--patience', type=int, default=0, help='stop after this many epochs without a better held-out loss; 0 = never')
    p.add_argument('--weight-decay', type=float, default=1e-4)
    p.add_argument('--kinds', default='0,1,2', help='table kinds to train on: 0 root tables, 1 tie-fork tables, 2 gap-fork tables')
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    kind = KINDS[a.kind]
    z = np.load(a.data)
    data = {k: z[k] for k in (*INPUTS, 'gap', 'owner', 'meta', 'deal')}
    bank = {k: z[k] for k in BANK_KEYS}
    split = z['deal_split']
    train_deals = np.flatnonzero(split == 0)
    keep = train_deals[:max(1, int(round(len(train_deals) * a.fraction)))]         # deal order is arbitrary but fixed
    kinds = [int(k) for k in a.kinds.split(',')]
    train = np.flatnonzero(np.isin(data['deal'], keep) & np.isin(data['meta'][:, 2], kinds))
    val = np.flatnonzero(split[data['deal']] == 1)
    test = np.flatnonzero(split[data['deal']] == 2)
    rng = np.random.default_rng(a.seed)
    params = {k: jnp.asarray(v) for k, v in init(kind, rng, a.width).items()}
    steps = a.epochs * (len(train) // a.batch)
    schedule = optax.warmup_cosine_decay_schedule(0., a.lr, min(500, steps // 10), steps, a.lr / 50)
    opt = optax.chain(optax.clip_by_global_norm(1.), optax.adamw(schedule, weight_decay=a.weight_decay))
    state = opt.init(params)

    def loss_fn(params, b):
        out = forward(params, b, jnp, kind)
        n = b['legal'].shape[0]
        rows = jnp.arange(n)
        logp = jax.nn.log_softmax(out['policy'])
        ce = -logp[rows, b['card']].mean()
        legal = b['legal'].astype(jnp.float32)
        target = jnp.clip(b['gap'].astype(jnp.float32), 0., 3.)
        gap = (optax.huber_loss(out['gap'], target, delta=1.) * legal).sum() / legal.sum()
        seen = b['owner'] < 0
        owner_logp = jax.nn.log_softmax(out['owner'])
        picked = jnp.take_along_axis(owner_logp, jnp.clip(b['owner'], 0, 2).astype(jnp.int32)[..., None], axis=2)[..., 0]
        owner = -(picked * ~seen).sum() / jnp.maximum((~seen).sum(), 1)
        tricks = ((out['tricks'] - b['tricks'] / 13.) ** 2).mean()
        return ce + 2. * gap + .5 * owner + tricks, (ce, gap, owner, tricks)

    @jax.jit
    def step(params, state, b):
        (loss, parts), grads = jax.value_and_grad(loss_fn, has_aux=True)(params, b)
        updates, state = opt.update(grads, state, params)
        return optax.apply_updates(params, updates), state, loss, parts

    @jax.jit
    def predict(params, b):
        out = forward(params, b, jnp, kind)
        return jax.nn.log_softmax(out['policy']), out['gap']

    def batch_of(rows):
        b = {k: data[k][rows] for k in (*INPUTS, 'gap', 'owner')}
        b['card'] = data['meta'][rows, 0]
        b['tricks'] = data['meta'][rows, 1].astype(np.float32)
        if a.augment == 'all':
            b = relabel(b, PERMS[rng.integers(0, len(PERMS), len(rows))])
        elif a.augment == 'cards':
            pick = np.where(rng.random(len(rows)) < a.identity, 0, rng.integers(1, len(PERMS), len(rows)))
            b = relabel(b, PERMS[pick], auction='blank')
        return b

    history, best, started = [], None, time.time()
    for epoch in range(a.epochs):
        order = rng.permutation(train)
        total = np.zeros(4)
        count = 0
        for i in range(0, len(order) - a.batch + 1, a.batch):
            params, state, loss, parts = step(params, state, batch_of(order[i:i + a.batch]))
            total += np.array([float(x) for x in parts])
            count += 1
        v = evaluate(lambda b: predict(params, b), data, val)
        row = dict(epoch=epoch + 1, seconds=round(time.time() - started), train_ce=round(total[0] / count, 4),
                   train_gap=round(total[1] / count, 4), train_owner=round(total[2] / count, 4), val=v['all'])
        history.append(row)
        print(json.dumps(row), flush=True)
        if best is None or v['all']['nll'] < best[0]:
            best = (v['all']['nll'], epoch + 1, {k: np.asarray(x) for k, x in params.items()})
        elif a.patience and epoch + 1 - best[1] >= a.patience:
            break
    final = {k: jnp.asarray(x) for k, x in best[2].items()}
    exported = dict(best[2], kind=np.array(kind))
    np.savez(a.out / 'policy.npz', **exported, **bank)
    # NumPy inference must agree with the trained graph.
    rows = val[:512]
    b = {k: data[k][rows] for k in INPUTS}
    jax_out = np.asarray(forward(final, b, jnp, kind)['policy'])
    numpy_out = forward(exported, b)['policy']
    parity = float(np.abs(np.where(b['legal'], jax_out - numpy_out, 0.)).max())
    # Does the net use the auction? The same held-out positions with the auction inputs blanked, and with
    # another position's auction in their place. A net that reads the auction must score worse on both.
    held = {k: data[k][val] for k in (*INPUTS, 'gap', 'meta')}
    everyone = np.arange(len(val))
    other = np.random.default_rng(0).permutation(len(val))
    def short(d):
        return {k: {m: v[m] for m in ('nll', 'agree', 'regret')} for k, v in (('all', d['all']), *d['by_phase'].items())}
    auction_use = {
        'real': short(evaluate(lambda b: predict(final, b), held, everyone)),
        'blank': short(evaluate(lambda b: predict(final, b), dict(held, auction=np.zeros_like(held['auction']),
                                                                  shown=np.zeros_like(held['shown'])), everyone)),
        'another_deals': short(evaluate(lambda b: predict(final, b), dict(held, auction=held['auction'][other],
                                                                          shown=held['shown'][other]), everyone)),
        'blank_calls_only': short(evaluate(lambda b: predict(final, b), dict(held, auction=np.zeros_like(held['auction'])), everyone)),
        'blank_shown_only': short(evaluate(lambda b: predict(final, b), dict(held, shown=np.zeros_like(held['shown'])), everyone)),
    }
    metrics = dict(kind=a.kind, width=a.width, kinds=kinds, augment=a.augment, identity=a.identity, weight_decay=a.weight_decay, parameters=int(sum(x.size for x in best[2].values())), epochs=a.epochs,
                   selected_epoch=best[1], fraction=a.fraction, train_deals=int(len(keep)), train_examples=int(len(train)),
                   validation=evaluate(lambda b: predict(final, b), data, val),
                   test=evaluate(lambda b: predict(final, b), data, test) if a.fraction == 1. else None,
                   auction_use=auction_use, numpy_parity_max_abs_logit=parity, seconds=round(time.time() - started), history=history)
    (a.out / 'metrics.json').write_text(json.dumps(metrics, indent=1))
    print(json.dumps(dict(done=str(a.out), selected_epoch=best[1], validation=metrics['validation']['all'], parity=parity,
                          auction_use={k: v['all'] for k, v in auction_use.items()},
                          auction_use_lead={k: v.get('lead') for k, v in auction_use.items()})))


if __name__ == '__main__':
    main()
