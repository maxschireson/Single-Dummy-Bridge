"""Frozen BEN bidder with small, information-legal residual bidding models.

Only the actor's hand and public auction enter the adapter. Full deals are used
exclusively by the existing reward code. Every adapter starts at the same policy.
"""
import numpy as np
from .bidding_env import CALL_ID, encode, pack_inputs

MAX_CALLS = 320
VARIANTS = ('dense_compressed', 'dense_exact', 'attention_exact')


def features(observations):
    hand = np.zeros((len(observations), 4, 13), np.float32)
    calls = np.zeros((len(observations), MAX_CALLS + 1), np.int32)
    roles = np.zeros_like(calls)
    context = np.zeros((len(observations), 6), np.float32)
    for i, obs in enumerate(observations):
        if len(obs.calls) > MAX_CALLS:
            raise ValueError('Auction exceeds legal bound')
        if len(obs.hand) != 13 or len(set(obs.hand)) != 13:
            raise ValueError('Invalid own hand')
        for c in obs.hand:
            hand[i, c // 13, 12 - c % 13] = 1
        calls[i, 0], roles[i, 0] = 1, 4  # START; distinct from padding.
        for j, call in enumerate(obs.calls):
            calls[i, j + 1] = CALL_ID[call]
            roles[i, j + 1] = (obs.dealer + j - obs.seat) % 4
        context[i, :2] = encode(obs)[-1, 2:4]
        context[i, 2 + (obs.seat - obs.dealer) % 4] = 1
    return dict(hand=hand, calls=calls, roles=roles, context=context)


def make_adapter(variant):
    import tensorflow as tf
    if variant not in VARIANTS:
        raise ValueError(variant)
    L = tf.keras.layers

    class Adapter(tf.keras.Model):
        def __init__(self):
            super().__init__(name=variant)
            self.bid = L.Embedding(40, 32 if variant == 'attention_exact' else 4)
            self.role = L.Embedding(5, 32 if variant == 'attention_exact' else 4)
            if variant == 'attention_exact':
                self.position = L.Embedding(MAX_CALLS + 1, 32)
                self.suit = L.Embedding(4, 8)
                self.hand_projection = L.Dense(32, activation='gelu')
                self.self_attention = L.MultiHeadAttention(2, 16)
                self.cross_attention = L.MultiHeadAttention(2, 16)
                self.ff1 = L.Dense(64, activation='gelu')
                self.ff2 = L.Dense(32)
                self.norm1, self.norm2, self.norm3 = [L.LayerNormalization() for _ in range(3)]
                self.hidden = L.Dense(64, activation='gelu')
            else:
                self.hidden = L.Dense(32, activation='gelu')
                self.hidden2 = L.Dense(32, activation='gelu')
            self.delta = L.Dense(40, kernel_initializer='zeros', bias_initializer='zeros')
            self.value = L.Dense(1, kernel_initializer='zeros', bias_initializer='zeros')

        def call(self, f):
            hand, calls = f['hand'], f['calls']
            lengths = tf.reduce_sum(hand, axis=-1, keepdims=True) / 13.
            hcp = tf.reduce_sum(hand[..., :4] * [4., 3., 2., 1.], axis=-1, keepdims=True) / 10.
            controls = (2 * hand[..., :1] + hand[..., 1:2]) / 3.
            global_features = tf.concat([f['hidden'], tf.math.log(tf.maximum(f['base'], 1e-12)), f['context']], -1)
            if variant == 'attention_exact':
                n = tf.reduce_max(tf.reduce_sum(tf.cast(calls != 0, tf.int32), axis=1))
                tokens, roles = calls[:, :n], f['roles'][:, :n]
                valid = tokens != 0
                auction = self.bid(tokens) + self.role(roles) + self.position(tf.range(n))[None, :, :]
                auction = self.norm1(auction + self.self_attention(auction, auction, attention_mask=valid[:, None, :]))
                auction = self.norm2(auction + self.ff2(self.ff1(auction)))
                suits = tf.broadcast_to(self.suit(tf.range(4))[None, :, :], [tf.shape(hand)[0], 4, 8])
                h = self.hand_projection(tf.concat([hand, lengths, hcp, controls, suits], -1))
                h = self.norm3(h + self.cross_attention(h, auction, attention_mask=valid[:, None, :]))
                out = self.hidden(tf.concat([global_features, tf.reshape(h, [-1, 128])], -1))
            else:
                if variant == 'dense_compressed':
                    hand = tf.concat([hand[..., :5], tf.reduce_sum(hand[..., 5:], -1, keepdims=True)], -1)
                h = tf.concat([hand, lengths, hcp, controls], -1)
                bids = (self.bid(calls) + self.role(f['roles'])) * tf.cast(calls != 0, tf.float32)[..., None]
                h = tf.reshape(h, [tf.shape(hand)[0], -1])
                bids = tf.reshape(bids, [-1, (MAX_CALLS + 1) * 4])
                out = self.hidden2(self.hidden(tf.concat([global_features, h, bids], -1)))
            logits = tf.math.log(tf.maximum(f['base'], 1e-12)) + self.delta(out)
            return tf.nn.softmax(logits), self.value(out)[:, 0]

    model = Adapter()
    model(dict(hand=np.zeros((1, 4, 13), np.float32), calls=np.ones((1, MAX_CALLS + 1), np.int32),
               roles=np.zeros((1, MAX_CALLS + 1), np.int32), context=np.zeros((1, 6), np.float32),
               hidden=np.zeros((1, 256), np.float32), base=np.full((1, 40), .025, np.float32)))
    return model


class FrozenBidder:
    def __init__(self, path):
        import tensorflow as tf
        from .bidding_ppo import Policy
        self.policy = Policy.load(path)
        self.policy.model.trainable = False
        self.encoder = tf.keras.Model(self.policy.model.inputs,
            [self.policy.model.outputs[0], self.policy.model.layers[-2].output])

        @tf.function(input_signature=[tf.TensorSpec([None, None, 193], tf.float32), tf.TensorSpec([None], tf.int32)])
        def forward(x, lengths):
            p, h = self.encoder(x, training=False)
            ix = tf.stack([tf.range(tf.shape(x)[0]), lengths - 1], axis=1)
            return tf.gather_nd(p, ix), tf.gather_nd(h, ix)
        self.forward = forward

    def encode(self, observations):
        x, lengths = pack_inputs([encode(o) for o in observations])
        p, h = self.forward(x, lengths)
        f = features(observations)
        f.update(base=p.numpy(), hidden=h.numpy())
        return f


class Trainer:
    def __init__(self, model, learning_rate=1e-4, epsilon=.005, anchor_weight=.02):
        import tensorflow as tf
        self.model = model
        self.optimizer = tf.keras.optimizers.Adam(learning_rate)
        self.optimizer.build(model.trainable_variables)
        self.checkpoint = tf.train.Checkpoint(model=model, optimizer=self.optimizer)

        def dist(raw, mask, explore):
            p = tf.maximum(raw, 1e-12) * mask
            p /= tf.reduce_sum(p, -1, keepdims=True)
            return (1 - explore) * p + explore * mask / tf.reduce_sum(mask, -1, keepdims=True)

        @tf.function(reduce_retracing=True)
        def update(f, masks, actions, old_logp, advantage, returns):
            masks = tf.cast(masks, tf.float32)
            old_logp = tf.cast(old_logp, tf.float32)
            advantage = tf.cast(advantage, tf.float32)
            returns = tf.cast(returns, tf.float32)
            with tf.GradientTape() as tape:
                raw, values = model(f)
                p = dist(raw, masks, epsilon)
                logp = tf.math.log(tf.maximum(tf.gather(p, actions, batch_dims=1), 1e-12))
                ratio = tf.exp(logp - old_logp)
                actor = -tf.reduce_mean(tf.minimum(ratio * advantage, tf.clip_by_value(ratio, .8, 1.2) * advantage))
                q, base = dist(f['base'], masks, 0.), dist(raw, masks, 0.)
                kl = tf.reduce_mean(tf.reduce_sum(q * (tf.math.log(tf.maximum(q, 1e-12)) - tf.math.log(tf.maximum(base, 1e-12))), -1))
                entropy = -tf.reduce_mean(tf.reduce_sum(p * tf.math.log(tf.maximum(p, 1e-12)), -1))
                value_loss = tf.reduce_mean(tf.square(values - returns))
                loss = actor + .5 * value_loss + anchor_weight * kl - .001 * entropy
            gradients = tape.gradient(loss, model.trainable_variables)
            tf.debugging.assert_all_finite(loss, 'Invalid loss')
            for g in gradients:
                tf.debugging.assert_all_finite(g, 'Invalid gradient')
            gs, norm = tf.clip_by_global_norm(gradients, .5)
            self.optimizer.apply_gradients(zip(gs, model.trainable_variables))
            approx_kl = tf.reduce_mean((ratio - 1) - (logp - old_logp))
            return dict(loss=loss, anchor_kl=kl, approx_kl=approx_kl, grad_norm=norm)
        self.update = update

    def train(self, arrays, rewards, rng, epochs=2, minibatch=64):
        f = {k:arrays[k] for k in ('hand', 'calls', 'roles', 'context', 'hidden', 'base')}
        returns = np.asarray(rewards, np.float32) / 10.
        advantages = returns - arrays['old_value']
        advantages /= max(float(advantages.std()), 1.)
        metrics = []
        for _ in range(epochs):
            order = rng.permutation(len(returns))
            for start in range(0, len(order), minibatch):
                ix = order[start:start + minibatch]
                m = self.update({k:v[ix] for k,v in f.items()}, arrays['masks'][ix], arrays['actions'][ix],
                                arrays['old_logp'][ix], advantages[ix], returns[ix])
                m = {k:float(v.numpy()) for k,v in m.items()}
                metrics.append(m)
                if m['approx_kl'] > .02:
                    return dict(minibatches=len(metrics), kl_stopped=True, last=m)
        return dict(minibatches=len(metrics), kl_stopped=False, last=metrics[-1])
