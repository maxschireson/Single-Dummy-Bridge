from dataclasses import replace
import hashlib
import json
import multiprocessing as mp
import platform
import random
import time
import traceback

from . import __version__
from .core import Board, Game, SEATS, card, imps, symbol
from .players import Decision, make_player
from .dds import DDS_REVISION


def decision_rng(seed, board_id, spec, observation):
    # No actual deal data or deal-generation seed is provided to the player.
    payload = json.dumps([seed, board_id, spec, observation.controller, observation.history])
    return random.Random(int.from_bytes(hashlib.sha256(payload.encode()).digest(), "big"))


def play_table(board, assignments, players, seed=1, prefix=(), on_event=None, rng_group=None):
    game = Game(board)
    actions = []
    started = time.perf_counter()
    try:
        while not game.done:
            o = game.observation()
            spec = assignments[o.controller]
            before = time.perf_counter()
            if len(actions) < len(prefix):
                d = Decision(card(prefix[len(actions)]["card"]), {"replayed_prefix": True})
            elif not actions and board.opening_lead is not None:
                d = Decision(board.opening_lead, {"fixed_opening_lead": True})
            else:
                d = players[spec].choose(o, decision_rng(seed, board.id, rng_group or spec, o))
            elapsed = time.perf_counter() - before
            game.play(d.card)
            action = dict(ply=len(actions), seat=SEATS[o.actor], controller=SEATS[o.controller],
                          player=spec, card=symbol(d.card), seconds=elapsed, **d.details)
            actions.append(action)
            if on_event:
                on_event(action)
        return dict(status="ok", actions=actions, declarer_tricks=game.declarer_tricks,
                    ns_score=game.ns_score(), seconds=time.perf_counter()-started)
    except Exception as e:
        return dict(status="error", actions=actions, seconds=time.perf_counter()-started,
                    error=f"{type(e).__name__}: {e}", traceback=traceback.format_exc())


def run_pair(board, config, event=None):
    seed = config.get("seed", 1)
    candidate, baseline, common = (config.get(k, d) for k, d in
                                   (("candidate", "pimc"), ("baseline", "greedy"), ("common", "greedy")))
    mode = config.get("mode", "declarer")
    players = {}
    result = dict(schema_version=1, harness_version=__version__, dds_revision=DDS_REVISION,
                  python=platform.python_version(), board=board.to_dict(), config=config, tables=[])
    try:
        for spec in set((candidate, baseline, common)):
            players[spec] = make_player(spec, **{k: config[k] for k in
                ("samples", "ben_url", "timeout", "objective", "batch", "near_tie") if k in config})
        lead_decision = None
        if board.contract and mode not in ("partnership", "selfplay") and board.opening_lead is None:
            o = Game(board).observation()
            t = time.perf_counter()
            lead_decision = players[common].choose(o, decision_rng(seed, board.id, common, o))
            if lead_decision.card not in o.legal:
                raise ValueError("Invalid common opening lead")
            result["lead_selection"] = dict(card=symbol(lead_decision.card), player=common,
                                             seconds=time.perf_counter()-t, **lead_decision.details)
            board = replace(board, opening_lead=lead_decision.card)
        result["board"] = board.to_dict()
        if mode == "selfplay":
            assignments = [[candidate] * 4]
            sign = 1
        elif mode == "partnership":
            assignments = [[candidate, baseline, candidate, baseline], [baseline, candidate, baseline, candidate]]
            sign = 1
        elif mode in ("declarer", "defence"):
            parity = board.contract.declarer % 2 if board.contract else 0
            assignments = [[p if (s % 2 == parity) == (mode == "declarer") else common
                            for s in range(4)] for p in (candidate, baseline)]
            sign = (1 if parity == 0 else -1) * (1 if mode == "declarer" else -1)
        else:
            raise ValueError(f"Unknown mode {mode}")
        result["assignments"] = assignments
        for index, assignment in enumerate(assignments):
            def emit(action):
                if event:
                    event({"table": index, "action": action})
            table = play_table(board, assignment, players, seed, on_event=emit, rng_group=config.get('rng_group'))
            result["tables"].append(table)
        result["status"] = "ok" if all(t["status"] == "ok" for t in result["tables"]) else "error"
        if result["status"] == "ok" and mode != "selfplay":
            a, b = result["tables"]
            result["score_difference"] = sign * (a["ns_score"] - b["ns_score"])
            result["imps"] = imps(result["score_difference"])
            result["first_difference"] = next((i for i, (x, y) in enumerate(zip(a["actions"], b["actions"]))
                                                if x["card"] != y["card"]), None)
        return result
    except Exception as e:
        result.update(status="error", error=f"{type(e).__name__}: {e}", traceback=traceback.format_exc())
        return result
    finally:
        for p in players.values():
            if hasattr(p, "close"):
                p.close()


def _worker(conn, board, config):
    try:
        result = run_pair(board, config, lambda action: conn.send(("action", action)))
        conn.send(("result", result))
    finally:
        conn.close()


def isolated_pair(board, config, deadline=300):
    """Hard wall-clock deadline includes native DDS; preserve actions before failure."""
    ctx = mp.get_context("spawn")
    parent, child = ctx.Pipe(duplex=False)
    p = ctx.Process(target=_worker, args=(child, board, config))
    p.start(); child.close()
    until = time.monotonic() + deadline
    partial = [[], []]
    result = None
    while time.monotonic() < until:
        if parent.poll(min(0.1, max(0, until-time.monotonic()))):
            try:
                kind, data = parent.recv()
            except EOFError:
                break
            if kind == "result":
                result = data
                break
            partial[data["table"]].append(data["action"])
        elif not p.is_alive():
            break
    if result is None:
        timed_out = time.monotonic() >= until
        result = dict(schema_version=1, harness_version=__version__, dds_revision=DDS_REVISION,
                      status="timeout" if timed_out else "crash", board=board.to_dict(), config=config,
                      error=f"Board deadline {deadline}s exceeded" if timed_out else f"Worker exit code {p.exitcode}",
                      tables=[dict(status="incomplete", actions=a) for a in partial])
    if p.is_alive():
        p.join(timeout=0.2)
    if p.is_alive():
        p.terminate(); p.join(timeout=2)
    if p.is_alive():
        p.kill(); p.join()
    parent.close()
    return result


def replay(record):
    """Validate legality and scores using logged cards; no engine needed."""
    board = Board.from_dict(record["board"])
    results = []
    for t in record["tables"]:
        g = Game(board)
        for i, a in enumerate(t["actions"]):
            if SEATS[g.actor] != a["seat"] or a["ply"] != i:
                raise ValueError("Replay actor/ply mismatch")
            g.play(card(a["card"]))
        if t["status"] == "ok":
            if not g.done or g.ns_score() != t["ns_score"] or g.declarer_tricks != t["declarer_tricks"]:
                raise ValueError("Replay score mismatch")
        results.append(dict(plies=len(g.history), complete=g.done,
                            ns_score=g.ns_score() if g.done else None))
    return results
