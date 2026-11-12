"""Small outcome-trained near-tie selector; only observable inputs are encoded.

The logged behavior randomized uniformly within its PIMC window. Regression
uses the observed action's return, never labels unchosen moves as good/bad.
A centered action head separates preferences from a shared state-value head.
"""
import numpy as np

MAX_ACTIONS = 13
INPUT_KEYS = ('known', 'played', 'visible', 'voids', 'remaining_counts',
              'context', 'history_cards', 'history_seats')


def encode(a, policy, utility, suit_order=None):
    """Encode only observations and pre-action PIMC estimates, never targets.

    Seat zero is the acting hand. Optional suit permutation is safe because
    this play-only model deliberately ignores the synthetic auctions.
    """
    a = {k: np.asarray(a[k]) for k in INPUT_KEYS}
    ct = a['context']; n = len(ct); rows = np.arange(n)
    actor, declarer, ply = ct[:, 1], ct[:, 3], ct[:, 10]
    seat_order = (actor[:, None] + np.arange(4)) % 4
    suits = np.arange(4) if suit_order is None else np.asarray(suit_order)
    cards = (suits[:, None]*13 + np.arange(13)).reshape(-1)
    inverse = np.argsort(cards); inverse_suit = np.argsort(suits)
    known = a['known'][rows[:, None], seat_order][:, :, cards]
    played = a['played'][rows[:, None], seat_order][:, :, cards]
    current = np.zeros((n, 4, 52), np.float32)
    for offset in range(3):
        take = ply % 4 > offset; r = rows[take]
        at = ply[take] - ply[take] % 4 + offset
        c = inverse[a['history_cards'][r, at]]
        s = (a['history_seats'][r, at]-actor[take]) % 4
        current[r, s, c] = 1
    declaring = actor % 2 == declarer % 2
    already = np.where(declaring, ct[:, 9], ply//4-ct[:, 9])
    q = np.asarray(utility) + np.where(declaring, 0, 13)[:, None] - already[:, None]
    q = q[:, cards]; behavior = np.asarray(policy)[:, cards]
    active = behavior > 0
    count = active.sum(1)
    if np.any((count < 1) | (count > MAX_ACTIONS)): raise ValueError('Invalid candidate count')
    if not np.allclose(behavior.sum(1), 1): raise ValueError('Behavior must sum to one')
    if not np.isfinite(q[active]).all(): raise ValueError('Missing candidate PIMC value')
    # All training and deployment support is uniform among the eligible moves.
    if not np.allclose(behavior[active], np.repeat(1/count, count)):
        raise ValueError('Expected uniform exploration on eligible candidates')
    order = np.argsort(~active, axis=1, kind='stable')[:, :MAX_ACTIONS]
    mask = np.arange(MAX_ACTIONS)[None, :] < count[:, None]
    q_actions = np.where(mask, np.take_along_axis(q, order, 1), 0).astype(np.float32)
    actual_cards = cards[order]
    # Each candidate sees all visible and played ranks in its own suit. Sharing
    # the scorer across ranks/suits substantially reduces parameter count.
    suit_patterns = np.concatenate([known, played, current], axis=1).reshape(n, 12, 4, 13).transpose(0, 2, 1, 3).reshape(n, 4, 156)
    local = suit_patterns[rows[:, None], order//13]
    trump = np.r_[inverse_suit, 4][ct[:, 4]]
    led = np.full(n, 4)
    mid = ply % 4 > 0; r = rows[mid]
    led[mid] = inverse_suit[a['history_cards'][r, ply[mid]-ply[mid]%4]//13]
    features = np.concatenate([local, np.eye(13, dtype=np.float32)[order % 13],
        (order//13 == trump[:, None])[..., None],
        (order//13 == led[:, None])[..., None]], axis=-1).astype(np.int8)
    state = [known.reshape(n, -1), played.reshape(n, -1), current.reshape(n, -1),
        a['visible'][rows[:, None], seat_order],
        a['voids'][rows[:, None], seat_order][:, :, suits].reshape(n, -1),
        a['remaining_counts'][rows[:, None], seat_order]/13]
    for values, size in [((ct[:, 0]-actor)%4, 4), ((ct[:, 2]-actor)%4, 4),
                         ((declarer-actor)%4, 4), (trump, 5), (led, 5), (ply%4, 4)]:
        state.append(np.eye(size, dtype=np.float32)[values])
    mean_q = (q_actions*mask).sum(1)/count
    state.append(np.stack([ply/52, already/13, ct[:, 5]/7, mean_q/13], axis=1))
    return dict(state=np.concatenate(state, 1).astype(np.float32),
                actions=features, mask=mask.astype(np.float32), q=q_actions), actual_cards


def build_model(state_size, action_size):
    import tensorflow as tf
    k = tf.keras
    state = k.Input((state_size,), name='state')
    actions = k.Input((MAX_ACTIONS, action_size), name='actions')
    h = k.layers.Dense(32, activation='relu', name='state_hidden')(state)
    value = k.layers.Dense(1, name='state_value')(h)
    shared = k.layers.RepeatVector(MAX_ACTIONS)(h)
    x = k.layers.Concatenate()([actions, shared])
    x = k.layers.Dense(16, activation='relu', name='action_hidden')(x)
    x = k.layers.Dense(8, activation='relu', name='action_hidden_2')(x)
    score = k.layers.Dense(1, kernel_initializer='zeros', name='action_score')(x)
    return k.Model(dict(state=state, actions=actions), dict(value=value, score=score), name='tiny_pimc_selector')


class SelectorWeights:
    """NumPy deployment of the checked Keras model; no TensorFlow in players."""
    def __init__(self, path):
        with np.load(path, allow_pickle=False) as z:
            self.weights = {name:z[name] for name in z.files}

    def predict(self, x):
        w=self.weights
        def dense(x, name, relu=False):
            y=x@w[name+'_kernel']+w[name+'_bias']
            return np.maximum(y,0) if relu else y
        h=dense(x['state'],'state_hidden',True)
        value=dense(h,'state_value')[:, 0]
        shared=np.broadcast_to(h[:,None,:], (len(h), MAX_ACTIONS, h.shape[-1]))
        a=dense(np.concatenate([x['actions'],shared],-1),'action_hidden',True)
        a=dense(a,'action_hidden_2',True)
        scores=dense(a,'action_score')[...,0]
        scores-= (scores*x['mask']).sum(1,keepdims=True)/x['mask'].sum(1,keepdims=True)
        return x['q']+value[:,None]+scores

    def choose(self, observation, details, rng):
        from .core import card
        from .training import input_tensors, observation_dict
        a={k:v[None] for k,v in input_tensors(observation_dict(observation)).items() if k in INPUT_KEYS}
        policy=np.zeros((1,52),np.float32); utility=np.zeros((1,52),np.float32)
        for c,p in details['behavior_probabilities'].items():policy[0,card(c)]=p
        for c,s in details['estimates'].items():utility[0,card(c)]=s['utility']
        x,cards=encode(a,policy,utility);values=self.predict(x)[0]
        valid=x['mask'][0].astype(bool);best=values[valid].max()
        tied=np.flatnonzero(valid & np.isclose(values,best,rtol=0,atol=1e-7))
        return int(cards[0,rng.choice(tied.tolist())]), {int(c):float(v) for c,v in zip(cards[0,valid],values[valid])}


from .players import PIMCPlayer, Decision


class SelectorPlayer(PIMCPlayer):
    def __init__(self, weights):
        super().__init__(32, 'tricks', True, .125)
        self.selector = SelectorWeights(weights)

    def choose(self, o, rng):
        from .core import symbol
        result = super().choose(o, rng)
        details = result.details
        if details.get('forced') or sum(p > 0 for p in details['behavior_probabilities'].values()) < 2:
            return result
        chosen, values = self.selector.choose(o, details, rng)
        assert details['behavior_probabilities'].get(symbol(chosen), 0) > 0
        details = dict(details, selector='tiny-outcome-v1',
            proposal_probabilities=details['behavior_probabilities'],
            selector_predictions={symbol(c):v for c,v in values.items()},
            selected_pimc_gap=details['estimates'][symbol(chosen)]['gap_to_best'])
        # Report the actual greedy selection policy (including numerical ties).
        best = max(values.values()); ties = [c for c,v in values.items() if abs(v-best) <= 1e-7]
        details['behavior_probabilities'] = {symbol(c):float(c in ties)/len(ties) for c in values}
        details['selected_probability'] = 1/len(ties)
        return Decision(chosen, details)
