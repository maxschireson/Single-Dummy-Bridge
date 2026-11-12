# The arrival run: /tmp/fullpath/control

Epochs played: [1, 2, 3, 4, 5]. Boards: 80. Guests: ['guest-a', 'guest-b'].

## 1 and 3. The player model at the table

`9a-32` against the guest minus `8p-32` against the same guest, on the same deals (the floor), IMPs a board from the bot's side.

| Guest | Epoch | Deals | Native: mean (SE) | Common: mean (SE) |
| --- | --- | ---: | --- | --- |
| guest-a | 2 | 4 | -1.250 (1.250) | +0.000 (0.000) |
| guest-a | 3 | 4 | -0.250 (1.031) | +0.250 (0.629) |
| guest-a | 4 | 4 | +0.000 (0.000) | +0.000 (0.000) |
| guest-a | 5 | 4 | +1.500 (3.708) | -6.250 (4.090) |
| guest-a | all | 16 | +0.000 (0.940) | -1.500 (1.165) |
| guest-b | 4 | 3 | -1.000 (0.577) | +0.000 (0.000) |
| guest-b | 5 | 3 | -3.333 (3.383) | -0.333 (0.333) |
| guest-b | all | 6 | -2.167 (1.621) | -0.167 (0.167) |

## 2. What experience adds

What each epoch's bots were handed for each guest (the snapshot frozen when the previous epoch closed), read as the Gen 9 bot reads it.

| Guest | Epoch | Boards in the snapshot | Deltas (board-sides) | P(card) as read | Other profiles as read | Honesty as read | Play factor | Snapshot = envelopes of earlier epochs |
| --- | --- | ---: | ---: | ---: | --- | ---: | --- | --- |
| guest-a | 2 | 0 | 0 | 0.792 | flat 0.20 | — (prior) | — | yes |
| guest-a | 3 | 5 | 16 | 0.984 | — | 0.616 | — | yes |
| guest-a | 4 | 9 | 31 | 0.984 | — | 0.627 | — | yes |
| guest-b | 4 | 0 | 0 | 0.692 | flat 0.17, house-gen5 0.05 | — (prior) | — | yes |
| guest-a | 5 | 13 | 44 | 0.984 | — | 0.680 | — | yes |
| guest-b | 5 | 3 | 9 | 0.004 | house-gen5 0.37, house-gen6 0.34, house-dds40k 0.22, flat 0.07 | 0.242 | — | yes |
| guest-a | 6 (after the run) | 17 | 60 | 0.984 | — | 0.685 | — | yes |
| guest-b | 6 (after the run) | 6 | 18 | 0.004 | house-gen5 0.38, house-gen6 0.38, house-dds40k 0.23 | 0.247 | — | yes |

## 4. The arena

**Registry events**

- seq 6 `submit` guest-a (epoch 2): arrival run plan: guest-a arrives before epoch 2 first model card: 0.792, flat: 0.198, house-dds40k: 0.003, house-gen5: 0.004, house-gen6: 0.003
- seq 7 `retire` 7s-32 (epoch None): arrival run plan: a house bot retired by a queued command before epoch 4
- seq 8 `submit` guest-b (epoch 4): arrival run plan: guest-b arrives before epoch 4 first model card: 0.692, flat: 0.173, house-dds40k: 0.032, house-gen5: 0.054, house-gen6: 0.049

**Share of boards by epoch**

| Epoch | guest-a | guest-b |
| --- | ---: | ---: |
| 1 | 0% | 0% |
| 2 | 56% | 0% |
| 3 | 50% | 0% |
| 4 | 50% | 38% |
| 5 | 50% | 38% |

**Ratings (native) at the close of each epoch, IMPs a board against the reference, 95% half-width**

- epoch 1: 1 +0.00 ± 0.00, 7s-32 -4.99 ± 4.62
- epoch 2: 8p-32 +3.12 ± 3.18, 9a-32 +1.92 ± 3.89, 1 +0.00 ± 0.00, guest-a -1.28 ± 3.15, 7s-32 -4.99 ± 4.62
- epoch 3: 8p-32 +1.38 ± 2.64, 9a-32 +1.17 ± 3.37, 1 +0.00 ± 0.00, guest-a -1.71 ± 2.81, 7s-32 -4.99 ± 4.62
- epoch 4: guest-b +1.40 ± 3.25, 8p-32 +1.38 ± 2.37, 9a-32 +1.17 ± 2.93, 1 +0.00 ± 0.00, guest-a -3.02 ± 2.60, 7s-32 -4.94 ± 4.63
- epoch 5: guest-b +1.70 ± 2.85, 8p-32 +1.15 ± 2.32, 9a-32 +0.66 ± 2.78, 1 +0.00 ± 0.00, guest-a -2.35 ± 2.54, 7s-32 -4.94 ± 4.63

**Betting test `9a-32~8p-32`** on every direct board so far (native): 0 boards, K = 1.000 (promote at 20), L = 1.000 (futility at 10), decision None. The controller opens the test only once `9a-32` is admitted and rated above the champion.

## 5. Replay

```
{
 "epoch": 3,
 "k": 524288,
 "pair": "9a-32~guest-a",
 "index": 524288,
 "snapshot": "2f7248b7db3bd27d76b6b59e90031caa3e5232cf046c6177c2d5e5c2f7a4d863",
 "recorded": "d5aa9f57f5b90d4a5b705a0f1d5af90398bbc18337d660923539fd8b7ca49ecf",
 "replayed": "d5aa9f57f5b90d4a5b705a0f1d5af90398bbc18337d660923539fd8b7ca49ecf",
 "manifest_recorded": "181fb93696c7d9029afb64dfcfdf8eb8386700cab2ae286ddd46070eea117152",
 "manifest_replayed": "181fb93696c7d9029afb64dfcfdf8eb8386700cab2ae286ddd46070eea117152",
 "common": [
  1,
  1
 ],
 "native": [
  0,
  0
 ],
 "same": true
}
```
