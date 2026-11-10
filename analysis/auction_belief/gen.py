import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Free training data for an auction belief model: random deals bid by the frozen bidder.

simulate() runs many auctions in lockstep with the NumPy bidder (greedy, as in the
arena). examples() turns finished auctions into opening-leader training rows.
"""
import sys

import numpy as np

sys.path.insert(0, HERE)
from nbid import NumpyBidder, CARD_FEAT, CARD_HCP, LEN_FEAT, sigmoid  # noqa: E402

VUL_NS = np.array([0, 1, 0, 1])   # index: None, NS, EW, Both
VUL_EW = np.array([0, 0, 1, 1])
VUL_NAMES = ('None', 'NS', 'EW', 'Both')
MAX_SLOTS = 28                    # auction slots aligned to the leader's seat

# all ways to split 13 cards over four suits
COMP = np.array([(a, b, c, 13 - a - b - c) for a in range(14) for b in range(14 - a) for c in range(14 - a - b)], np.int64)
COMP_ID = np.full((14, 14, 14), -1, np.int64)
COMP_ID[COMP[:, 0], COMP[:, 1], COMP[:, 2]] = np.arange(len(COMP))
POP = np.array([bin(i).count('1') for i in range(32)])
HON_HCP = np.array([sum(v for j, v in enumerate((4, 3, 2, 1, 0)) if i >> j & 1) for i in range(32)])
# legal honour subsets: MASKH[available bits, suit length, low cards available, subset]
MASKH = np.zeros((32, 14, 9, 32), bool)
for _a in range(32):
    for _sub in range(32):
        if _sub & ~_a:
            continue
        for _l in range(14):
            for _lo in range(9):
                MASKH[_a, _l, _lo, _sub] = POP[_sub] <= _l and _l - POP[_sub] <= _lo


def deal(rng, n):
    deck = rng.permuted(np.broadcast_to(np.arange(52), (n, 52)), axis=1)
    return deck.reshape(n, 4, 13), rng.integers(0, 4, n), rng.integers(0, 4, n)


def hand_inputs(hands, vul):
    """Bidder hand features for every seat: (B,4,33)."""
    B = len(hands)
    m = np.zeros((B, 4, 52), np.float32)
    np.put_along_axis(m, hands, 1.0, axis=2)
    x = np.empty((B, 4, 33), np.float32)
    x[..., :2] = 1
    ns, ew = VUL_NS[vul], VUL_EW[vul]
    for seat in range(4):
        x[:, seat, 2] = ns if seat % 2 == 0 else ew
        x[:, seat, 3] = ew if seat % 2 == 0 else ns
    x[..., 4] = (m @ CARD_HCP - 10) / 4
    x[..., 5:9] = LEN_FEAT[m.reshape(B, 4, 4, 13).sum(-1).astype(np.int64)]
    x[..., 9:33] = m @ CARD_FEAT
    return x, m


def simulate(bidder, hands, dealer, vul, max_calls=44):
    """Greedy auctions for a batch. Returns dict with calls (-1 padded) and contract fields."""
    B = len(hands)
    x, member = hand_inputs(hands, vul)
    gates = x @ bidder.w_hand                           # (B,4,1024)
    H = np.zeros((B, 4, 3, 256), np.float32)
    Cs = np.zeros((B, 4, 3, 256), np.float32)
    out3 = np.zeros((B, 4, 256), np.float32)
    calls = np.full((B, max_calls), -1, np.int8)
    last4 = np.zeros((B, 4), np.int64)
    last_order = np.full(B, -1)
    last_seat = np.full(B, -1)
    doubled = np.zeros(B, np.int64)
    passes = np.zeros(B, np.int64)
    first = np.full((B, 2, 5), -1)
    active = np.ones(B, bool)
    orders = np.arange(35)
    for t in range(max_calls):
        idx = np.flatnonzero(active)
        if not len(idx):
            break
        seat = (dealer[idx] + t) % 4
        l4 = last4[idx]
        z = gates[idx, seat] + bidder.w_ctx[l4[:, 0]] + bidder.w_ctx[40 + l4[:, 1]] + bidder.w_ctx[80 + l4[:, 2]] + bidder.w_ctx[120 + l4[:, 3]]
        inp = None
        for layer, ((w, u, b), (scale, shift)) in enumerate(zip(bidder.lstm, bidder.bn)):
            if layer:
                z = inp @ w
            h, c = H[idx, seat, layer], Cs[idx, seat, layer]
            z = z + b + h @ u
            i, f, g, o = sigmoid(z[:, :256]), sigmoid(z[:, 256:512]), np.tanh(z[:, 512:768]), sigmoid(z[:, 768:])
            c2 = f * c + i * g
            h2 = o * np.tanh(c2)
            H[idx, seat, layer], Cs[idx, seat, layer] = h2, c2
            inp = h2 * scale + shift
        out3[idx, seat] = inp
        logits = inp @ bidder.wd + bidder.bd
        legal = np.zeros((len(idx), 40), bool)
        legal[:, 2] = True
        lo, ls, db = last_order[idx], last_seat[idx], doubled[idx]
        legal[:, 5:] = orders[None, :] > lo[:, None]
        legal[:, 3] = (lo >= 0) & (db == 0) & (seat % 2 != ls % 2)
        legal[:, 4] = (db == 1) & (seat % 2 == ls % 2)
        call = np.argmax(np.where(legal, logits, -np.inf), axis=1)
        calls[idx, t] = call
        bid = call >= 5
        order = call - 5
        b_idx = idx[bid]
        last_order[b_idx] = order[bid]
        last_seat[b_idx] = seat[bid]
        doubled[b_idx] = 0
        side, strain = seat[bid] % 2, order[bid] % 5
        new = first[b_idx, side, strain] < 0
        first[b_idx[new], side[new], strain[new]] = seat[bid][new]
        passes[idx] = np.where(call == 2, passes[idx] + 1, 0)
        doubled[idx[call == 3]] = 1
        doubled[idx[call == 4]] = 2
        last4[idx] = np.concatenate([l4[:, 1:], call[:, None]], axis=1)
        ended = ((passes[idx] >= 3) & (last_order[idx] >= 0)) | ((passes[idx] >= 4) & (last_order[idx] < 0))
        active[idx[ended]] = False
    finished = ~active
    has = finished & (last_order >= 0)
    declarer = np.full(B, -1)
    ix = np.flatnonzero(has)
    declarer[ix] = first[ix, last_seat[ix] % 2, last_order[ix] % 5]
    return dict(calls=calls, length=(calls >= 0).sum(1), finished=finished, contract=has, last_order=last_order,
                doubled=doubled, declarer=declarer, out3=out3, member=member)


def types(member):
    """Hand types from membership (..., 52): suit lengths (...,4), honour bits (...,4), low counts (...,4)."""
    m = member.reshape(*member.shape[:-1], 4, 13)
    length = m.sum(-1).astype(np.int64)
    hon = sum((m[..., 12 - j] > 0).astype(np.int64) << j for j in range(5))
    return length, hon, length - POP[hon]


def examples(sim, hands, dealer, vul):
    """Opening-leader rows for deals that reached a contract within the slot limit."""
    keep = np.flatnonzero(sim['contract'] & ((sim['length'] + 3) <= MAX_SLOTS))
    dec = sim['declarer'][keep]
    leader = (dec + 1) % 4
    member = sim['member'][keep]
    ar = np.arange(len(keep))
    own = member[ar, leader]
    L_len, L_hon, L_low = types(own)
    D_len, D_hon, D_low = types(member[ar, dec])
    M_len, M_hon, M_low = types(member[ar, (leader + 1) % 4])
    P_len, P_hon, P_low = types(member[ar, (leader + 2) % 4])
    v = vul[keep]
    own_vul = np.where(leader % 2 == 0, VUL_NS[v], VUL_EW[v])
    opp_vul = np.where(leader % 2 == 0, VUL_EW[v], VUL_NS[v])
    xh = np.concatenate([own, own @ CARD_FEAT, ((own @ CARD_HCP - 10) / 4)[:, None], LEN_FEAT[L_len],
                         own_vul[:, None], opp_vul[:, None]], axis=1).astype(np.float32)
    calls = sim['calls'][keep].astype(np.int64)
    d0 = (dealer[keep] - leader) % 4
    slots = np.full((len(keep), MAX_SLOTS), MAX_SLOTS * 38, np.int64)        # dummy index = zero row
    T = calls.shape[1]
    pos = d0[:, None] + np.arange(T)[None, :]
    valid = (calls >= 0) & (pos < MAX_SLOTS)
    r, c = np.nonzero(valid)
    slots[r, pos[r, c]] = pos[r, c] * 38 + (calls[r, c] - 2)
    return dict(xh=xh, slots=slots, state=sim['out3'][keep][ar, leader].astype(np.float16),
                n=(13 - L_len), avail=(31 - L_hon), low=(8 - L_low),
                D_len=D_len, D_hon=D_hon, M_len=M_len, M_hon=M_hon,
                P_low=P_low, D_low=D_low, M_low=M_low, index=keep)


if __name__ == '__main__':
    import time
    bidder = NumpyBidder(FEED + '/artifacts/v5/bidder.keras')
    rng = np.random.default_rng(int(sys.argv[2]))
    out, total, chunk = sys.argv[1], int(sys.argv[3]), 4096
    parts, n, t0, passed, dropped = [], 0, time.time(), 0, 0
    while n < total:
        hands, dealer, vul = deal(rng, chunk)
        sim = simulate(bidder, hands, dealer, vul)
        ex = examples(sim, hands, dealer, vul)
        passed += int((sim['finished'] & ~sim['contract']).sum())
        dropped += int(sim['contract'].sum()) - len(ex['xh'])
        del ex['index']
        parts.append(ex)
        n += len(ex['xh'])
    data = {k: np.concatenate([p[k] for p in parts])[:total] for k in parts[0]}
    for k in ('n', 'avail', 'low', 'D_len', 'D_hon', 'M_len', 'M_hon', 'P_low', 'D_low', 'M_low'):
        data[k] = data[k].astype(np.int8)
    data['slots'] = data['slots'].astype(np.int16)
    data['xh'] = data['xh'].astype(np.float16)
    np.savez(out, **data)
    print(f'{out}: {total} rows in {time.time()-t0:.0f}s ({total/(time.time()-t0):.0f}/s); passed out {passed}, too long {dropped}')
