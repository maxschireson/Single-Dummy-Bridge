# SiD net S_0 (13 November 2026)

**Status: research prototype. No bot uses it, and it has not been played at a table.** How it was made, and what
it was measured to do: [training/sid-net-s0-20261113](../../../training/sid-net-s0-20261113/README.md). What it is
for: [the SiD loop specification](../../../experiments/sid_loop/SPEC.md).

Rollout net v2 (768 wide; `transfer/rollout-net-v2-20261113`, `runs/w768/policy_epoch5.npz`) trained five more
epochs on v2's own set with the exact line finder's labels joined, 1,791,365 parameters. Besides v2's outputs
(`policy`, `gap`, `owner`, `tricks`) it has, from `bridge_harness.gen7_net.forward`:

- `guar`, `cert`, `single`: [n, 52, 3] logits per card and target (one down, the contract, an overtrick). For the
  declaring side to play: the card guarantees the target / the true layout is in the card's certified set / the
  card wins the true layout's shape taken alone. For a defender to play, `guar` and `cert` say the same of the
  declaring side once the card is played; `single` is not trained there.
- `tricks14`: [n, 14] logits for the final tricks of the side to play.

Measured on 2,719 held-out Gen 8 deals:
- `guar` is calibrated for both sides. Contract log-loss 0.101 for the declaring side against 0.692 for its base
  rate, 0.249 against 0.660 for defenders.
- `cert` and `single` are over-confident for the declaring side, and say little where some card guarantees the
  target: their training labels leave the other cards unlabelled there.
- The card head is worse than v2's on the same rows (log-loss 0.553 against 0.531).

Rebuild `sid_net_s0.npz` from its parts with `python restore.py`: it checks every part's and the whole file's
SHA-256 against `manifest.json`. `metrics.json` is the trainer's.
