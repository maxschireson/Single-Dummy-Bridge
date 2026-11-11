"""Training records: observation-only inputs, privileged labels added after play.

The model input is exactly `observation`. Metadata, targets, and the underlying
replay record must never be fed to a model. Cards are S2..SA,H2..HA,D2..DA,C2..CA;
seats are N=0,E=1,S=2,W=3. See docs/SELFPLAY.md for loss masks and split rules.
"""
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path

from .core import Board, Game, card, symbol
from .runner import replay

SCHEMA_VERSION = 1


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def split_identity(board):
    # The identity comes from the cards, never a caller-supplied board ID/seed.
    # All repeated trajectories and related fixed-N/S layouts stay together.
    return digest([board.hands[0], board.hands[2]] if board.family else board.hands)


def split_for(board):
    bucket = int(split_identity(board)[:8], 16) % 100
    return "train" if bucket < 80 else "validation" if bucket < 90 else "test"


def observation_dict(o):
    return asdict(o)


def examples_from_record(record, episode_id):
    """Reconstruct pre-action observations, then add outcomes and true owners.

    This runs after a successful, independently replay-validated full game.
    Nothing from this function is passed back to a playing bot.
    """
    if record["status"] != "ok":
        return []
    replay(record)
    board = Board.from_dict(record["board"])
    examples = []
    for table_index, table in enumerate(record["tables"]):
        game = Game(board)
        for action in table["actions"]:
            o = game.observation()
            chosen = card(action["card"])
            declaring = o.actor % 2 == o.contract.declarer % 2
            final_declarer = table["declarer_tricks"]
            final_actor = final_declarer if declaring else 13 - final_declarer
            already_actor = o.declarer_tricks if declaring else len(o.history) // 4 - o.declarer_tricks
            owners = [-1] * 52
            shape = [[0] * 4 for _ in range(4)]
            unknown = [False] * 52
            for seat, hand in enumerate(game.hands):
                for c in hand:
                    owners[c] = seat
                    shape[seat][c // 13] += 1
                    unknown[c] = o.known_hands[seat] is None
            estimates = action.get("estimates", {})
            expected = estimates.get(symbol(chosen), {}).get("declarer_tricks")
            if expected is not None and not declaring:
                expected = 13 - expected
            probabilities = action.get("behavior_probabilities", {symbol(chosen): 1.0})
            policy = dict(action=chosen,
                behavior_probabilities={str(card(c)): p for c, p in probabilities.items()},
                selected_probability=probabilities[symbol(chosen)],
                pimc={str(card(c)): v for c, v in estimates.items()},
                objective=record["config"].get("objective", "score"),
                samples=action.get("samples", 0), near_tie=action.get("near_tie", 0.0),
                forced=len(o.legal) == 1,
                selector_eligible=sum(p > 0 for p in probabilities.values()) > 1,
                final_actor_tricks=final_actor, remaining_actor_tricks=final_actor - already_actor,
                final_declarer_tricks=final_declarer,
                actor_duplicate_score=table["ns_score"] * (1 if o.actor % 2 == 0 else -1),
                outcome_minus_pimc=None if expected is None else final_actor - expected)
            examples.append(dict(schema_version=SCHEMA_VERSION,
                metadata=dict(episode_id=episode_id, table=table_index, ply=len(o.history),
                    deal_id=digest(board.hands), split_group=split_identity(board),
                    split=split_for(board), auction_source=board.auction_source,
                    behavior=record["config"].get("behavior_id", "pimc-uniform-near-tie-v1")),
                observation=observation_dict(o), policy_target=policy,
                belief_target=dict(remaining_owner=owners, unknown_mask=unknown,
                    remaining_suit_counts=shape)))
            game.play(chosen)
    return examples


def iter_episodes(directory):
    for path in sorted((Path(directory) / "episodes").glob("*.json.gz")):
        with gzip.open(path, "rt") as f:
            yield json.load(f)


def iter_examples(directory, split=None):
    for episode in iter_episodes(directory):
        for example in episode["examples"]:
            if split is None or example["metadata"]["split"] == split:
                yield example


def input_tensors(observation):
    """NumPy features built only from the supplied pre-action observation.

    Absolute-seat baseline encoding; downstream models can rotate seats/suits.
    History remains ordered, allowing inference from choices as well as voids.
    """
    import numpy as np
    o = observation
    known = np.zeros((4, 52), dtype=np.float32)
    visible = np.array([h is not None for h in o["known_hands"]], dtype=np.float32)
    for s, h in enumerate(o["known_hands"]):
        if h is not None:
            known[s, h] = 1
    history_cards = np.full(52, 52, dtype=np.int16)
    history_seats = np.full(52, 4, dtype=np.int8)
    played = np.zeros((4, 52), dtype=np.float32)
    voids = np.zeros((4, 4), dtype=np.float32)
    for i, (s, c) in enumerate(o["history"]):
        history_cards[i], history_seats[i] = c, s
        played[s, c] = 1
        led = o["history"][i - i % 4][1] // 13
        if c // 13 != led:
            voids[s, led] = 1
    legal = np.zeros(52, dtype=np.bool_)
    legal[list(o["legal"])] = True
    support = np.zeros((52, 4), dtype=np.bool_)
    remaining_counts = 13 - played.sum(axis=1)
    for c in range(52):
        if played[:, c].any():
            continue
        if known[:, c].any():
            support[c] = known[:, c].astype(bool)
        else:
            support[c] = (visible == 0) & (voids[:, c // 13] == 0) & (remaining_counts > 0)
    ct = o["contract"]
    context = np.array([o["controller"], o["actor"], o["leader"], ct["declarer"],
        "SHDCN".index(ct["strain"]), ct["level"], ct["doubled"], o["dealer"],
        ("None", "NS", "EW", "Both").index(o["vulnerability"]),
        o["declarer_tricks"], len(o["history"])], dtype=np.int16)
    # Auctions are preserved in JSON; v1 tensors intentionally omit them because
    # the initial corpus uses synthetic auctions with no hand information.
    return dict(known=known, visible=visible, played=played, voids=voids,
        history_cards=history_cards, history_seats=history_seats, legal=legal,
        owner_support=support, remaining_counts=remaining_counts, context=context)


def export_npz(directory, output, split):
    """One split per file; refuse accidental overwrite. NumPy is optional."""
    import numpy as np
    examples = list(iter_examples(directory, split))
    if not examples:
        raise ValueError("No examples in selected split")
    inputs = [input_tensors(e["observation"]) for e in examples]
    arrays = {k: np.stack([x[k] for x in inputs]) for k in inputs[0]}
    arrays["owner_target"] = np.array([e["belief_target"]["remaining_owner"] for e in examples], dtype=np.int8)
    arrays["owner_loss_mask"] = np.array([e["belief_target"]["unknown_mask"] for e in examples]) & (arrays["owner_support"].sum(axis=2) > 1)
    arrays["action_target"] = np.array([e["policy_target"]["action"] for e in examples], dtype=np.int8)
    arrays["return_target"] = np.array([e["policy_target"]["remaining_actor_tricks"] for e in examples], dtype=np.float32)
    arrays["selector_mask"] = np.array([e["policy_target"]["selector_eligible"] for e in examples])
    arrays["behavior_probability"] = np.array([e["policy_target"]["selected_probability"] for e in examples], dtype=np.float32)
    arrays["pimc_utility"] = np.full((len(examples), 52), np.nan, dtype=np.float32)
    arrays["behavior_policy"] = np.zeros((len(examples), 52), dtype=np.float32)
    arrays["episode_id"] = np.array([e["metadata"]["episode_id"] for e in examples])
    arrays["split_group"] = np.array([e["metadata"]["split_group"] for e in examples])
    for i, e in enumerate(examples):
        for c, stats in e["policy_target"]["pimc"].items():
            arrays["pimc_utility"][i, int(c)] = stats["utility"]
        for c, p in e["policy_target"]["behavior_probabilities"].items():
            arrays["behavior_policy"][i, int(c)] = p
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as f:
        np.savez_compressed(f, **arrays)
    return len(examples)
