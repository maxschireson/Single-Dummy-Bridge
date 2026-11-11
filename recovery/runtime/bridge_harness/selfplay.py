"""Resumable, bounded self play with per-game process deadlines and atomic shards."""
import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import time

from .corpus import generate, load
from .dds import DDS_REVISION, DDS_VARIANT
from .runner import isolated_pair
from .training import SCHEMA_VERSION, digest, examples_from_record, export_npz, iter_episodes


def atomic_json(path, value, compressed=False):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    opener = gzip.open if compressed else open
    with opener(temp, "wt", encoding="utf-8") as f:
        json.dump(value, f, separators=(",", ":"), allow_nan=False)
        f.write("\n")
    os.replace(temp, path)


def provenance():
    root = Path(__file__).resolve().parents[1]
    paths = sorted((root / "bridge_harness").glob("*.py")) + sorted((root / "native").glob("*.cpp"))
    source = hashlib.sha256()
    for p in paths:
        source.update(str(p.relative_to(root)).encode()); source.update(p.read_bytes())
    library = root / "bridge_harness" / ("libbridge_dds.dylib" if platform.system() == "Darwin" else "libbridge_dds.so")
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    return dict(git_base=commit, source_sha256=source.hexdigest(), dds_revision=DDS_REVISION,
        dds_variant=DDS_VARIANT, library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),
        python=platform.python_version(), platform=platform.platform(), cpus=os.cpu_count())


def run_job(board, episode, config, deadline):
    cfg = {**config, "seed": config["seed"] + episode}
    record = isolated_pair(board, cfg, deadline)
    episode_id = digest([board.to_dict(), episode])[:24]
    examples = examples_from_record(record, episode_id)
    return dict(schema_version=SCHEMA_VERSION, episode_id=episode_id, episode=episode,
                record=record, examples=examples)


def summarize_run(directory, wall_seconds, attempted):
    times, rows, choices, selectors, explored, nodes, solves = [], 0, 0, 0, 0, 0, 0
    gaps = []
    splits = {s: dict(games=0, rows=0, choices=0, selectors=0) for s in ("train", "validation", "test")}
    contracts = {}
    deal_ids = set()
    owner_cards = 0
    for e in iter_episodes(directory):
        record = e["record"]; table = record["tables"][0]
        times.append(table["seconds"])
        contracts.setdefault(record["board"]["contract"], []).append(table["declarer_tricks"])
        if not e["examples"]:
            continue
        split = e["examples"][0]["metadata"]["split"]
        splits[split]["games"] += 1
        deal_ids.add(e["examples"][0]["metadata"]["deal_id"])
        for row, action in zip(e["examples"], table["actions"]):
            rows += 1; splits[split]["rows"] += 1
            choice = not row["policy_target"]["forced"]
            selector = row["policy_target"]["selector_eligible"]
            choices += choice; selectors += selector
            splits[split]["choices"] += choice; splits[split]["selectors"] += selector
            owner_cards += sum(row["belief_target"]["unknown_mask"])
            gap = action.get("selected_pimc_gap", 0)
            if choice: gaps.append(gap)
            explored += gap > 0
            nodes += action.get("dds_nodes", 0); solves += action.get("dds_calls", 0)
    games = len(times)
    failures = len(list((Path(directory) / "failures").glob("*.json.gz")))
    return dict(games=games, independent_deals=len(deal_ids), failures=failures,
        rows=rows, nonforced_policy_rows=choices, selector_rows=selectors,
        hidden_card_labels=owner_cards, selected_below_pimc_best=explored,
        mean_selected_pimc_gap=statistics.mean(gaps) if gaps else 0,
        dds_world_solves=solves, dds_nodes=nodes, splits=splits,
        total_wall_seconds=wall_seconds, attempted_games=attempted,
        games_per_second=games / wall_seconds if wall_seconds else None,
        mean_game_seconds=statistics.mean(times) if times else None,
        p50_game_seconds=statistics.median(times) if times else None,
        p95_game_seconds=sorted(times)[min(games - 1, int(games * .95))] if times else None,
        contract_results={k: dict(games=len(v), mean_declarer_tricks=statistics.mean(v)) for k, v in contracts.items()})


def run(args):
    if min(args.count, args.episodes, args.workers, args.samples) < 1 or args.board_timeout <= 0:
        raise ValueError("Positive counts, workers, samples and timeout required")
    if args.near_tie < 0:
        raise ValueError("near-tie must be nonnegative")
    boards = load(args.corpus) if args.corpus else list(generate(args.count, args.deal_seed))
    if args.corpus:
        boards = boards[:args.count]
    if not boards:
        raise ValueError("No boards")
    if len({b.id for b in boards}) != len(boards):
        raise ValueError("Duplicate board IDs")
    config = dict(mode="selfplay", candidate="pimc", baseline="pimc", common="pimc",
        samples=args.samples, objective=args.objective, near_tie=args.near_tie,
        batch=not args.serial_dds, seed=args.seed)
    manifest = dict(schema_version=SCHEMA_VERSION, config=config,
        corpus_sha256=digest([b.to_dict() for b in boards]), games_requested=len(boards) * args.episodes,
        episodes=args.episodes, provenance=provenance(), board_timeout=args.board_timeout)
    directory = Path(args.out)
    directory.mkdir(parents=True, exist_ok=True)
    # Single writer per run; a crashed run may require manually removing this
    # lock after checking that no writer remains. Never remove a live lock.
    lock = directory / ".writer.lock"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, str(os.getpid()).encode()); os.close(fd)
    try:
        previous = directory / "manifest.json"
        if previous.exists():
            if not args.resume:
                raise ValueError("Output exists; use --resume or a new directory")
            old = json.loads(previous.read_text())
            # The base commit may change when identical source is committed.
            for prov in (manifest["provenance"], old["provenance"]):
                prov.pop("git_base", None)
            if old != manifest:
                raise ValueError("Resume config, corpus, source, or solver differs")
        else:
            if any((directory / "episodes").glob("*.json.gz")):
                raise ValueError("Episodes exist without a manifest")
            atomic_json(previous, manifest)
        jobs = []
        for board in boards:
            for episode in range(args.episodes):
                eid = digest([board.to_dict(), episode])[:24]
                if not (directory / "episodes" / (eid + ".json.gz")).exists():
                    jobs.append((board, episode))
        old_summary = json.loads((directory / "summary.json").read_text()) if (directory / "summary.json").exists() else {}
        prior_wall = old_summary.get("total_wall_seconds", 0)
        prior_attempts = old_summary.get("attempted_games", 0)
        started = time.perf_counter(); completed = 0
        jobs = iter(jobs)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            pending = {}
            def submit():
                job = next(jobs, None)
                if job is not None:
                    future = pool.submit(run_job, *job, config, args.board_timeout)
                    pending[future] = job
            for _ in range(args.workers): submit()
            while pending:
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    pending.pop(future)
                    result = future.result()
                    status = result["record"]["status"]
                    sub = "episodes" if status == "ok" else "failures"
                    dest = directory / sub / (result["episode_id"] + ".json.gz")
                    atomic_json(dest, result, compressed=True)
                    if status == "ok":
                        (directory / "failures" / dest.name).unlink(missing_ok=True)
                    completed += 1
                    if completed % 10 == 0 or status != "ok":
                        print(f"completed={completed} status={status} elapsed={time.perf_counter()-started:.1f}s", flush=True)
                    submit()
        summary = summarize_run(directory, prior_wall + time.perf_counter() - started,
                                prior_attempts + completed)
        summary["workers"] = args.workers
        atomic_json(directory / "summary.json", summary)
        print(json.dumps(summary, indent=2), flush=True)
        return 1 if summary["failures"] else 0
    finally:
        lock.unlink(missing_ok=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    p.add_argument("--corpus", help="Frozen corpus; default is synthetic profiling/training deals")
    p.add_argument("--count", type=int, default=1000)
    p.add_argument("--episodes", type=int, default=1, help="Different exploration trajectories per deal")
    p.add_argument("--deal-seed", type=int, default=20261108)
    p.add_argument("--seed", type=int, default=9173, help="Decision seed; independent of deal seed")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--samples", type=int, default=32)
    p.add_argument("--objective", choices=("tricks", "score", "make"), default="tricks")
    p.add_argument("--near-tie", type=float, default=.125)
    p.add_argument("--board-timeout", type=float, default=300)
    p.add_argument("--serial-dds", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--export", choices=("train", "validation", "test"), help="Export this existing run split to NPZ")
    p.add_argument("--export-path")
    args = p.parse_args(argv)
    if args.export:
        if not args.export_path:
            p.error("--export-path is required with --export")
        print(f"Exported {export_npz(args.out, args.export_path, args.export)} rows")
        return 0
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
