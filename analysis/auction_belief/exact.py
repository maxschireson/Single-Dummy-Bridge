import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Exact sampling of hidden hands given per-seat consistency tests.

Target: the uniform distribution over ways to split `unknown` into three hidden
hands such that check[s](hand_s) is true for every hidden seat s. In the arena's
common-auction condition every seat bids greedily with one known network, so
this is the exact posterior over layouts given the auction and the observer's
own hand.

Method: rejection from uniform proposals, with one refinement for tight
auctions. Round 0 is plain rejection (block seat tested first). If that has not
produced enough layouts once K block hands have passed their own test, those K
block hands are kept and further uniform completions of each are tried, the
number doubling each round. Every proposal (block hand uniform among consistent
block hands, completion uniform) is marginally uniform over layouts whose block
hand is consistent, so every accepted layout is marginally exact. Layouts that
share a block hand are dependent; K is a multiple of the target so that sharing
is rare, and the count of distinct block hands is reported.
"""
import numpy as np


def _perms(rng, cards, m):
    return rng.permuted(np.broadcast_to(np.asarray(cards), (m, len(cards))), axis=1)


def exact_posterior(unknown, checks, n_target, rng, sizes=(13, 13, 13), k_mult=8,
                    pilot=2048, batch=8192, max_block_checks=600_000,
                    max_total_checks=2_000_000):
    unknown = np.asarray(unknown)
    a, b, c = sizes
    assert len(unknown) == a + b + c and len(checks) == 3
    stats = dict(checks=0, proposals=0, rounds=0, capped=False, block_proposals=0, completions=0, completion_successes=0)

    def split(perm, order):
        """perm rows hold the cards in slot order given by `order` (block first)."""
        out = [None] * 3
        offset = 0
        for slot in order:
            out[slot] = perm[:, offset:offset + sizes[slot]]
            offset += sizes[slot]
        return out

    def run(slot, hands):
        stats['checks'] += len(hands)
        return checks[slot](hands)

    # Pilot: every seat tested on every proposal, giving marginal acceptance rates
    # and (as plain rejection) exact independent layouts.
    perm = _perms(rng, unknown, pilot)
    hands = split(perm, (0, 1, 2))
    ok = [run(s, hands[s]) for s in range(3)]
    stats['proposals'] += pilot
    p = [max(o.mean(), 0.5 / pilot) for o in ok]
    stats['p_seat'] = [float(o.mean()) for o in ok]
    good = ok[0] & ok[1] & ok[2]
    found = [np.stack([hands[s][good] for s in range(3)], axis=1)]
    block_ids = [np.full(int(good.sum()), -1)]
    n_found = int(good.sum())
    stats['pilot_accept'] = float(good.mean())
    K = k_mult * n_target

    def cost(block):
        others = [s for s in range(3) if s != block]
        return K / p[block] + n_target / (p[others[0]] * p[others[1]])
    block = min(range(3), key=cost)
    others = sorted((s for s in range(3) if s != block), key=lambda s: p[s])
    order = (block, *others)
    stats['block_slot'] = block

    # Round 0: plain rejection, block seat first.
    pool_block, pool_rest = [], []
    n_pool = 0
    block_checks = 0
    while n_found < n_target and n_pool < K:
        if block_checks >= max_block_checks or stats['checks'] >= max_total_checks:
            stats['capped'] = True
            break
        perm = _perms(rng, unknown, batch)
        stats['proposals'] += batch
        hb = perm[:, :sizes[block]]
        okb = run(block, hb)
        block_checks += batch
        stats['block_proposals'] += batch
        if not okb.any():
            continue
        perm = perm[okb]
        ids = n_pool + np.arange(len(perm))
        pool_block.append(perm[:, :sizes[block]])
        pool_rest.append(perm[:, sizes[block]:])
        n_pool += len(perm)
        hs = split(perm, order)
        alive = np.ones(len(perm), bool)
        for s in others:
            idx = np.flatnonzero(alive)
            if not len(idx):
                break
            alive[idx] = run(s, hs[s][idx])
        stats['completions'] += len(perm)
        stats['completion_successes'] += int(alive.sum())
        if alive.any():
            found.append(np.stack([hs[s][alive] for s in range(3)], axis=1))
            block_ids.append(ids[alive])
            n_found += int(alive.sum())
    stats['block_pool'] = n_pool

    # Later rounds: more uniform completions of the retained block hands.
    if n_found < n_target and n_pool > 0:
        pb = np.concatenate(pool_block)
        pr = np.concatenate(pool_rest)
        ids_all = np.arange(n_pool)
        extra = 1
        while n_found < n_target:
            if stats['checks'] >= max_total_checks:
                stats['capped'] = True
                break
            stats['rounds'] += 1
            for _ in range(extra):
                for start in range(0, n_pool, batch):
                    rest = rng.permuted(pr[start:start + batch], axis=1)
                    hb = pb[start:start + batch]
                    perm = np.concatenate([hb, rest], axis=1)
                    stats['proposals'] += len(perm)
                    hs = split(perm, order)
                    alive = np.ones(len(perm), bool)
                    for s in others:
                        idx = np.flatnonzero(alive)
                        if not len(idx):
                            break
                        alive[idx] = run(s, hs[s][idx])
                    stats['completions'] += len(perm)
                    stats['completion_successes'] += int(alive.sum())
                    if alive.any():
                        found.append(np.stack([hs[s][alive] for s in range(3)], axis=1))
                        block_ids.append(ids_all[start:start + batch][alive])
                        n_found += int(alive.sum())
            extra *= 2

    layouts = np.concatenate(found) if found else np.zeros((0, 3, max(sizes)), int)
    ids = np.concatenate(block_ids)
    stats['found'] = len(layouts)
    if len(layouts) > n_target:
        keep = rng.permutation(len(layouts))[:n_target]
        layouts, ids = layouts[keep], ids[keep]
    else:
        keep = rng.permutation(len(layouts))
        layouts, ids = layouts[keep], ids[keep]
    shared = ids[ids >= 0]
    stats['distinct_blocks'] = int(len(set(shared.tolist())) + (ids < 0).sum())
    stats['returned'] = len(layouts)
    return layouts, stats
