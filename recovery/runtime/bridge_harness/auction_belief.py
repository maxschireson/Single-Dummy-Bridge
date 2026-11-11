"""Auction-prefix encoder: own hand and public calls only; targets stay separate."""
import numpy as np

MAX_CALLS = 64
CALLS = ("PASS", "X", "XX") + tuple(f"{n}{s}" for n in range(1, 8) for s in "CDHSN")
CALL_ID = {c: i + 1 for i, c in enumerate(CALLS)}  # zero is padding
SCHEMA = "auction-belief-own-hand-relative-v1"


def encode_auction(own_hand, observer, dealer, vulnerability, prefix):
    """No full board, final contract, hidden hand or future call accepted."""
    if len(prefix) > MAX_CALLS: raise ValueError("Auction prefix exceeds encoder capacity")
    own = np.zeros(52, np.float32); own[list(own_hand)] = 1
    if own.sum() != 13: raise ValueError("Expected thirteen distinct own cards")
    shape = own.reshape(4, 13).sum(-1) / 13
    hcp = sum(max(0, c % 13 - 8) for c in own_hand) / 40
    vul = [vulnerability in ("NS", "Both"), vulnerability in ("EW", "Both")]
    state = np.concatenate([own, shape, [hcp, vul[observer % 2], vul[1 - observer % 2]],
        np.eye(4)[(dealer - observer) % 4], [len(prefix) / MAX_CALLS]]).astype(np.float32)
    calls = np.zeros(MAX_CALLS, np.int32); seats = np.full(MAX_CALLS, 4, np.int32)
    for i, call in enumerate(prefix):
        calls[i] = CALL_ID[call]; seats[i] = (dealer + i - observer) % 4
    support = np.ones((52, 4), bool); support[:, 0] = False
    support[own.astype(bool)] = [True, False, False, False]
    return dict(state=state, calls=calls, seats=seats), support


def make_model(state_size, width=64):
    import tensorflow as tf
    k = tf.keras
    state = k.Input((state_size,), name="state")
    calls = k.Input((MAX_CALLS,), dtype="int32", name="calls")
    seats = k.Input((MAX_CALLS,), dtype="int32", name="seats")
    c = k.layers.Flatten()(k.layers.Embedding(len(CALLS)+1, 4)(calls))
    s = k.layers.Flatten()(k.layers.Embedding(5, 2)(seats))
    x = k.layers.Concatenate()([state, c, s])
    x = k.layers.Dense(width, activation="relu")(x)
    x = k.layers.Dropout(.15)(x)
    x = k.layers.Dense(64, activation="relu")(x)
    x = k.layers.Dense(52*4, kernel_initializer="zeros")(x)
    return k.Model(dict(state=state, calls=calls, seats=seats),
                   k.layers.Reshape((52, 4))(x), name="small_auction_belief_v1")
