"""Size-study helpers; do not alter frozen player/trainer implementations."""
import hashlib
from pathlib import Path
import numpy as np

INPUTS = ('state', 'calls', 'seats', 'play')
FIELDS = (*INPUTS, 'owner_target', 'owner_loss_mask', 'support', 'kind', 'split_group')
PLAY_SIZE = 523
SCHEMA = 'auction-and-public-play-belief-size-study-v1'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def load(path):
    with np.load(path, allow_pickle=False) as z:
        d = {k: z[k] for k in FIELDS}
    y, m = d['owner_target'], d['owner_loss_mask']
    if not np.all((y >= 0) & (y < 4)) or not np.all(d['support'][np.arange(len(y))[:,None], np.arange(52), y] | ~m):
        raise ValueError('Invalid ownership labels/mask')
    if np.any(m & (d['support'].sum(-1) < 2)):
        raise ValueError('Loss must exclude known or forced owners')
    return d


def batch(d, ix):
    x = {k: d[k][ix] for k in INPUTS}
    y, m = d['owner_target'][ix].astype(np.int32), d['owner_loss_mask'][ix].astype(np.float32)
    return x, y, m, d['support'][ix]


def encode_play(observation):
    """Public pre-action information only. Relative seats; suits never permuted.

    A per-card play position plus relative player retains the full ordered history.
    Own original hand and public auction enter through the existing auction encoder.
    """
    from dataclasses import asdict
    from .training import input_tensors
    from .auction_belief import encode_auction
    o = observation
    a = input_tensors(asdict(o))
    observer = o.controller
    order = (np.arange(4) + observer) % 4
    positions = np.zeros(52, np.float32)
    for i, (_, c) in enumerate(o.history):
        positions[c] = (i + 1) / 52
    c = o.contract
    eye = np.eye(4, dtype=np.float32)
    play = np.concatenate([a['known'][order].ravel(), a['played'][order].ravel(), positions,
        a['voids'][order].ravel(), a['remaining_counts'][order]/13, a['visible'][order],
        eye[(o.actor-observer)%4], eye[(o.leader-observer)%4], eye[(c.declarer-observer)%4],
        np.eye(5)['SHDCN'.index(c.strain)], np.eye(8)[c.level], np.eye(3)[c.doubled],
        [o.declarer_tricks/13, len(o.history)/52, 1]]).astype(np.float32)
    if play.shape != (PLAY_SIZE,):
        raise ValueError(f'Wrong play encoding: {play.shape}')
    x, _ = encode_auction(o.original_hand(observer), observer, o.dealer, o.vulnerability, o.auction)
    return dict(**x, play=play), a['owner_support'][:, order]


def add_empty_play(d):
    """Auction-only rows have no invented play trajectory."""
    y = d['owner_target']
    support = np.ones((*y.shape, 4), bool)
    support[:, :, 0] = False
    support[d['state'][:, :52].astype(bool)] = [True, False, False, False]
    return {**d, 'play': np.zeros((len(y), PLAY_SIZE), np.float32), 'support': support}


def widen(weights, widths, seed=2026110902):
    """Function-preserving widening, with balanced copies and no test access.

    Replicate incoming units and divide their outgoing weights by multiplicity.
    Independent dropout during fitting breaks symmetry between copied units.
    """
    ce, se, w0, b0, w1, b1, w2, b2 = [w.copy() for w in weights]
    n0, n1 = widths
    if n0 < len(b0) or n1 < len(b1):
        raise ValueError('Widening cannot shrink the parent')
    rng = np.random.default_rng(seed)
    a = np.concatenate([np.arange(len(b0)), np.resize(rng.permutation(len(b0)), n0-len(b0))])
    b = np.concatenate([np.arange(len(b1)), np.resize(rng.permutation(len(b1)), n1-len(b1))])
    count_a, count_b = np.bincount(a), np.bincount(b)
    # Existing auction weights get zero weights for the new public-play inputs.
    if w0.shape[0] == 448:
        w0 = np.concatenate([w0, np.zeros((PLAY_SIZE, w0.shape[1]), w0.dtype)])
    outgoing=(w2[b] / count_b[b, None]).astype(w2.dtype)
    # Zero-sum perturbations preserve the function while giving replicated
    # second-layer units different gradients (there is no dropout after them).
    noise=rng.normal(0,1e-4,outgoing.shape)
    for j in range(len(b1)):
        ix=np.flatnonzero(b==j);noise[ix]-=noise[ix].mean(axis=0)
    if n1>len(b1):
        outgoing+=noise.astype(w2.dtype)
    return [ce, se, w0[:, a], b0[a],
            (w1[a][:, b] / count_a[a, None]).astype(w1.dtype), b1[b],outgoing,b2]


def make_model(widths):
    import tensorflow as tf
    from .auction_belief import MAX_CALLS, CALLS
    k = tf.keras
    state = k.Input((64,), name='state')
    calls = k.Input((MAX_CALLS,), dtype='int32', name='calls')
    seats = k.Input((MAX_CALLS,), dtype='int32', name='seats')
    play = k.Input((PLAY_SIZE,), name='play')
    c = k.layers.Flatten()(k.layers.Embedding(len(CALLS)+1, 4)(calls))
    s = k.layers.Flatten()(k.layers.Embedding(5, 2)(seats))
    x = k.layers.Concatenate()([state, c, s, play])
    x = k.layers.Dense(widths[0], activation='relu')(x)
    x = k.layers.Dropout(.15)(x)
    x = k.layers.Dense(widths[1], activation='relu')(x)
    x = k.layers.Dense(208)(x)
    return k.Model(dict(state=state, calls=calls, seats=seats, play=play), k.layers.Reshape((52, 4))(x))


def score(metrics):
    """Predeclared score: half public play, one quarter per auction source."""
    return (.5*metrics['play']['all']['nll'] + .25*metrics['bidding']['complete_auction']['nll']
            + .25*metrics['ben']['complete_auction']['nll'])


class Weights:
    def __init__(self, path):
        with np.load(path, allow_pickle=False) as z:
            self.weights = [z[f'w{i}'] for i in range(8)]

    def predict(self, x):
        ce,se,w0,b0,w1,b1,w2,b2 = self.weights
        n = len(x['state'])
        h = np.concatenate([x['state'], ce[x['calls']].reshape(n,-1),
                            se[x['seats']].reshape(n,-1), x['play']],axis=1)
        return (np.maximum(np.maximum(h@w0+b0,0)@w1+b1,0)@w2+b2).reshape(n,52,4)

    def logits(self, observation):
        x, _ = encode_play(observation)
        relative = self.predict({k:v[None] for k,v in x.items()})[0]
        return relative[:,[(s-observation.controller)%4 for s in range(4)]]
