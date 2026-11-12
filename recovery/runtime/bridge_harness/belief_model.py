"""Small play-only ownership model. Privileged labels are never encoder inputs.

TensorFlow is optional and imported only when building/loading the model.
V1 deliberately excludes synthetic auctions. A later bidding-aware encoder must
use real auction prefixes and a new schema; old trajectories cannot be relabelled
with unrelated BEN auctions.
"""
import numpy as np

INPUT_KEYS = ("known", "played", "visible", "voids", "remaining_counts",
              "context", "history_cards", "history_seats", "owner_support")
CONTEXT_CATEGORIES = (4, 4, 4, 4, 5, 8, 3, 4, 4)
ENCODER_VERSION = "play-observation-v1"


def encode_inputs(arrays):
    """Explicit observation-only whitelist, with ordered history retained."""
    a = {k: np.asarray(arrays[k]) for k in INPUT_KEYS}
    n = len(a["context"])
    parts = [a[k].reshape(n, -1).astype(np.float32)
             for k in ("known", "played", "visible", "voids")]
    parts.append(a["remaining_counts"].astype(np.float32) / 13)
    for i, size in enumerate(CONTEXT_CATEGORIES):
        values = a["context"][:, i]
        if np.any((values < 0) | (values >= size)):
            raise ValueError(f"Invalid context field {i}")
        parts.append(np.eye(size, dtype=np.float32)[values])
    parts.append(a["context"][:, 9:].astype(np.float32) / np.array([13, 52], np.float32))
    return dict(state=np.concatenate(parts, axis=1),
                cards=a["history_cards"].astype(np.int32),
                seats=a["history_seats"].astype(np.int32))


def masked_probabilities(logits, support):
    """Zero for impossible ownership; played cards have all-zero output."""
    x = np.where(support, logits, -1e9)
    e = np.exp(x - x.max(axis=-1, keepdims=True)) * support
    return e / np.maximum(e.sum(axis=-1, keepdims=True), 1e-30)


def capacity_prior(support, remaining_counts, iterations=40):
    """Iteratively balance support and seat capacities (approximate marginals).

    This is a diagnostic baseline, not exact uniform feasible-deal sampling.
    Known cards are included as singleton rows and consume their seat capacity.
    """
    p = support.astype(np.float32)
    target = remaining_counts.astype(np.float32)
    for _ in range(iterations):
        p *= (target / np.maximum(p.sum(axis=1), 1e-20))[:, None, :]
        p /= np.maximum(p.sum(axis=2, keepdims=True), 1e-20)
    return p


def permute_observation(a, rotation, suit_order):
    """Observation-only symmetry: suit_order gives old suit at each new suit.

    Safe for play-only data. Bidding conventions need their own transformation
    rules, so this must not be applied blindly to real auction training.
    """
    b = {k: np.array(a[k], copy=True) for k in INPUT_KEYS}
    seats = (np.arange(4) - rotation) % 4
    cards = np.concatenate([np.arange(s * 13, s * 13 + 13) for s in suit_order])
    inverse = np.argsort(cards)
    for k in ("known", "played"):
        b[k] = b[k][:, seats][:, :, cards]
    for k in ("visible", "remaining_counts"):
        b[k] = b[k][:, seats]
    b["voids"] = b["voids"][:, seats][:, :, suit_order]
    b["owner_support"] = b["owner_support"][:, cards][:, :, seats]
    b["history_cards"] = np.r_[inverse, 52][b["history_cards"]]
    hs = b["history_seats"]
    b["history_seats"] = np.where(hs < 4, (hs + rotation) % 4, 4)
    ct = b["context"]
    for i in (0, 1, 2, 3, 7): ct[:, i] = (ct[:, i] + rotation) % 4
    ct[:, 4] = np.r_[np.argsort(suit_order), 4][ct[:, 4]]
    if rotation % 2:
        ct[:, 8] = np.array([0, 2, 1, 3])[ct[:, 8]]
    return b, cards, seats


def build_model(state_size, width=80, zero_output=False):
    import tensorflow as tf
    k = tf.keras
    state = k.Input((state_size,), name="state")
    cards = k.Input((52,), dtype="int32", name="cards")
    seats = k.Input((52,), dtype="int32", name="seats")
    # A fixed ordered embedding is much cheaper than recurrent inference for
    # this first small baseline. Position is retained by flattening, not pooling.
    c = k.layers.Flatten()(k.layers.Embedding(53, 4)(cards))
    s = k.layers.Flatten()(k.layers.Embedding(5, 4)(seats))
    x = k.layers.Concatenate()([state, c, s])
    x = k.layers.Dense(width, activation="relu")(x)
    x = k.layers.Dropout(.1)(x)
    x = k.layers.Dense(64, activation="relu")(x)
    x = k.layers.Dense(52 * 4, kernel_initializer="zeros" if zero_output else "glorot_uniform")(x)
    logits = k.layers.Reshape((52, 4), name="ownership_logits")(x)
    return k.Model(dict(state=state, cards=cards, seats=seats), logits,
                   name="small_play_belief_v1")


def masked_loss(logits, target, mask, support):
    import tensorflow as tf
    logits = tf.where(support, logits, tf.constant(-1e9, dtype=logits.dtype))
    losses = tf.nn.sparse_softmax_cross_entropy_with_logits(labels=target, logits=logits)
    numerator = tf.reduce_sum(losses * mask)
    denominator = tf.reduce_sum(mask)
    return numerator, denominator
