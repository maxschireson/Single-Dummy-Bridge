from collections import defaultdict
import math
import random
import statistics
from .core import Board
from .training import split_identity


def trick_difference(record):
    """Paired tricks oriented toward the candidate, including partnership swaps."""
    if not record["board"].get("contract"):
        return 0
    a, b = record["tables"]
    delta = a["declarer_tricks"] - b["declarer_tricks"]
    mode = record["config"].get("mode", "declarer")
    if mode == "partnership":
        return delta if record["board"]["declarer"] in ("N", "S") else -delta
    if mode == "declarer":
        return delta
    if mode == "defence":
        return -delta
    raise ValueError(f"Not a paired comparison mode: {mode}")


def quantile(values, q):
    if not values:
        return None
    v = sorted(values)
    return v[round((len(v)-1)*q)]


def summarize(records):
    ok = [r for r in records if r["status"] == "ok"]
    clusters = defaultdict(list)
    for r in ok:
        b = r["board"]
        # Board/family names can repeat across independent collection chunks.
        # Use actual cards (or fixed N/S cards for related layouts), as in the
        # train/validation/test boundary, to define independent clusters.
        clusters[split_identity(Board.from_dict(b))].append(
            (r["imps"], trick_difference(r)))
    rng = random.Random(194)
    groups = list(clusters.values())
    boot, trick_boot = [], []
    if len(groups) >= 2:
        for _ in range(2000):
            drawn = [rng.choice(groups) for _ in groups]
            values = [v for group in drawn for v in group]
            boot.append(statistics.mean(v[0] for v in values))
            trick_boot.append(statistics.mean(v[1] for v in values))
    timings, calls, samples = defaultdict(list), defaultdict(int), defaultdict(int)
    for r in records:
        for t in r.get("tables", []):
            for a in t["actions"]:
                # Fixed leads have their own measurement in lead_selection.
                if a.get("fixed_opening_lead") or a.get("replayed_prefix"):
                    continue
                timings[a["player"]].append(a["seconds"])
                calls[a["player"]] += a.get("dds_calls", 0)
                samples[a["player"]] += a.get("samples", 0)
    return dict(boards=len(records), completed_pairs=len(ok),
                failures=[dict(board=r["board"]["id"], status=r["status"],
                               error=r.get("error") or [t.get("error") for t in r.get("tables", [])])
                          for r in records if r["status"] != "ok"],
                independent_clusters=len(groups),
                mean_imps=statistics.mean(r["imps"] for r in ok) if ok else None,
                mean_tricks=statistics.mean(trick_difference(r) for r in ok) if ok else None,
                tricks_cluster_bootstrap_95_interval=[quantile(trick_boot,.025),quantile(trick_boot,.975)] if trick_boot else None,
                played_pairs=sum(bool(r["board"].get("contract")) for r in ok),
                passed_out_pairs=sum(not r["board"].get("contract") for r in ok),
                cluster_bootstrap_95_interval=[quantile(boot, .025), quantile(boot, .975)] if boot else None,
                wins=sum(r["imps"] > 0 for r in ok), ties=sum(r["imps"] == 0 for r in ok),
                losses=sum(r["imps"] < 0 for r in ok),
                timing={p: dict(decisions=len(v), total_seconds=sum(v),
                                mean_seconds=statistics.mean(v), p50_seconds=quantile(v,.5),
                                p95_seconds=quantile(v,.95), max_seconds=max(v),
                                dds_calls=calls[p], sampled_worlds=samples[p]) for p, v in timings.items()},
                largest_differences=[dict(board=r["board"]["id"], imps=r["imps"],
                                          scores=[t["ns_score"] for t in r["tables"]],
                                          tricks=[t["declarer_tricks"] for t in r["tables"]],
                                          first_difference=r["first_difference"])
                                     for r in sorted(ok,key=lambda r:abs(r["imps"]),reverse=True)[:10]])


def markdown(s):
    lines = ["# Match report", "", f"Completed {s['completed_pairs']} of {s['boards']} paired boards; "
             f"{len(s['failures'])} failures. Positive IMPs favor the candidate.", "",
             f"Mean: **{s['mean_imps']} IMP/board**. Wins/ties/losses: "
             f"{s['wins']}/{s['ties']}/{s['losses']}.", "",
             f"Mean: **{s['mean_tricks']} tricks/board**. Positive favors the candidate; "
             f"95% cluster bootstrap interval: {s['tricks_cluster_bootstrap_95_interval']}.", "",
             f"Played pairs: {s['played_pairs']}; passed-out pairs: {s['passed_out_pairs']}.", "",
             f"Independent board/family clusters: {s['independent_clusters']}. "
             f"95% cluster bootstrap interval: {s['cluster_bootstrap_95_interval']}.", "",
             "Intervals measure deal sampling uncertainty, not systematic engine or corpus bias. "
             "Failures are excluded from scores and reported separately. Synthetic auctions do not "
             "represent a realistic bidding population.", "",
             "| Player | Decisions | Mean ms | p95 ms | DDS calls |", "|---|---:|---:|---:|---:|"]
    for p, t in s["timing"].items():
        lines.append(f"| {p} | {t['decisions']} | {t['mean_seconds']*1000:.2f} | {t['p95_seconds']*1000:.2f} | {t['dds_calls']} |")
    lines += ["", "## Largest differences", "", "| Board | IMPs | NS scores | Declarer tricks | First differing ply (0-based) |",
              "|---|---:|---|---|---|"]
    for r in s["largest_differences"]:
        lines.append(f"| {r['board']} | {r['imps']} | {r['scores']} | {r['tricks']} | {r['first_difference']} |")
    if s["failures"]:
        lines += ["", "## Failures", ""] + [f"- {f}" for f in s["failures"]]
    return "\n".join(lines) + "\n"
