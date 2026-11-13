# SiD net S_0: labels and training (13 November 2026)

Steps 1 and 2 of [the SiD loop specification](../../experiments/sid_loop/SPEC.md): exact labels from the line finder
(`experiments/sure_tricks/cells`, called SiD) on rollout net v2's records, and the first student net, `S_0`.
**Research: no bot uses `S_0`, and nothing here was played at a table.** The net is released at
[`models/cardplay/sid-net-s0-2026-11-13`](../../models/cardplay/sid-net-s0-2026-11-13/README.md).

Run on azure6 (8 cores, 32 GB) by `chain.sh` (stages `fetch label fetchB labelB build buildB train e1 push`), source on
`research/sid-net-s0-20261113`. The outputs are on `transfer/sid-net-s0-20261113` (research data, never merge):
every epoch's weights, the label sidecars as tar parts, the fetch manifests, label statistics and every log.

## What was labelled

- **Episodes:** the 75,545 episodes at the tips of rollout net v2's last fetch (`v2-fetch.json`, 02:17 UTC on
  13 November; `fetch_tips.py`). With the same builder they give v2's set exactly: 75,390 deals, 30,367,755 rows,
  60,992 families, the same 18 bots and the same split by family hash.
- **Rows:** every decision the builder keeps (`--policy-only`) in which the actor holds 7 cards or fewer:
  21,968,591 rows, 72% of the set. All of them joined to their rows (16 parts summed).
- **Labels** (`experiments/sid_loop/sidlabel.py`), per legal card and per target (one down, the contract, an
  overtrick):
  - Declaring side to play: `guar` (the card guarantees the target against every split), `single` (it wins the true
    layout's shape taken alone) and `cert` (the true layout is in the card's certified set).
  - A defender to play, from the declaring side's view once the card is played: `guar` (the declaring side then
    holds a guaranteed line) and `cert` (the true layout is in its best line's certified set).
  - Shape level, no named cards. Line choice is weighted by the hand-fit scorer (the auction only), cells to 99% of
    the weight. Training labels leave `cert` and `single` unasked for the cards that do not guarantee a target when
    another card does.
- **Cost:** 87,030 core-seconds, 3.96 ms a row; 3 h 11 min on 8 cores, 0 failed. Rows with 7 cards cost most:
  16.3 ms a defender row, 8.8 ms a declaring row (`label_stats.txt` on the output branch).
- **Checks before the run** (`experiments/sid_loop/results/checks-20261113.txt`), 84 episodes from ten feed types,
  0 differences: 123,423 declaring answers against `sure_cpp` at `2e6ed6d`; 37,572 defender answers against
  `Finder.handovers`; 110,693 answers on rows of four cards or fewer against brute force over explicit layouts.
  875 tables that played a guaranteed card at every labelled decision all made.

## Held-out boards

4,000 episodes that reached the feeds after v2's tips, all Gen 8: `arena-gen8-*` 1,418, `-19bbdce5` 1,047,
`-candidate` 1,016, `-m1` 215, `-p2` 153, `-f` 151. They were labelled in full (`--full`: every card, also where
another card guarantees the target): 2,156,241 rows. Deals whose family is in the training set are dropped, which
leaves 2,719 deals and 2,240,497 rows. The trainer scores each epoch on the first 600 of them (495,688 rows); E1 uses
all 2,719 (1,588,530 labelled rows).

## Training

`scripts/train_rollout_net.py --init` rollout net v2 (`runs/w768/policy_epoch5.npz` on
`transfer/rollout-net-v2-20261113`) with v2's recipe: 768 wide, five epochs, rate 2e-3 falling by one cosine, batch
512, all deals trained on (`--all-train`), label losses at weight 1.0. 1,791,365 parameters. 2 h 0 min on 8 cores.
The epoch with the lowest held-out card log-loss is kept: epoch 5.

Held-out scores by epoch, log-loss against the base rate's log-loss, contract target:

| Epoch | Card log-loss | Regret | `guar` declaring, 7 cards | `guar` defending, 7 cards | `cert`, all | `single`, all |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.619 | 0.0272 | 0.215 / 0.675 | 0.436 / 0.687 | 0.257 / 0.659 | 0.269 / 0.677 |
| 2 | 0.595 | 0.0255 | 0.194 | 0.429 | 0.264 | 0.288 |
| 3 | 0.575 | 0.0243 | 0.180 | 0.421 | 0.265 | 0.296 |
| 4 | 0.559 | 0.0229 | 0.173 | 0.420 | 0.239 | 0.246 |
| 5 | 0.553 | 0.0224 | 0.168 | 0.411 | 0.252 | 0.274 |

**The card head is worse than v2's on the same 495,688 held-out rows:** log-loss 0.553 against 0.531, regret
0.0224 against 0.0212, best card 91.7% against 92.1%. Epoch 1 moved it from v2's level to 0.619 and five epochs did
not bring it back. My guess, not tested: restarting at v2's full rate is the cause, and a lower rate or a frozen
trunk would keep v2's card head.

`cert` and `single` do not fall steadily on the held-out rows while their training losses do (training `cert`
0.156 to 0.113, held out 0.257 to 0.252). See the split below.

## E1: the student against the solver

`scripts/sid_e1.py` on all 2,719 held-out deals; the report is
[`e1-s0-20261113.txt`](../../experiments/sid_loop/results/e1-s0-20261113.txt). Errors are standard errors by deal.

**Heads** (log-loss / base-rate log-loss, contract target):

| Head | Declaring, all | Declaring, 7 cards | Defending, all | Defending, 7 cards |
| --- | --- | --- | --- | --- |
| `guar` | 0.101 / 0.692 | 0.163 / 0.676 | 0.249 / 0.660 | 0.405 / 0.689 |
| `cert` | 0.265 / 0.681 | 0.296 / 0.691 | 0.224 / 0.634 | 0.361 / 0.649 |
| `single` | 0.263 / 0.679 | 0.286 / 0.689 | | |

- **Calibration:** `guar` in both roles and `cert` for defenders are calibrated within a few points in every band.
  `cert` and `single` for the declaring side are over-confident: of cards given 0.5 to 0.6 (0.55 on average), 42%
  are certified.
- **The split** (`experiments/sid_loop/e1_split.py`,
  [`e1-split-s0-20261113.txt`](../../experiments/sid_loop/results/e1-split-s0-20261113.txt)), declaring side,
  contract target:
  - Where no card guarantees the contract, the only kind of position `cert` was trained on for every card:
    log-loss 0.169 against 0.306. Still over-confident: cards given 0.96 are certified 75% of the time.
  - Where some card guarantees it: 0.326 against 0.348. The other cards' `cert` was never labelled there.
  - Use `cert` and `single` only where `guar` says no card guarantees the target, and refit their calibration first.

**Declaring decisions** (816,977): shortfall of the chosen card's exact floor from the best card's, contract
target. Last column: the share naming the best card on the 156,804 decisions whose two best floors differ by more
than 0.05.

| Chooser | Shortfall | Share above 0.05 | Best card named |
| --- | --- | --- | --- |
| `cert` first | 0.0051 +- 0.0002 | 1.2% | 94.3% |
| `single` first | 0.0049 +- 0.0002 | 1.1% | 94.4% |
| `guar` first | 0.0054 +- 0.0002 | 1.2% | 94.0% |
| `S_0`'s card head | 0.0055 +- 0.0002 | 1.2% | 94.0% |
| v2's card head | 0.0055 +- 0.0002 | 1.2% | 94.0% |
| The card played | 0.0025 +- 0.0001 | 0.7% | 96.3% |
| A random card | 0.0732 +- 0.0013 | 9.7% | 51.4% |

With 7 cards: `cert` 0.0097, `S_0`'s card head 0.0097, v2's 0.0101, the card played 0.0057. At one down, `cert`
and `single` are worse than the card heads (0.0063 and 0.0070 against 0.0039 and 0.0040).

**Defender decisions** where some card hands the declaring side a guaranteed contract and some card does not
(50,083), the share that does not hand it over:

| Chooser | All | 7 cards |
| --- | --- | --- |
| Lowest `guar` | 0.900 +- 0.003 | 0.892 +- 0.005 |
| Lowest `cert` | 0.893 +- 0.003 | 0.881 +- 0.005 |
| `S_0`'s card head | 0.873 +- 0.003 | 0.863 +- 0.006 |
| v2's card head | 0.874 +- 0.003 | 0.866 +- 0.006 |
| The card played | 0.903 +- 0.003 | 0.881 +- 0.005 |
| A random card | 0.593 +- 0.003 | 0.626 +- 0.006 |

## What this shows and what it does not

- A net of this size learns which cards guarantee a target, for both sides, with calibrated probabilities. As a
  defender's choice, the lowest `guar` avoids handing over a guaranteed contract more often than either card head
  (0.900 against 0.873), and about as often as the card the bots played.
- On declaring decisions none of the label heads chooses closer to the solver's best floor than the card heads, and
  the card the bots played is about twice as close as any of them.
- The card head regressed against v2.
- Not measured: anything played (E2 and E3 of the specification), rows with 8 cards or more, labels weighted by the
  play. On 455 seven-card decisions, weighting by the play changed 1.3% to 2.4% of open `cert` entries
  ([`read_weights_m1_7cards.txt`](../../experiments/sid_loop/results/read_weights_m1_7cards.txt)). The held-out
  boards are Gen 8 only; the training set is mostly Gen 6 and 7.

## Rebuilding

From the repository root on a box with `~/work/venv`: `bash training/sid-net-s0-20261113/box-setup.sh`, then
`bash training/sid-net-s0-20261113/chain.sh`.
- **The training set:** `fetch_tips.py` gets the same 75,545 episodes. The labels need not be recomputed: unpack the
  tar parts of `labels/` on the output branch into `~/work/sidnet/labels`, then run the stages `fetch build`.
- **The held-out boards:** the stage `fetchB` takes the newest boards on the feeds, so a later run gets other
  boards. The 4,000 used here are named by blob id in `labelsB/files.txt` on the output branch; no script here
  fetches episodes by id.
