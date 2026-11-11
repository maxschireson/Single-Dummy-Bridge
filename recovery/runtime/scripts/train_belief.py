#!/usr/bin/env python3
"""Train a small masked ownership baseline after the complete 10,000-deal audit.

Uses train/validation only. The test labels remain unopened. Model selection is
validation NLL; this script does not change the bot or claim strength gains.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.belief_model import (ENCODER_VERSION, INPUT_KEYS, build_model,
    capacity_prior, encode_inputs, masked_probabilities, masked_loss, permute_observation)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""): h.update(block)
    return h.hexdigest()


def inspect_dataset(root, audit):
    if not audit.get("validated") or audit.get("games") != 10000 or audit.get("independent_deals") != 10000:
        raise ValueError("A successful audit of exactly 10,000 independent complete deals is required")
    dirs = [root / f"chunk-{i}" for i in range(10)]
    if len(audit["chunks"]) != 10 or any(c["games"] != 1000 for c in audit["chunks"]):
        raise ValueError("Expected ten complete chunks")
    groups = {s: set() for s in ("train", "validation", "test")}
    rows = {s: 0 for s in groups}; provenance = []
    for i, d in enumerate(dirs):
        manifest = json.loads((d / "manifest.json").read_text())
        if manifest["corpus_sha256"] != audit["chunks"][i]["corpus_sha256"]:
            raise ValueError("Chunk identity differs from audit")
        for split in groups:
            p = d / f"{split}.npz"
            with np.load(p, allow_pickle=False) as z:
                # Test metadata only: no test inputs or labels are selected.
                g = z["split_group"]
                u, counts = np.unique(g, return_counts=True)
                if np.any(counts != 52) or groups[split].intersection(u):
                    raise ValueError("Repeated/incomplete original deal in export")
                groups[split].update(u); rows[split] += len(g)
            provenance.append(dict(chunk=i, split=split, sha256=sha(p)))
    for s in groups:
        if len(groups[s]) != audit["splits"][s]["games"] or rows[s] != audit["splits"][s]["rows"]:
            raise ValueError("Export counts differ from audit")
        for t in groups:
            if s != t and groups[s].intersection(groups[t]): raise ValueError("Split leakage")
    return dirs, provenance


def load_shard(path, augmentation=None, prior_cache=None):
    with np.load(path, allow_pickle=False) as z:
        a = {k: z[k] for k in INPUT_KEYS}
        target = z["owner_target"].astype(np.int32)
        mask = z["owner_loss_mask"]
        support = a["owner_support"]
        if np.any(mask & ((target < 0) | (target > 3))): raise ValueError("Invalid target")
        safe = np.maximum(target, 0)
        if np.any(mask & ~np.take_along_axis(support, safe[..., None], -1)[..., 0]):
            raise ValueError("Impossible ownership label")
        if np.any(mask & (support.sum(-1) <= 1)): raise ValueError("Hard-known labels in loss")
        prior = None
        if prior_cache is not None:
            cache_path = prior_cache / (path.parent.name + "-" + path.stem + ".npy")
            if cache_path.exists():
                prior = np.load(cache_path, allow_pickle=False)
            else:
                prior = capacity_prior(support, a["remaining_counts"])
                np.save(cache_path, prior)
        if augmentation is not None:
            rotation, suits = augmentation
            a, card_order, seat_order = permute_observation(a, rotation, suits)
            safe = (safe[:, card_order] + rotation) % 4
            mask = mask[:, card_order]
            support = a["owner_support"]
            if prior is not None: prior = prior[:, card_order][:, :, seat_order]
        x = encode_inputs(a)
        x["log_prior"] = (np.log(np.maximum(prior, 1e-12)) if prior is not None
                          else np.zeros(support.shape, np.float32))
        return x, safe, mask.astype(np.float32), support, a["remaining_counts"]


def totals(probabilities, target, mask):
    truth = np.take_along_axis(probabilities, target[..., None], -1)[..., 0]
    nll = -(np.log(np.maximum(truth, 1e-12)) * mask).sum(dtype=np.float64)
    accuracy = ((probabilities.argmax(-1) == target) * mask).sum(dtype=np.float64)
    # Multiclass Brier score; only uncertain hidden cards count.
    brier = ((np.square(probabilities).sum(-1) - 2 * truth + 1) * mask).sum(dtype=np.float64)
    return np.array([nll, accuracy, brier, mask.sum(dtype=np.float64)])


def summarize(t):
    return dict(nll=float(t[0] / t[3]), accuracy=float(t[1] / t[3]),
                brier=float(t[2] / t[3]), uncertain_card_labels=int(t[3]))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--audit", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--epochs", type=int, default=20)
    p.add_argument("--patience", type=int, default=4)
    p.add_argument("--batch-size", type=int, default=1024)
    p.add_argument("--width", type=int, default=80)
    p.add_argument("--seed", type=int, default=20261108)
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--residual-prior", action="store_true")
    p.add_argument("--augment", action="store_true")
    args = p.parse_args()
    if args.out.exists(): raise ValueError("Refusing to overwrite a training run")
    audit = json.loads(args.audit.read_text())
    dirs, provenance = inspect_dataset(args.data, audit)
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    os.environ.setdefault("OMP_NUM_THREADS", str(args.threads))
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(args.threads)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(args.seed)
    tf.config.experimental.enable_op_determinism()
    rng = np.random.default_rng(args.seed)
    first = load_shard(dirs[0] / "train.npz")
    model = build_model(first[0]["state"].shape[1], args.width, zero_output=args.residual_prior)
    del first
    optimizer = tf.keras.optimizers.AdamW(learning_rate=1e-3, weight_decay=1e-4, clipnorm=1.)
    args.out.mkdir(parents=True)
    prior_cache = args.out / "cache" if args.residual_prior else None
    if prior_cache is not None: prior_cache.mkdir()
    manifest = dict(schema=1, encoder=ENCODER_VERSION, parameters=model.count_params(),
        args={k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
        tensorflow=tf.__version__, numpy=np.__version__, audit_sha256=sha(args.audit),
        datasets=provenance, splits=audit["splits"],
        selection="lowest validation uncertain-card NLL; test labels unopened",
        objective="uncertain hidden remaining-card ownership cross entropy",
        auction="excluded: synthetic auctions contain no genuine bidding evidence",
        strength_evaluation="not performed; model not deployed to bot",
        architecture="ordered card/seat embeddings, Dense(width), dropout .1, Dense(64), 52x4 logits",
        output="residual added to log capacity prior" if args.residual_prior else "raw logits",
        augmentation="random seat rotation and suit permutation per training shard/epoch" if args.augment else "none")
    sources = ["bridge_harness/belief_model.py", "scripts/train_belief.py", "tests/test_belief_model.py"]
    repo = Path(__file__).resolve().parents[1]
    manifest["source_sha256"] = {p: sha(repo / p) for p in sources}
    for source in sources:
        dest = args.out / "source" / source; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / source, dest)
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(dict(event="start", parameters=model.count_params(), splits=audit["splits"])), flush=True)

    @tf.function(reduce_retracing=True)
    def train_step(x, y, mask, support):
        with tf.GradientTape() as tape:
            inputs = {k: v for k, v in x.items() if k != "log_prior"}
            logits = model(inputs, training=True) + x["log_prior"]
            numerator, denominator = masked_loss(logits, y, mask, support)
            loss = numerator / tf.maximum(denominator, 1.)
        grads = tape.gradient(loss, model.trainable_variables)
        optimizer.apply_gradients(zip(grads, model.trainable_variables))
        return numerator, denominator

    @tf.function(reduce_retracing=True)
    def predict(x):
        return model({k: v for k, v in x.items() if k != "log_prior"}, training=False) + x["log_prior"]

    def evaluate(baselines=False):
        sums = {"model": np.zeros(4, np.float64)}
        if baselines: sums.update(uniform_support=np.zeros(4), capacity_balanced=np.zeros(4))
        for d in dirs:
            x, y, mask, support, counts = load_shard(d / "validation.npz", prior_cache=prior_cache)
            for start in range(0, len(y), args.batch_size):
                sl = slice(start, start + args.batch_size)
                raw = predict({k: v[sl] for k, v in x.items()}).numpy()
                sums["model"] += totals(masked_probabilities(raw, support[sl]), y[sl], mask[sl])
                if baselines:
                    sums["uniform_support"] += totals(masked_probabilities(np.zeros_like(raw), support[sl]), y[sl], mask[sl])
                    sums["capacity_balanced"] += totals(capacity_prior(support[sl], counts[sl]), y[sl], mask[sl])
        return {k: summarize(v) for k, v in sums.items()}

    baseline = evaluate(baselines=True)
    (args.out / "baseline.json").write_text(json.dumps(baseline, indent=2))
    print(json.dumps(dict(event="baseline", **baseline)), flush=True)
    best, stale, history = baseline["model"]["nll"], 0, []
    model.save(args.out / "best.keras")
    (args.out / "best_metrics.json").write_text(json.dumps(dict(epoch=0, validation=baseline["model"]), indent=2))
    started = time.perf_counter()
    for epoch in range(1, args.epochs + 1):
        at = time.perf_counter(); train_sum = np.zeros(2, np.float64)
        order = rng.permutation(len(dirs))
        for i in order:
            augmentation = (int(rng.integers(4)), rng.permutation(4)) if args.augment else None
            x, y, mask, support, _ = load_shard(dirs[i] / "train.npz", augmentation=augmentation, prior_cache=prior_cache)
            rows = rng.permutation(len(y))
            for start in range(0, len(rows), args.batch_size):
                idx = rows[start:start + args.batch_size]
                if not mask[idx].any(): continue
                loss, count = train_step({k: v[idx] for k, v in x.items()}, y[idx], mask[idx], support[idx])
                train_sum += [float(loss), float(count)]
        val = evaluate()["model"]
        row = dict(epoch=epoch, seconds=time.perf_counter() - at,
                   train_nll=float(train_sum[0] / train_sum[1]), validation=val)
        history.append(row)
        with (args.out / "history.jsonl").open("a") as f: f.write(json.dumps(row) + "\n")
        if val["nll"] < best - 1e-5:
            best, stale = val["nll"], 0
            model.save(args.out / "best.keras")
            (args.out / "best_metrics.json").write_text(json.dumps(row, indent=2))
        else: stale += 1
        print(json.dumps(row), flush=True)
        if stale >= args.patience: break
    model.save(args.out / "last.keras")
    result = dict(status="complete", seconds=time.perf_counter() - started, epochs=len(history),
        best=json.loads((args.out / "best_metrics.json").read_text()), baseline=baseline,
        parameters=model.count_params(), test_evaluated=False,
        checkpoint_sha256=sha(args.out / "best.keras"))
    (args.out / "result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)


if __name__ == "__main__": main()
