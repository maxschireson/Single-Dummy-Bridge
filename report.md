# The arrival run: /tmp/fullpath2/control

Epochs played: [1, 2, 3, 4, 5]. Boards: 144. Guests: ['guest-a', 'guest-b']. Rules `arrival-v2-fullpath-rehearsal`.

*Shares of the scheduled boards, for this run only (nothing trains on it; rules v0 stays as accepted): self-play 0.10, promotion 0.30, the rest (0.60, and any empty purpose's share) to admission and panel pairs by the gain rule of G9-A4 (bridge_harness/arena9.gain_units).*

## 1 and 3. The player model at the table

*Prediction registered before the run:* 9a-32 against guest-a minus 8p-32 against guest-a, same deals: +0.2 IMPs a board or more pooled over epochs 2 to 5 (lowered from +0.4 on 12 Nov 11:45 UTC, before the run, on two sandbox pilots).

*Prediction registered before the run:* 9a-32 against guest-b minus 8p-32 against guest-b: between -0.2 and +0.2 IMPs a board in each epoch (epoch 4 on the arrival prior alone, epoch 5 on experience), and pooled within one standard error of zero.

`9a-32` against the guest minus `8p-32` against the same guest, on the same deals (the floor), IMPs a board from the bot's side.

| Guest | Epoch | Deals | Native: mean (SE) | Common: mean (SE) |
| --- | --- | ---: | --- | --- |
| guest-a | 2 | 6 | +0.333 (0.333) | -1.000 (0.816) |
| guest-a | 3 | 6 | +0.167 (0.167) | -0.167 (0.401) |
| guest-a | 4 | 6 | +0.167 (0.167) | +4.500 (2.849) |
| guest-a | 5 | 6 | +3.500 (2.217) | -2.000 (1.807) |
| guest-a | all | 24 | +1.042 (0.603) | +0.333 (0.966) |
| guest-b | 4 | 10 | +0.100 (0.100) | +0.500 (0.500) |
| guest-b | 5 | 10 | -0.300 (0.213) | -0.100 (0.100) |
| guest-b | all | 20 | -0.100 (0.124) | +0.200 (0.258) |

## 2. What experience adds

*Prediction registered before the run:* P(card) for guest-a above 0.95 from epoch 3; guest-a's learned honesty 0.65 to 0.8 (the reader measures the effective value, sam); guest-b's below 0.25 from epoch 5; item 1's difference rises from epoch 2 to epochs 3 to 5 by less than its standard error at this size.

What each epoch's bots were handed for each guest (the snapshot frozen when the previous epoch closed), read as the Gen 9 bot reads it.

| Guest | Epoch | Boards in the snapshot | Deltas (board-sides) | P(card) as read | Other profiles as read | Honesty as read | Play factor | Snapshot = envelopes of earlier epochs |
| --- | --- | ---: | ---: | ---: | --- | ---: | --- | --- |
| guest-a | 2 | 0 | 0 | 0.661 | flat 0.17, house-gen5 0.07, house-gen6 0.06 | — (prior) | — | yes |
| guest-a | 3 | 18 | 50 | 0.984 | — | 0.761 | — | yes |
| guest-a | 4 | 32 | 89 | 0.984 | — | 0.743 | — | yes |
| guest-b | 4 | 0 | 0 | 0.240 | house-gen5 0.24, house-gen6 0.24, house-dds40k 0.22, flat 0.06 | — (prior) | — | yes |
| guest-a | 5 | 44 | 125 | 0.984 | — | 0.752 | — | yes |
| guest-b | 5 | 22 | 54 | 0.004 | house-gen5 0.53, house-dds40k 0.46 | 0.232 | — | yes |
| guest-a | 6 (after the run) | 55 | 154 | 0.984 | — | 0.768 | — | yes |
| guest-b | 6 (after the run) | 42 | 103 | 0.004 | house-gen5 0.56, house-dds40k 0.43 | 0.198 | — | yes |

## 6. The reading itself

*Prediction registered before the run:* Release check (g9, 12 Nov): 9a-32's reading not below 8p-32's by more than 0.3 nats on guest-b after its first epoch, and above it on guest-a.

On the floor boards, at each native table, the first decision of the bot's side after the opening lead: the log weight the auction gives the true layout, as that bot reads it, minus the log of its mean weight over every layout consistent with what it sees (nats; 0 = no information). Computed after the board, from its record (bridge_harness/arena9_pipeline.reading_gain).

| Guest | Epoch | `9a-32`: tables, mean (SE) | `8p-32`: tables, mean (SE) | Paired by deal: deals, difference (SE) | Not measured |
| --- | --- | --- | --- | --- | ---: |
| guest-a | 2 | 12, +1.369 (0.289) | 12, -4.852 (3.138) | 6, +6.221 (2.841) | 0 |
| guest-a | 3 | 12, +1.890 (0.334) | 12, -2.183 (2.607) | 6, +4.073 (2.216) | 0 |
| guest-a | 4 | 12, +2.259 (0.463) | 12, -3.527 (2.957) | 6, +5.786 (3.422) | 0 |
| guest-a | 5 | 12, +2.068 (0.516) | 12, -0.702 (1.967) | 6, +2.771 (2.372) | 0 |
| guest-a | all | 48, +1.897 (0.205) | 48, -2.816 (1.328) | 24, +4.713 (1.315) | 0 |
| guest-b | 4 | 20, +1.478 (0.407) | 20, +2.183 (0.237) | 10, -0.705 (0.302) | 0 |
| guest-b | 5 | 20, +1.422 (0.559) | 20, +2.546 (0.336) | 10, -1.125 (0.464) | 0 |
| guest-b | all | 40, +1.450 (0.341) | 40, +2.365 (0.205) | 20, -0.915 (0.274) | 0 |

**Release check** (`9a-32` minus `8p-32`, paired by deal): guest-a pooled: +4.713 over 24 deals; needs > 0 — met; guest-b after its first epoch (epochs [5]): -1.125 over 10 deals; needs ≥ -0.3 — **not met**

## 4. The arena

**Registry events**

- seq 6 `activate` 9a-32 (epoch 2): arrival run plan (g9, 12 Nov 11:32 UTC): 9a-32 activated before epoch 2 so that its test can open
- seq 7 `open-test` 9a-32 (epoch 2): arrival run plan (g9, 12 Nov 11:32 UTC): the test of 9a-32 against 8p-32 opened by plan; not expected to decide
- seq 8 `submit` guest-a (epoch 2): arrival run plan: guest-a arrives before epoch 2 first model card: 0.661, flat: 0.165, house-dds40k: 0.046, house-gen5: 0.069, house-gen6: 0.058
- seq 9 `retire` 7s-32 (epoch 4): arrival run plan: a house bot retired by a queued command before epoch 4
- seq 10 `submit` guest-b (epoch 4): arrival run plan: guest-b arrives before epoch 4 first model card: 0.240, flat: 0.060, house-dds40k: 0.220, house-gen5: 0.240, house-gen6: 0.240

**Share of boards by epoch**

| Epoch | guest-a | guest-b |
| --- | ---: | ---: |
| 1 | 0% | 0% |
| 2 | 75% | 0% |
| 3 | 58% | 0% |
| 4 | 30% | 55% |
| 5 | 30% | 55% |

**Ratings (native) at the close of each epoch, IMPs a board against the reference, 95% half-width**

- epoch 1: 9a-32 +2.62 ± 3.17, 8p-32 +1.12 ± 2.65, 7s-32 +0.33 ± 2.82, 5RZ32 +0.28 ± 3.28, 1 +0.00 ± 0.00
- epoch 2: guest-a +1.52 ± 2.53, 9a-32 +1.38 ± 2.50, 7s-32 +0.84 ± 2.54, 8p-32 +0.83 ± 2.26, 5RZ32 +0.79 ± 2.63, 1 +0.00 ± 0.00
- epoch 3: 9a-32 +1.25 ± 2.23, 7s-32 +1.14 ± 2.24, 8p-32 +1.03 ± 2.07, guest-a +0.88 ± 2.14, 5RZ32 +0.21 ± 2.35, 1 +0.00 ± 0.00
- epoch 4: guest-b +2.09 ± 2.30, 9a-32 +1.62 ± 2.02, 7s-32 (retired) +1.11 ± 2.21, 8p-32 +1.09 ± 1.93, 5RZ32 +0.10 ± 2.24, 1 +0.00 ± 0.00, guest-a -0.38 ± 2.05
- epoch 5: guest-b +1.79 ± 2.02, 9a-32 +1.73 ± 1.94, 8p-32 +1.31 ± 1.87, 7s-32 (retired) +1.19 ± 2.20, 5RZ32 +0.20 ± 2.19, 1 +0.00 ± 0.00, guest-a -0.81 ± 2.00

**Betting test `9a-32~8p-32`** on every direct board so far (native): 15 boards, K = 1.058 (promote at 20), L = 0.987 (futility at 10), decision None. The controller opens the test only once `9a-32` is admitted and rated above the champion.

## 5. Replay

```
{
 "epoch": 3,
 "k": 524288,
 "pair": "9a-32~guest-a",
 "index": 524288,
 "snapshot": "8bccfca4764097dc51f78574febe9938ce2f8a512677b514e2b6a0e9b40f8d63",
 "recorded": "37030274e82404da6702ce406e7bc8b19964bab9b63a677aa654b8e115daac14",
 "replayed": "37030274e82404da6702ce406e7bc8b19964bab9b63a677aa654b8e115daac14",
 "manifest_recorded": "11073d059fa4eb210a0c59628fbdc614dad32d55996b9c7d881b88c2699f394e",
 "manifest_replayed": "11073d059fa4eb210a0c59628fbdc614dad32d55996b9c7d881b88c2699f394e",
 "common": [
  -2,
  -2
 ],
 "native": [
  2,
  2
 ],
 "same": true
}
```
