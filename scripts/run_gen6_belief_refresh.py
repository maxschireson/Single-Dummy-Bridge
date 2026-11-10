"""Refresh the promoted dense belief on a verified incremental arena batch.

Reuse the promoted architecture, consequence labeling, replay mix and trainer.
Separate the frozen v4 world proposal used for labels from the gen5 fit parent.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import fcntl
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import time

for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

def collect_ids(value, target):
    if isinstance(value, str) and len(value) == 64:
        target.add(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            collect_ids(key, target)
            collect_ids(item, target)
    elif isinstance(value, list):
        for item in value:
            collect_ids(item, target)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "batch", "receipts", "base", "parent", "label-parent", "out"):
        ap.add_argument("--" + name, type=Path, required=True)
    ap.add_argument("--reserved-json", type=Path, action="append", default=[])
    ap.add_argument("--reserved-dataset", type=Path, action="append", default=[])
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--source-audit", type=Path)
    args = ap.parse_args()
    sys.path.insert(0, str(args.repo.resolve()))
    import numpy as np
    from bridge_harness.belief_capacity import sha
    from bridge_harness.bidding_env import deal_key
    from bridge_harness.core import Board
    from bridge_harness.training import digest
    from scripts.prepare_impactful_belief import init, one, pack
    from scripts.screen_attention_belief import save_json, split

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    lock = (out / "pipeline.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    os.environ["BRIDGE_DDS_LIBRARY"] = str(args.repo / "bridge_harness/libbridge_dds.so")
    parent_sha = sha(args.parent)
    label_sha = sha(args.label_parent)
    if parent_sha != "99330ad3b1387a6fd8d78b297b3d1c915dbb67f5e9e624c871b997c0352fd37a":
        raise ValueError("Unexpected gen5 parent")
    if label_sha != "b23eb37554a26abb5a5eaa03f547472c489abd00dd6f3c9b0cada96cc46eb7d9":
        raise ValueError("Changed consequence world proposal")
    old_manifest = json.loads((args.base / "manifest.json").read_text())
    old_data = json.loads((args.base / "dataset.json").read_text())
    if old_data["manifest_sha256"] != sha(args.base / "manifest.json"):
        raise ValueError("Historical manifest changed")
    manifest = json.loads((args.batch / "manifest.json").read_text())
    if digest({k: v for k, v in manifest.items() if k != "identity"}) != manifest["identity"]:
        raise ValueError("Arena manifest changed")
    source_audit = None
    if args.source_audit:
        source_audit = json.loads(args.source_audit.read_text())
        if source_audit['receipts_sha256'] != sha(args.receipts):
            raise ValueError("Derived receipts changed after source audit")
        if source_audit['sources_sha256'] != sha(args.batch / 'sources.json'):
            raise ValueError("Derived provenance changed after source audit")
    receipts = {r["index"]: r for r in json.loads(args.receipts.read_text())}
    old_groups = {"train": set(), "validation": set()}
    for entry in old_data["shards"]:
        path = Path(entry["file"])
        if sha(path) != entry["sha256"]:
            raise ValueError("Historical shard changed: " + str(path))
        with np.load(path, allow_pickle=False) as z:
            old_groups[entry["split"]].update(map(str, z["split_group"]))
    if old_groups["train"] & old_groups["validation"]:
        raise ValueError("Inherited split leakage")
    reserved = {e["family"] for e in old_manifest["families"] if e["split"] == "test"}
    for path in args.reserved_json:
        collect_ids(json.loads(path.read_text()), reserved)
    for path in args.reserved_dataset:
        for entry in json.loads(path.read_text())["shards"]:
            shard = Path(entry["file"])
            if not shard.is_absolute():
                shard = path.parent / shard
            if sha(shard) != entry["sha256"]:
                raise ValueError("Reserved shard changed")
            with np.load(shard, allow_pickle=False) as z:
                reserved.update(map(str, z["split_group"]))
    families = []
    skipped = []
    seen = set()
    bad = old_manifest["excluded_policy_sha256"]
    for path in sorted((args.batch / "episodes").glob("*.json.gz")):
        record = json.loads(gzip.decompress(path.read_bytes()))
        receipt = receipts[record["index"]]
        if sha(path) != receipt["episode_sha256"]:
            raise ValueError("Episode checksum differs")
        family = record["family"]
        if family in seen:
            raise ValueError("Duplicate incoming family")
        seen.add(family)
        if record["manifest_identity"] != manifest["identity"]:
            raise ValueError("Wrong arena identity")
        if family != receipt["family"] or record["split"] != receipt["split"]:
            raise ValueError("Receipt identity mismatch")
        if deal_key(Board.from_dict(record["board"]).hands, True) != family:
            raise ValueError("Wrong canonical family")
        expected = "train" if split(family) == "train" else "validation"
        if record["split"] != expected:
            raise ValueError("Changed inherited split")
        actor_policies = []
        for name in (record["candidate"], record["opponent"]):
            bot = manifest["bots"][name]
            h = bot["artifact_sha256"].get("policy")
            if h == bad or (bot.get("policy") and not h):
                raise ValueError("Excluded or unidentified active policy")
            actor_policies.append(h)
        if family in reserved:
            skipped.append(dict(family=family, reason="reserved"))
            continue
        if family in old_groups["train"] | old_groups["validation"]:
            skipped.append(dict(family=family, reason="already represented in base"))
            continue
        families.append(dict(family=family, split=split(family), sources=[
            dict(path=str(path.resolve()), sha256=sha(path), policy_clean=True,
                 active_policy_sha256=actor_policies)]))
    frozen = dict(schema="gen6-belief-incremental-source-v1",
                  base_dataset_sha256=sha(args.base / "dataset.json"),
                  arena_manifest_sha256=sha(args.batch / "manifest.json"),
                  training_parent_sha256=parent_sha,
                  label_parent_sha256=label_sha,
                  families=families, excluded=skipped,
                  source_splits=dict(Counter(e["split"] for e in families)),
                  trainer_sha256=sha(args.repo / "scripts/train_belief_factorial.py"),
                  labeling_sha256=sha(args.repo / "scripts/prepare_impactful_belief.py"),
                  dds_sha256=sha(args.repo / "bridge_harness/libbridge_dds.so"),
                  reserved_json_sha256={str(p):sha(p) for p in args.reserved_json},
                  reserved_dataset_sha256={str(p):sha(p) for p in args.reserved_dataset})
    if source_audit is not None:
        frozen.update(source_audit=source_audit, source_audit_sha256=sha(args.source_audit),
                      original_raw_episode_hashes='See compact sources.json; source file hashes refer to derived root-only episodes')
    source_file = out / "incremental-sources.json"
    if source_file.exists() and json.loads(source_file.read_text()) != frozen:
        raise ValueError("Frozen input changed on resume")
    save_json(source_file, frozen)
    print(json.dumps(dict(stage="frozen", families=len(families),
                          splits=frozen["source_splits"], skipped=len(skipped))), flush=True)
    if not (out / "dataset.json").exists():
        pending = [e for e in families if e["split"] != "test"]
        start = time.time()
        entries = []
        counts = Counter()
        cache = out / "empty-label-cache"
        cache.mkdir(exist_ok=True)
        with ProcessPoolExecutor(max_workers=args.workers, initializer=init,
                                 initargs=(str(args.label_parent), str(cache))) as pool:
            futures = [pool.submit(one, entry, str(out)) for entry in pending]
            for i, future in enumerate(as_completed(futures), 1):
                md = future.result()
                if md["rows"]:
                    entries.append(md)
                for key in ("rows", "targets"):
                    counts[md["split"] + "_" + key] += md[key]
                counts["upweighted_targets"] += md["upweighted_targets"]
                if i % 10 == 0 or i == len(pending):
                    status = dict(stage="labeling", completed_families=i,
                                  total_families=len(pending), counts=dict(counts),
                                  seconds=time.time()-start, updated=time.time())
                    save_json(out / "status.json", status)
                    print(json.dumps(status), flush=True)
        packed = pack(entries, out / "new-packed")
        cfg = dict(old_manifest)
        cfg.update(schema="gen6-dense-current-recipe-v1", parent_sha256=parent_sha,
                   parent_checkpoint=None, training_parent="promoted gen5 NumPy weights; fresh AdamW",
                   label_parent_sha256=label_sha,
                   families=old_manifest["families"]+families,
                   incremental_sources_sha256=sha(source_file),
                   initial_partial_snapshot=source_audit is None,
                   clean_sources_counts=dict(old_manifest["clean_sources_counts"],
                                             new_source_families=len(families),
                                             new_training_families=frozen["source_splits"].get("train",0),
                                             new_validation_families=frozen["source_splits"].get("validation",0)),
                   test_evaluated=False)
        save_json(out / "manifest.json", cfg)
        merged_counts = Counter(old_data["counts"])
        merged_counts.update(counts)
        dataset = dict(old_data, schema=cfg["schema"],
                       shards=old_data["shards"]+packed,
                       family_shards=old_data["family_shards"]+sorted(entries,key=lambda e:e["family"]),
                       counts=dict(merged_counts), new_counts=dict(counts),
                       manifest_sha256=sha(out / "manifest.json"), test_evaluated=False)
        save_json(out / "dataset.json", dataset)
    if not (out / "fit/result.json").exists():
        cmd = [sys.executable, "-u", str(args.repo / "scripts/train_belief_factorial.py"),
               "--data", str(out), "--out", str(out / "fit"), "--parent", str(args.parent),
               "--widths", "256", "128", "--loss", "consequence",
               "--epochs", "3", "--threads", str(args.threads)]
        print(json.dumps(dict(stage="training", command=cmd)), flush=True)
        subprocess.run(cmd, cwd=args.repo, env=os.environ.copy(), check=True)
    result = json.loads((out / "fit/result.json").read_text())
    save_json(out / "status.json", dict(stage="complete", best_epoch=result["best_epoch"],
              parent="gen5", selected_sha256=result["selected_sha256"], updated=time.time()))
    print(json.dumps(dict(stage="complete", best_epoch=result["best_epoch"],
                          initial_score=result["initial"]["score"],
                          selected_score=result["selected"]["score"],
                          export_max_error=result["export_max_error"])), flush=True)

if __name__ == "__main__":
    main()
