#!/usr/bin/env python3
"""Validate complete self-play shards and count independent deals across chunks."""
import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.core import Board, Game, card
from bridge_harness.runner import replay
from bridge_harness.training import digest, iter_episodes, split_for


def audit(directories, expected_games):
    totals, splits = Counter(), {s: Counter() for s in ("train", "validation", "test")}
    deals, episodes, groups = set(), set(), {}
    chunks = []
    for directory in directories:
        directory = Path(directory)
        manifest = json.loads((directory / "manifest.json").read_text())
        config = manifest["config"]
        assert config["samples"] == 32 and config["near_tie"] == .125 and config["objective"] == "tricks"
        assert not list((directory / "failures").glob("*.json.gz")), directory
        chunk_games = 0
        for e in iter_episodes(directory):
            r = e["record"]; assert r["status"] == "ok" and len(r["tables"]) == 1
            assert all(x == "pimc" for x in r["assignments"][0])
            assert r["config"]["samples"] == 32 and r["config"]["near_tie"] == .125
            replay(r)
            b = Board.from_dict(r["board"]); did = digest(b.hands)
            assert did not in deals, "Repeated deal: count independent deals, not trajectories"
            assert e["episode_id"] not in episodes
            deals.add(did); episodes.add(e["episode_id"])
            assert len(e["examples"]) == 52
            split = split_for(b)
            game = Game(b)
            for row, action in zip(e["examples"], r["tables"][0]["actions"]):
                m, o, p, t = (row[k] for k in ("metadata", "observation", "policy_target", "belief_target"))
                assert m["deal_id"] == did and m["split"] == split
                assert m["ply"] == len(game.history)
                group = m["split_group"]
                assert groups.setdefault(group, split) == split, "Split leakage"
                actual = game.observation()
                assert digest(o) == digest(asdict(actual)), "Observation differs from legal pre-action information"
                assert o["history"] == [list(x) for x in actual.history]
                assert o["known_hands"] == [None if h is None else list(h) for h in actual.known_hands]
                assert o["legal"] == list(actual.legal)
                played = {c for _, c in game.history}
                known = {c for h in actual.known_hands if h is not None for c in h}
                for c, owner in enumerate(t["remaining_owner"]):
                    assert t["unknown_mask"][c] == (c not in played | known)
                    if c in played: assert owner == -1
                    else: assert owner in range(4) and c in game.hands[owner]
                assert abs(sum(p["behavior_probabilities"].values()) - 1) < 1e-10
                assert p["behavior_probabilities"][str(p["action"])] == p["selected_probability"] > 0
                assert p["action"] == card(action["card"])
                declaring = actual.actor % 2 == b.contract.declarer % 2
                final = r["tables"][0]["declarer_tricks"]
                actor_final = final if declaring else 13 - final
                before = actual.declarer_tricks if declaring else len(game.history) // 4 - actual.declarer_tricks
                assert p["remaining_actor_tricks"] == actor_final - before
                assert p["final_actor_tricks"] == actor_final
                for counter in (totals, splits[split]):
                    counter["rows"] += 1
                    counter["nonforced_policy_rows"] += not p["forced"]
                    counter["selector_rows"] += p["selector_eligible"]
                    counter["hidden_card_labels"] += sum(t["unknown_mask"])
                game.play(p["action"])
            assert game.done
            splits[split]["games"] += 1; totals["games"] += 1; chunk_games += 1
        chunks.append(dict(directory=str(directory), games=chunk_games,
                           corpus_sha256=manifest["corpus_sha256"]))
    assert totals["games"] == expected_games, (totals["games"], expected_games)
    return dict(validated=True, **totals, independent_deals=len(deals), split_groups=len(groups),
                splits=splits, chunks=chunks, samples=32, near_tie=.125)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directories", nargs="+")
    p.add_argument("--expected-games", type=int, required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    result = audit(args.directories, args.expected_games)
    dest = Path(args.out); dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("x") as f: json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
