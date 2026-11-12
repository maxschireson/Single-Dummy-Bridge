"""Cheap suit-shape and honor-strength geometry for candidate layouts.

Each unknown player contributes four suit lengths and four honor-strength sums.
K/Q swaps change strength slightly; K/spot swaps change it more. Known hands are
masked before cosine normalization so common visible cards do not dominate it.
These are coarse attributes, not claims of exact DDS equivalence.
"""
import numpy as np


# Rank order is 2 .. A. Ten has a small weight to distinguish it from low spots.
HONOR_WEIGHTS = np.array([0.] * 8 + [.5, 1., 2., 3., 4.], np.float32)


def components(raw, fixed):
    """Return (n, 16) shape and strength arrays, in actor-relative seat order."""
    raw = np.asarray(raw, np.uint8).reshape(-1, 37)
    fixed = np.asarray(fixed, bool)
    if fixed.shape != (len(raw), 4):
        raise ValueError('Expected one visibility mask per layout')
    words = raw[:, 5:].copy().view('<u2').reshape(-1, 4, 4)
    cards = ((words[..., None] >> np.arange(2, 15)) & 1).astype(np.float32)
    actor = (raw[:, 1].astype(int) + (raw[:, 2:5] != 255).sum(1)) % 4
    seats = (actor[:, None] + np.arange(4)) % 4
    cards = cards[np.arange(len(raw))[:, None], seats]
    unknown = ~np.take_along_axis(fixed, seats, axis=1)
    cards *= unknown[:, :, None, None]
    return cards.sum(-1).reshape(-1, 16), (cards @ HONOR_WEIGHTS).reshape(-1, 16)


def combine(shape, strength, weights=(1., 1.), cosine=False):
    """Squared Euclidean distance uses two nonnegative block coefficients.

    With cosine=True, squared distance of these unit vectors is twice cosine
    distance. No DDS answers or neural model are needed at selection time.
    """
    weights = np.asarray(weights, np.float64)
    if weights.shape != (2,) or not np.isfinite(weights).all() or (weights < 0).any():
        raise ValueError('Expected two finite nonnegative weights')
    z = np.concatenate([shape * np.sqrt(weights[0]), strength * np.sqrt(weights[1])], axis=1)
    if cosine:
        z /= np.maximum(np.linalg.norm(z, axis=1, keepdims=True), 1e-12)
    return z


def encode(raw, fixed, weights=(1., 1.), cosine=False):
    return combine(*components(raw, fixed), weights=weights, cosine=cosine)
