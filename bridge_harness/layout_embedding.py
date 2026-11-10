"""Decision-relevant layout geometry, trained from within-position DDS contrasts.

Belief probabilities are inputs to the reducer, not invented by the encoder.
The initial encoder uses solver state and visibility. It does not consume DDS
answers at inference, or claim to model public-history likelihoods.
"""
import numpy as np
from .dds_value import encode as encode_dds

INPUT_SIZE = 445
EMBEDDING_SIZE = 16


def encode(raw, fixed, legal, suit_order=None):
    raw = np.asarray(raw, np.uint8).reshape(-1, 37)
    x, remaining, cards = encode_dds(raw, suit_order)
    actor = (raw[:, 1].astype(int) + (raw[:, 2:5] != 255).sum(1)) % 4
    seats = (actor[:, None] + np.arange(4)) % 4
    visibility = np.take_along_axis(np.asarray(fixed, np.float32), seats, 1)
    legal = np.asarray(legal, np.float32)[:, cards]
    lengths = x[:, :208].reshape(-1, 4, 4, 13).sum(-1).reshape(-1, 16) / 13
    return np.concatenate([x, visibility, legal, lengths], 1), cards


def make_model():
    import torch
    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.encoder = torch.nn.Sequential(
                torch.nn.Linear(INPUT_SIZE, 256), torch.nn.ReLU(),
                torch.nn.Linear(256, 128), torch.nn.ReLU(),
                torch.nn.Linear(128, EMBEDDING_SIZE))
            self.head = torch.nn.Linear(EMBEDDING_SIZE, 52)

        def forward(self, x):
            z = self.encoder(x)
            return z, self.head(z)
    return Model()


def centered(values, legal):
    legal = np.asarray(legal, bool)
    values = np.asarray(values, np.float32)
    return (values - (values * legal).sum(-1, keepdims=True) /
            legal.sum(-1, keepdims=True).clip(1)) * legal


def reduce_layouts(embedding, weights, budget, rng=None):
    """Greedy weighted medoids, optionally random representatives per cluster.

    With rng, each representative is drawn proportional to input mass in its
    cluster. Cluster weights preserve the full finite-pool average in expectation
    for any value vector, independently of the quality of the learned embedding.
    Deterministic medoids are an approximation. Weights must already represent
    the sampling/probability convention intended by the caller.
    """
    z = np.asarray(embedding, np.float64)
    w = np.asarray(weights, np.float64)
    if z.ndim != 2 or w.shape != (len(z),) or not 1 <= budget <= len(z):
        raise ValueError('Invalid embedding, masses or budget')
    if not np.isfinite(z).all() or not np.isfinite(w).all() or (w < 0).any() or w.sum() <= 0:
        raise ValueError('Nonfinite embedding or invalid probability mass')
    w = w / w.sum()
    dist = np.maximum((z*z).sum(1)[:, None] + (z*z).sum(1)[None, :] - 2*z@z.T, 0)
    first = int(np.argmin(w @ dist))
    chosen = [first]
    nearest = dist[:, first].copy()
    for _ in range(1, budget):
        gains = (w[:, None] * (nearest[:, None] - np.minimum(nearest[:, None], dist))).sum(0)
        gains[chosen] = -np.inf
        nxt = int(np.argmax(gains))
        chosen.append(nxt)
        nearest = np.minimum(nearest, dist[:, nxt])
    assignments = np.argmin(dist[:, chosen], axis=1)
    # Give each chosen point its own cluster even in exact-distance ties.
    assignments[np.asarray(chosen)] = np.arange(len(chosen))
    representatives, masses = [], []
    for j, medoid in enumerate(chosen):
        members = np.flatnonzero(assignments == j)
        mass = float(w[members].sum())
        if rng is not None and mass > 0:
            medoid = int(rng.choice(members, p=w[members]/mass))
        representatives.append(medoid)
        masses.append(mass)
    return np.asarray(representatives), np.asarray(masses)


def export_numpy(model, path):
    arrays = {k: v.detach().cpu().numpy() for k, v in model.state_dict().items()}
    np.savez_compressed(path, **arrays)


class Weights:
    def __init__(self, path):
        with np.load(path, allow_pickle=False) as data:
            self.w = {k: data[k] for k in data.files}

    def predict(self, raw, fixed, legal):
        x, _ = encode(raw, fixed, legal)
        for i in (0, 2, 4):
            x = x @ self.w[f'encoder.{i}.weight'].T + self.w[f'encoder.{i}.bias']
            if i != 4:
                x = np.maximum(x, 0)
        return x
