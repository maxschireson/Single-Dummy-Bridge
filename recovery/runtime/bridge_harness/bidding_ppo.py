"""PPO fine-tuning of external BEN bidding weights with a private-information critic.

Inference and gradient passes both disable dropout and freeze BatchNorm moments.
The legal-action exploration mixture is identical when collecting and updating.
"""
from pathlib import Path
import numpy as np
from .bidding_env import pack_inputs


class Policy:
    def __init__(self, model):
        import tensorflow as tf
        self.tf, self.model = tf, model
        if model.input_shape[-1] != 193 or model.outputs[0].shape[-1] != 40:
            raise ValueError('Requires BEN v3 193-feature / 40-output model')
        for layer in model.layers:
            if isinstance(layer, tf.keras.layers.BatchNormalization):
                layer.trainable = False

        @tf.function(input_signature=[tf.TensorSpec([None, None, 193], tf.float32),
                                       tf.TensorSpec([None], tf.int32)])
        def forward(x, lengths):
            out = self.model(x, training=False)
            if not isinstance(out, (tuple, list)):
                out = [out]
            ix = tf.stack([tf.range(tf.shape(x)[0]), lengths-1], axis=1)
            p = tf.gather_nd(out[0], ix)
            v = tf.gather_nd(out[1], ix)[:, 0] if len(out) > 1 else tf.zeros(tf.shape(x)[0])
            return p, v
        self.forward = forward

    @classmethod
    def load(cls, path, critic=False):
        import tensorflow as tf
        model = tf.keras.models.load_model(path, compile=False)
        # A Dense layer already applies independently to every time step. Remove
        # the redundant wrapper, whose vectorized_map fails with dynamic lengths
        # on some Keras releases. Preserve the exact layer and its saved weights.
        if len(model.outputs) == 1 and isinstance(model.layers[-1], tf.keras.layers.TimeDistributed):
            wrapper = model.layers[-1]
            if not isinstance(wrapper.layer, tf.keras.layers.Dense):
                raise ValueError('Only TimeDistributed(Dense) is supported')
            model = tf.keras.Model(model.inputs, wrapper.layer(wrapper.input))
        if critic and len(model.outputs) == 1:
            value = tf.keras.layers.Dense(1, kernel_initializer='zeros', bias_initializer='zeros',
                                          name='bidding_value')(model.layers[-2].output)
            model = tf.keras.Model(model.inputs, [model.outputs[0], value])
        return cls(model)

    def predict(self, x, lengths):
        p, v = self.forward(x, lengths)
        return p.numpy(), v.numpy()

    def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.model.save(path)


class PPO:
    def __init__(self, policy, anchor, *, learning_rate=1e-5, epsilon=.005,
                 clip=.2, anchor_weight=.02, entropy_weight=.001, target_kl=.02):
        tf = policy.tf
        self.policy, self.anchor = policy, anchor
        self.epsilon, self.target_kl = epsilon, target_kl
        self.optimizer = tf.keras.optimizers.Adam(learning_rate)
        self.optimizer.build(policy.model.trainable_variables)
        self.checkpoint = tf.train.Checkpoint(model=policy.model, optimizer=self.optimizer)

        def distribution(p, mask, exploration):
            mask = tf.cast(mask, tf.float32)
            p = tf.maximum(p, 1e-12)*mask
            p /= tf.reduce_sum(p, axis=-1, keepdims=True)
            return (1-exploration)*p + exploration*mask/tf.reduce_sum(mask, axis=-1, keepdims=True)

        @tf.function(input_signature=[
            tf.TensorSpec([None, None, 193], tf.float32), tf.TensorSpec([None], tf.int32),
            tf.TensorSpec([None, 40], tf.bool), tf.TensorSpec([None], tf.int32),
            tf.TensorSpec([None], tf.float32), tf.TensorSpec([None], tf.float32),
            tf.TensorSpec([None], tf.float32)])
        def update(x, lengths, masks, actions, old_logp, advantage, returns):
            ref, _ = anchor.forward(x, lengths)
            q = tf.stop_gradient(distribution(ref, masks, 0.))
            with tf.GradientTape() as tape:
                raw, values = policy.forward(x, lengths)
                p = distribution(raw, masks, epsilon)
                logp = tf.math.log(tf.maximum(tf.gather(p, actions, batch_dims=1), 1e-12))
                ratio = tf.exp(logp-old_logp)
                surrogate = tf.minimum(ratio*advantage, tf.clip_by_value(ratio, 1-clip, 1+clip)*advantage)
                actor_loss = -tf.reduce_mean(surrogate)
                value_loss = tf.reduce_mean(tf.square(values-returns))
                base = distribution(raw, masks, 0.)
                anchor_kl = tf.reduce_mean(tf.reduce_sum(q*(tf.math.log(tf.maximum(q, 1e-12))-
                                               tf.math.log(tf.maximum(base, 1e-12))), axis=-1))
                entropy = -tf.reduce_mean(tf.reduce_sum(p*tf.math.log(tf.maximum(p, 1e-12)), axis=-1))
                loss = actor_loss + .5*value_loss + anchor_weight*anchor_kl - entropy_weight*entropy
            gradients = tape.gradient(loss, policy.model.trainable_variables)
            tf.debugging.assert_all_finite(loss, 'Nonfinite PPO loss')
            for g in gradients:
                if g is not None:
                    tf.debugging.assert_all_finite(g, 'Nonfinite PPO gradient')
            pairs = [(g, v) for g, v in zip(gradients, policy.model.trainable_variables) if g is not None]
            gs, norm = tf.clip_by_global_norm([p[0] for p in pairs], .5)
            self.optimizer.apply_gradients(zip(gs, [p[1] for p in pairs]))
            approx_kl = tf.reduce_mean((ratio-1)-(logp-old_logp))
            return dict(loss=loss, actor_loss=actor_loss, value_loss=value_loss,
                        anchor_kl=anchor_kl, entropy=entropy, approx_kl=approx_kl, grad_norm=norm)
        self.update = update

    def train(self, decisions, rng, epochs=2, batch_size=256):
        if not decisions:
            raise ValueError('Cannot train without decisions')
        # The value target is IMPs/10; advantages preserve relative differences.
        returns = np.array([d['reward']/10 for d in decisions], np.float32)
        advantage = returns-np.array([d['old_value'] for d in decisions], np.float32)
        # Scale without subtracting a sample-dependent mean: preserve reward sign.
        advantage /= max(float(advantage.std()), 1.)
        updates = []
        stopped = False
        for _ in range(epochs):
            order = rng.permutation(len(decisions))
            for offset in range(0, len(order), batch_size):
                ix = order[offset:offset+batch_size]
                batch = [decisions[i] for i in ix]
                x, lengths = pack_inputs([d['x'] for d in batch])
                m = self.update(x, lengths, np.array([d['mask'] for d in batch]),
                    np.array([d['action'] for d in batch], np.int32),
                    np.array([d['old_logp'] for d in batch], np.float32), advantage[ix], returns[ix])
                metrics = {k: float(v.numpy()) for k, v in m.items()}
                updates.append(metrics)
                if metrics['approx_kl'] > self.target_kl:
                    stopped = True
                    break
            if stopped:
                break
        return dict(decisions=len(decisions), minibatches=len(updates), kl_stopped=stopped,
                    **{k: float(np.mean([m[k] for m in updates])) for k in updates[0]})

    def save(self, prefix):
        Path(prefix).parent.mkdir(parents=True, exist_ok=True)
        return self.checkpoint.save(str(prefix))

    def restore(self, checkpoint):
        self.checkpoint.restore(str(checkpoint)).assert_consumed()
