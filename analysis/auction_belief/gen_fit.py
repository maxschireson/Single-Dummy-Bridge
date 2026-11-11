import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Training data for a hand-fit scorer: does this hand fit this seat's calls?

Random deals are bid by the frozen bidder. For every seat the true hand is a positive example;
alternative hands (some random, some the true hand with a few cards swapped) are labelled by
replaying the seat's calls with the alternative hand. Stored compactly: per deal the calls,
dealer and vulnerability; per example the deal, seat, hand type and label.

Usage: python gen_fit.py OUT.npz SEED DEALS
"""
import os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nbid import NumpyBidder, CARD_FEAT, CARD_HCP, LEN_FEAT, sigmoid
from gen import deal, simulate, types, VUL_NS, VUL_EW, MAX_SLOTS

K_RAND, K_NEAR = 3, 5
ROOT = FEED


def alternatives(rng, hands):
    """(B,4,13) true hands -> (B,4,K,13) alternative hands."""
    B = len(hands)
    K = K_RAND + K_NEAR
    out = np.empty((B, 4, K, 13), np.int64)
    out[:, :, :K_RAND] = np.argsort(rng.random((B, 4, K_RAND, 52)), axis=-1)[..., :13]
    member = np.zeros((B, 4, 52), bool)
    np.put_along_axis(member, hands, True, axis=2)
    for k in range(K_NEAR):
        m = rng.integers(1, 9, (B, 4))                               # cards to swap
        keys_in = rng.random((B, 4, 52)) + (~member) * 10            # true cards first, in random order
        order_in = np.argsort(keys_in, axis=-1)[..., :13]            # the hand, shuffled
        keys_out = rng.random((B, 4, 52)) + member * 10              # other cards first, in random order
        order_out = np.argsort(keys_out, axis=-1)[..., :13]
        take_new = np.arange(13)[None, None, :] < m[..., None]
        out[:, :, K_RAND + k] = np.where(take_new, order_out, order_in)
    return out


def label(bidder, alt, sim, dealer, vul):
    """Replay each seat's calls with each alternative hand; True where every call matches."""
    B, _, K, _ = alt.shape
    N = B * 4 * K
    hands = alt.reshape(N, 13)
    d = np.repeat(np.arange(B), 4 * K)
    seat = np.tile(np.repeat(np.arange(4), K), B)
    m = np.zeros((N, 52), np.float32)
    np.put_along_axis(m, hands, 1.0, axis=1)
    x = np.empty((N, 33), np.float32)
    x[:, :2] = 1
    ns, ew = VUL_NS[vul][d], VUL_EW[vul][d]
    x[:, 2] = np.where(seat % 2 == 0, ns, ew)
    x[:, 3] = np.where(seat % 2 == 0, ew, ns)
    x[:, 4] = (m @ CARD_HCP - 10) / 4
    x[:, 5:9] = LEN_FEAT[m.reshape(N, 4, 13).sum(-1).astype(np.int64)]
    x[:, 9:33] = m @ CARD_FEAT
    gates = x @ bidder.w_hand
    calls = sim['calls'].astype(np.int64)
    length = sim['length']
    first = (seat - dealer[d]) % 4
    alive = np.ones(N, bool)
    H = np.zeros((N, 3, 256), np.float32)
    C = np.zeros((N, 3, 256), np.float32)
    for j in range(12):
        i = first + 4 * j
        idx = np.flatnonzero(alive & (i < length[d]))
        if not len(idx):
            break
        ii, dd = i[idx], d[idx]
        z = gates[idx].copy()
        for back in range(4):
            pos = ii - 4 + back
            tok = np.where(pos >= 0, calls[dd, np.maximum(pos, 0)], 0)
            z += bidder.w_ctx[40 * back + tok]
        inp = None
        for layer, ((w, u, b), (scale, shift)) in enumerate(zip(bidder.lstm, bidder.bn)):
            if layer:
                z = inp @ w
            h, c = H[idx, layer], C[idx, layer]
            z = z + b + h @ u
            ig, fg, g, og = sigmoid(z[:, :256]), sigmoid(z[:, 256:512]), np.tanh(z[:, 512:768]), sigmoid(z[:, 768:])
            c2 = fg * c + ig * g
            h2 = og * np.tanh(c2)
            H[idx, layer], C[idx, layer] = h2, c2
            inp = h2 * scale + shift
        logits = inp @ bidder.wd + bidder.bd
        call = np.argmax(np.where(sim['legal'][dd, ii], logits, -np.inf), axis=1)
        alive[idx[call != calls[dd, ii]]] = False
    return alive.reshape(B, 4, K)


def main():
    out, seed, total = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    bidder = NumpyBidder(ROOT + '/artifacts/v5/bidder.keras')
    rng = np.random.default_rng(seed)
    chunk, K = 768, K_RAND + K_NEAR
    D = dict(calls=[], dealer=[], vul=[])
    E = dict(deal=[], seat=[], length=[], hon=[], label=[], kind=[])
    n_deals, t0 = 0, time.time()
    while n_deals < total:
        hands, dealer, vul = deal(rng, chunk)
        sim = simulate(bidder, hands, dealer, vul, keep_legal=True)
        keep = np.flatnonzero(sim['contract'] & ((sim['length'] + 3) <= MAX_SLOTS))
        alt = alternatives(rng, hands)
        lab = label(bidder, alt, sim, dealer, vul)
        true_ok = label(bidder, hands[:, :, None, :], sim, dealer, vul)
        assert true_ok[keep].all(), 'true hands must reproduce their own calls'
        allh = np.concatenate([hands[:, :, None, :], alt], axis=2)[keep]          # (b,4,1+K,13)
        labels = np.concatenate([np.ones((len(keep), 4, 1), bool), lab[keep]], axis=2)
        b = len(keep)
        mem = np.zeros((b, 4, 1 + K, 52), np.float32)
        np.put_along_axis(mem, allh, 1.0, axis=3)
        ln, hon, _ = types(mem)
        D['calls'].append(sim['calls'][keep][:, :MAX_SLOTS]); D['dealer'].append(dealer[keep].astype(np.int8)); D['vul'].append(vul[keep].astype(np.int8))
        E['deal'].append(np.repeat(n_deals + np.arange(b), 4 * (1 + K)).astype(np.int32))
        E['seat'].append(np.tile(np.repeat(np.arange(4), 1 + K), b).astype(np.int8))
        E['length'].append(ln.reshape(-1, 4).astype(np.int8)); E['hon'].append(hon.reshape(-1, 4).astype(np.int8))
        E['label'].append(labels.reshape(-1))
        E['kind'].append(np.tile(np.array([0] + [1] * K_RAND + [2] * K_NEAR, np.int8), b * 4))
        n_deals += b
    data = {('d_' + k): np.concatenate(v) for k, v in D.items()}
    data.update({k: np.concatenate(v) for k, v in E.items()})
    np.savez(out, **data)
    lab, kind = data['label'], data['kind']
    print(f'{out}: {n_deals} deals, {len(lab)} examples in {time.time()-t0:.0f}s ({n_deals/(time.time()-t0):.0f} deals/s); '
          f'positive share: random hands {lab[kind==1].mean():.3f}, near hands {lab[kind==2].mean():.3f}')


if __name__ == '__main__':
    main()
