# The arrival run: /home/bridgebots/work/g9/runs/d6-arrival/control

Epochs played: [1, 2, 3, 4, 5]. Boards: 6200. Guests: ['guest-a', 'guest-b']. Rules `arrival-v2`.

*Shares of the scheduled boards, for this run only (nothing trains on it; rules v0 stays as accepted): self-play 0.10, promotion 0.30, the rest (0.60, and any empty purpose's share) to admission and panel pairs by the gain rule of G9-A4 (bridge_harness/arena9.gain_units).*

## 1 and 3. The player model at the table

*Prediction registered before the run:* 9a-32 against guest-a minus 8p-32 against guest-a, same deals: +0.2 IMPs a board or more pooled over epochs 2 to 5 (lowered from +0.4 on 12 Nov 11:45 UTC, before the run, on two sandbox pilots).

*Prediction registered before the run:* 9a-32 against guest-b minus 8p-32 against guest-b: between -0.2 and +0.2 IMPs a board in each epoch (epoch 4 on the arrival prior alone, epoch 5 on experience), and pooled within one standard error of zero.

`9a-32` against the guest minus `8p-32` against the same guest, on the same deals (the floor), IMPs a board from the bot's side.

| Guest | Epoch | Deals | Native: mean (SE) | Common: mean (SE) |
| --- | --- | ---: | --- | --- |
| guest-a | 2 | 300 | +0.430 (0.261) | +0.623 (0.220) |
| guest-a | 3 | 300 | +0.483 (0.277) | +0.517 (0.204) |
| guest-a | 4 | 300 | +0.530 (0.251) | +0.453 (0.209) |
| guest-a | 5 | 300 | +0.473 (0.264) | +0.540 (0.201) |
| guest-a | all | 1200 | +0.479 (0.131) | +0.533 (0.104) |
| guest-b | 4 | 300 | -0.060 (0.240) | +0.140 (0.205) |
| guest-b | 5 | 300 | -0.360 (0.232) | +0.133 (0.218) |
| guest-b | all | 600 | -0.210 (0.167) | +0.137 (0.150) |

## 2. What experience adds

*Prediction registered before the run:* P(card) for guest-a above 0.95 from epoch 3; guest-a's learned honesty 0.65 to 0.8 (the reader measures the effective value, sam); guest-b's below 0.25 from epoch 5; item 1's difference rises from epoch 2 to epochs 3 to 5 by less than its standard error at this size.

What each epoch's bots were handed for each guest (the snapshot frozen when the previous epoch closed), read as the Gen 9 bot reads it.

| Guest | Epoch | Boards in the snapshot | Deltas (board-sides) | P(card) as read | Other profiles as read | Honesty as read | Play factor | Snapshot = envelopes of earlier epochs |
| --- | --- | ---: | ---: | ---: | --- | ---: | --- | --- |
| guest-a | 2 | 0 | 0 | 0.661 | flat 0.17, house-gen5 0.07, house-gen6 0.06 | — (prior) | — | yes |
| guest-a | 3 | 735 | 2133 | 0.984 | — | 0.776 | — | yes |
| guest-a | 4 | 1494 | 4362 | 0.984 | — | 0.766 | — | yes |
| guest-b | 4 | 0 | 0 | 0.240 | house-gen5 0.24, house-gen6 0.24, house-dds40k 0.22, flat 0.06 | — (prior) | — | yes |
| guest-a | 5 | 2074 | 5968 | 0.984 | — | 0.761 | — | yes |
| guest-b | 5 | 776 | 2076 | 0.004 | house-gen5 0.62, house-dds40k 0.37 | 0.024 | — | yes |
| guest-a | 6 (after the run) | 2645 | 7518 | 0.984 | — | 0.754 | — | yes |
| guest-b | 6 (after the run) | 1472 | 3890 | 0.004 | house-gen5 0.81, house-dds40k 0.17 | 0.025 | — | yes |

## 6. The reading itself

*Prediction registered before the run:* Release check (g9, 12 Nov): 9a-32's reading not below 8p-32's by more than 0.3 nats on guest-b after its first epoch, and above it on guest-a.

On the floor boards, at each native table, the first decision of the bot's side after the opening lead: the log weight the auction gives the true layout, as that bot reads it, minus the log of its mean weight over every layout consistent with what it sees (nats; 0 = no information). Computed after the board, from its record (bridge_harness/arena9_pipeline.reading_gain).

| Guest | Epoch | `9a-32`: tables, mean (SE) | `8p-32`: tables, mean (SE) | Paired by deal: deals, difference (SE) | Not measured |
| --- | --- | --- | --- | --- | ---: |
| guest-a | 2 | 600, +1.736 (0.055) | 600, -2.567 (0.396) | 300, +4.303 (0.366) | 0 |
| guest-a | 3 | 598, +1.773 (0.057) | 598, -2.902 (0.393) | 300, +4.701 (0.393) | 0 |
| guest-a | 4 | 599, +1.869 (0.059) | 599, -2.174 (0.366) | 300, +4.037 (0.354) | 0 |
| guest-a | 5 | 599, +1.769 (0.058) | 599, -2.957 (0.414) | 300, +4.714 (0.411) | 0 |
| guest-a | all | 2396, +1.787 (0.029) | 2396, -2.650 (0.196) | 1200, +4.439 (0.191) | 0 |
| guest-b | 4 | 600, +2.452 (0.062) | 600, +2.599 (0.063) | 300, -0.147 (0.007) | 0 |
| guest-b | 5 | 596, +2.536 (0.069) | 596, +2.539 (0.069) | 298, -0.004 (0.000) | 0 |
| guest-b | all | 1196, +2.493 (0.046) | 1196, +2.569 (0.047) | 598, -0.076 (0.005) | 0 |

**Release check** (`9a-32` minus `8p-32`, paired by deal): guest-a pooled: +4.439 over 1200 deals; needs > 0 — met; guest-b after its first epoch (epochs [5]): -0.004 over 298 deals; needs ≥ -0.3 — met

## 4. The arena

**Registry events**

- seq 6 `activate` 9a-32 (epoch 2): arrival run plan (g9, 12 Nov 11:32 UTC): 9a-32 activated before epoch 2 so that its test can open
- seq 7 `open-test` 9a-32 (epoch 2): arrival run plan (g9, 12 Nov 11:32 UTC): the test of 9a-32 against 8p-32 opened by plan; not expected to decide
- seq 8 `submit` guest-a (epoch 2): arrival run plan: guest-a arrives before epoch 2 first model card: 0.661, flat: 0.165, house-dds40k: 0.046, house-gen5: 0.069, house-gen6: 0.058
- seq 9 `retire` 7s-32 (epoch 4): arrival run plan: a house bot retired by a queued command before epoch 4
- seq 10 `submit` guest-b (epoch 4): arrival run plan: guest-b arrives before epoch 4 first model card: 0.240, flat: 0.060, house-dds40k: 0.220, house-gen5: 0.240, house-gen6: 0.240
- seq 11 `activate` guest-a (epoch 4): rules arrival-v2: admitted evidence {"boards": 2174, "se": 0.2226}

**Share of boards by epoch**

| Epoch | guest-a | guest-b |
| --- | ---: | ---: |
| 1 | 0% | 0% |
| 2 | 64% | 0% |
| 3 | 66% | 0% |
| 4 | 39% | 51% |
| 5 | 38% | 47% |

**Ratings (native) at the close of each epoch, IMPs a board against the reference, 95% half-width**

- epoch 1: 9a-32 +2.12 ± 0.90, 7s-32 +2.02 ± 0.88, 8p-32 +1.93 ± 0.82, 5RZ32 +1.16 ± 0.98, 1 +0.00 ± 0.00
- epoch 2: 9a-32 +1.97 ± 0.59, 7s-32 +1.87 ± 0.59, 8p-32 +1.67 ± 0.56, 5RZ32 +0.46 ± 0.68, guest-a +0.40 ± 0.63, 1 +0.00 ± 0.00
- epoch 3: 9a-32 +2.20 ± 0.50, 7s-32 +2.06 ± 0.50, 8p-32 +1.99 ± 0.48, guest-a +1.00 ± 0.50, 5RZ32 +0.82 ± 0.58, 1 +0.00 ± 0.00
- epoch 4: guest-b +2.24 ± 0.44, 9a-32 +2.19 ± 0.43, 7s-32 (retired) +2.02 ± 0.47, 8p-32 +1.93 ± 0.41, guest-a +0.93 ± 0.44, 5RZ32 +0.75 ± 0.50, 1 +0.00 ± 0.00
- epoch 5: 9a-32 +2.23 ± 0.38, guest-b +2.14 ± 0.37, 8p-32 +2.07 ± 0.37, 7s-32 (retired) +2.06 ± 0.45, guest-a +1.03 ± 0.40, 5RZ32 +0.74 ± 0.46, 1 +0.00 ± 0.00

**Betting test `9a-32~8p-32`** on every direct board so far (native): 669 boards, K = 1.168 (promote at 20), L = 0.701 (futility at 10), decision None. The controller opens the test only once `9a-32` is admitted and rated above the champion.

## 5. Replay

```
{
 "epoch": 3,
 "k": 524288,
 "pair": "9a-32~guest-a",
 "index": 524288,
 "snapshot": "ac5055bbc4c0b3af8c550faa811c92c121fb2b4a79144aaa857e6e67d507d6d5",
 "recorded": "e86c84dc333864838170af5a544ea6eac0df0dedc50ca7238d36ef0a9554d200",
 "replayed": "e86c84dc333864838170af5a544ea6eac0df0dedc50ca7238d36ef0a9554d200",
 "manifest_recorded": "970fbf1038e62b90b1fe95d53b3ba2976409641a9861af8e9ab8797002adb647",
 "manifest_replayed": "970fbf1038e62b90b1fe95d53b3ba2976409641a9861af8e9ab8797002adb647",
 "common": [
  0,
  0
 ],
 "native": [
  0,
  0
 ],
 "same": true
}
```
