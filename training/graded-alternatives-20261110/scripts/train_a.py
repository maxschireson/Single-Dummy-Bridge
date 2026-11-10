"""Graded-alternatives training of the bidder ("approach a").

Each chunk of fresh training deals is graded with the current net: at every learner decision,
each call above a probability threshold is rolled out greedily and scored from the cached DD table.
The update maximises the expected IMP gain over the greedy line, sum_a p(a) * adv(a), with the
same optimiser, gradient clip and KL anchor to the base net as the user's PPO run.
Every training deal is used once per pass.
"""
import argparse
import json
import os
import sys
import time

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
import numpy as np

sys.path.insert(0, '/home/claude/gen5r')
sys.path.insert(0, '/home/claude/bid')
import abid  # noqa: E402
from bridge_harness.bidding_ppo import Policy  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument('--tag', required=True)
p.add_argument('--lr', type=float, default=1e-5)
p.add_argument('--chunk', type=int, default=2500)
p.add_argument('--mb', type=int, default=128)
p.add_argument('--epochs', type=int, default=2)
p.add_argument('--kl', type=float, default=0.02)
p.add_argument('--anchor', type=float, default=0.02)
p.add_argument('--threshold', type=float, default=0.01)
p.add_argument('--train_deals', type=int, default=35000)
p.add_argument('--passes', type=int, default=1)
p.add_argument('--eval_every', type=int, default=4)
p.add_argument('--keep_frac', type=float, default=0.15)
p.add_argument('--init', default='/home/claude/bid/base.keras')
p.add_argument('--seed', type=int, default=1)
a = p.parse_args()

out = f'/home/claude/bid/runs/{a.tag}'
os.makedirs(out, exist_ok=True)
log = open(f'{out}/log.jsonl', 'a')


def emit(**row):
    row['t'] = round(time.time() - T0, 1)
    log.write(json.dumps(row) + '\n'); log.flush()
    print(json.dumps(row), flush=True)


T0 = time.time()
import tensorflow as tf  # noqa: E402
tf.keras.utils.set_random_seed(a.seed)
all_train = abid.Deals.from_export('/home/claude/bid/data/train.jsonl.gz')
dev = abid.Deals.from_export('/home/claude/bid/data/dev.jsonl.gz')
train = all_train.subset(np.arange(a.train_deals))
hold = all_train.subset(np.arange(35000, 40000))


def join(x, y):
    d = object.__new__(abid.Deals)
    d.hands, d.vul = x.hands + y.hands, x.vul + y.vul
    d.dealer, d.table = np.concatenate([x.dealer, y.dealer]), np.concatenate([x.table, y.table])
    d.static, d.vulflag = np.concatenate([x.static, y.static]), np.concatenate([x.vulflag, y.vulflag])
    return d


select = join(hold, dev)                      # 6,000 deals never trained on here
base = Policy.load('/home/claude/bid/base.keras')
learner = Policy.load(a.init)
model = learner.model
opt = tf.keras.optimizers.Adam(a.lr)
opt.build(model.trainable_variables)
emit(event='start', config=vars(a), train=len(train), select=len(select),
     trainable=int(sum(np.prod(v.shape) for v in model.trainable_variables)))


@tf.function(input_signature=[tf.TensorSpec([None, None, 193], tf.float32), tf.TensorSpec([None], tf.int32),
                              tf.TensorSpec([None, 40], tf.bool), tf.TensorSpec([None, None], tf.int32),
                              tf.TensorSpec([None, None], tf.float32), tf.TensorSpec([None, 40], tf.float32),
                              tf.TensorSpec([None, 40], tf.float32)])
def update(x, lengths, mask, alt, adv, q_base, p_old):
    maskf = tf.cast(mask, tf.float32)
    with tf.GradientTape() as tape:
        seq = model(x, training=False)
        raw = tf.gather_nd(seq, tf.stack([tf.range(tf.shape(x)[0]), lengths - 1], axis=1))
        prob = tf.maximum(raw, 1e-12) * maskf
        prob /= tf.reduce_sum(prob, axis=-1, keepdims=True)
        valid = tf.cast(alt >= 0, tf.float32)
        p_alt = tf.gather(prob, tf.maximum(alt, 0), batch_dims=1) * valid
        expected_gain = tf.reduce_sum(p_alt * adv, axis=1)            # IMPs over the greedy line
        actor = -tf.reduce_mean(expected_gain) / 10.0
        logp = tf.math.log(tf.maximum(prob, 1e-12))
        anchor_kl = tf.reduce_mean(tf.reduce_sum(q_base * (tf.math.log(tf.maximum(q_base, 1e-12)) - logp), axis=-1))
        loss = actor + a.anchor * anchor_kl
    grads = tape.gradient(loss, model.trainable_variables)
    pairs = [(g, v) for g, v in zip(grads, model.trainable_variables) if g is not None]
    clipped, norm = tf.clip_by_global_norm([g for g, _ in pairs], 0.5)
    opt.apply_gradients(zip(clipped, [v for _, v in pairs]))
    step_kl = tf.reduce_mean(tf.reduce_sum(p_old * (tf.math.log(tf.maximum(p_old, 1e-12)) - logp), axis=-1))
    return tf.reduce_mean(expected_gain), anchor_kl, step_kl, norm


def evaluate(label, opponent, deals, name):
    t = time.time()
    result, _ = abid.duplicate(deals, learner, opponent)
    s = abid.summary(result)
    emit(event='eval', at=label, versus=name, seconds=round(time.time() - t, 1), **s)
    return s


rng = np.random.default_rng(a.seed)
chunks_done = 0
for pass_no in range(a.passes):
    order = rng.permutation(len(train)) if pass_no else np.arange(len(train))
    for start in range(0, len(train), a.chunk):
        deals = train.subset(order[start:start + a.chunk])
        t = time.time()
        auc, g, stats = abid.grade(deals, learner, base, threshold=a.threshold, keep_frac=a.keep_frac,
                                   seed=a.seed * 1000 + chunks_done)
        t_grade = time.time() - t
        d = len(g['auction'])
        if chunks_done == 0 and a.init.endswith('base.keras'):
            q_base = g['probs']
        else:
            q_base = np.zeros((d, 40), np.float32)
            for s in range(0, d, 4096):
                x, lengths = abid.decision_inputs(auc, g['auction'][s:s + 4096], g['n'][s:s + 4096])
                q_base[s:s + 4096] = abid.masked(abid.forward(base, x, lengths), g['mask'][s:s + 4096])
        t = time.time()
        gains, kls, steps, stopped = [], [], 0, False
        for epoch in range(a.epochs):
            perm = rng.permutation(d)
            for s in range(0, d, a.mb):
                b = perm[s:s + a.mb]
                x, lengths = abid.decision_inputs(auc, g['auction'][b], g['n'][b])
                gain, akl, skl, norm = update(x, lengths, g['mask'][b], g['alt'][b].astype(np.int32), g['adv'][b],
                                              q_base[b], g['probs'][b])
                gains.append(float(gain)); kls.append(float(skl)); steps += 1
            if np.mean(kls[-max(1, d // a.mb):]) > a.kl:
                stopped = True
                break
        chunks_done += 1
        emit(event='chunk', chunk=chunks_done, pass_no=pass_no, grade_s=round(t_grade, 1), train_s=round(time.time() - t, 1),
             steps=steps, kl_stopped=stopped, mean_step_kl=float(np.mean(kls)), anchor_kl=float(akl),
             expected_gain_first=float(np.mean(gains[:10])), expected_gain_last=float(np.mean(gains[-10:])), **stats)
        if chunks_done % a.eval_every == 0:
            evaluate(chunks_done, base, select, 'base')
            model.save(f'{out}/chunk{chunks_done:03d}.keras')
evaluate('final', base, select, 'base')
model.save(f'{out}/final.keras')
emit(event='done')
