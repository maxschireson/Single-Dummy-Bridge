# The arrival run: /home/claude/g9data/rehearsal/control

Epochs played: [1, 2, 3]. Boards: 72. Guests: ['guest-a'].

## 1 and 3. The player model at the table

`9a-32` against the guest minus `8p-32` against the same guest, on the same deals (the floor), IMPs a board from the bot's side.

| Guest | Epoch | Deals | Native: mean (SE) | Common: mean (SE) |
| --- | --- | ---: | --- | --- |
| guest-a | 2 | 6 | +0.333 (0.211) | -3.333 (3.333) |
| guest-a | 3 | 6 | +1.000 (1.000) | +0.167 (0.167) |
| guest-a | all | 12 | +0.667 (0.497) | -1.583 (1.676) |

## 2. What experience adds

What each epoch's bots were handed for each guest (the snapshot frozen when the previous epoch closed), read as the Gen 9 bot reads it.

| Guest | Epoch | Boards in the snapshot | P(card) as read | Honesty as read | Play factor | Snapshot = envelopes of earlier epochs |
| --- | --- | ---: | ---: | ---: | --- | --- |
| guest-a | 2 | 0 | 0.791 | — (prior) | — | yes |
| guest-a | 3 | 23 | 0.984 | 0.694 | — | yes |
| guest-a | 4 | 44 | 0.984 | 0.648 | — | yes |

## 4. The arena

**Registry events**

- seq 6 `submit` guest-a (epoch 2): G9-D6 rehearsal: guest-a arrives before epoch 2 first model card: 0.791, flat: 0.198, house-dds40k: 0.004, house-gen5: 0.004, house-gen6: 0.003

**Share of boards by epoch**

| Epoch | guest-a |
| --- | ---: |
| 1 | 0% |
| 2 | 50% |
| 3 | 50% |

**Ratings (native) at the close of each epoch, IMPs a board against the reference, 95% half-width**

- epoch 1: 8p-32 +2.40 ± 3.36, 7s-32 +1.15 ± 4.62, 9a-32 +0.57 ± 3.30, 1 +0.00 ± 0.00, 5RZ32 -0.17 ± 4.79
- epoch 2: 5RZ32 +4.82 ± 4.13, 9a-32 +1.01 ± 2.77, 7s-32 +0.76 ± 3.52, 8p-32 +0.50 ± 2.50, 1 +0.00 ± 0.00, guest-a -0.34 ± 3.03
- epoch 3: 5RZ32 +4.05 ± 3.48, 9a-32 +1.10 ± 2.60, 7s-32 +0.78 ± 3.52, 8p-32 +0.59 ± 2.35, 1 +0.00 ± 0.00, guest-a -0.07 ± 2.68

**Betting test `9a-32~8p-32`** on every direct board so far (native): 3 boards, K = 1.000 (promote at 20), L = 0.982 (futility at 10), decision None. The controller opens the test only once `9a-32` is admitted and rated above the champion.

## 5. Replay

```
{
 "epoch": 3,
 "k": 524288,
 "pair": "9a-32~guest-a",
 "index": 524288,
 "snapshot": "fd3ae8dfbf0751cc8264dcd7740f9f231a178a7124da89908388bc1708627aed",
 "recorded": "7527e36257e6ddceadb197d4e65852fa90ebd0958462c790f5653750b942826e",
 "replayed": "7527e36257e6ddceadb197d4e65852fa90ebd0958462c790f5653750b942826e",
 "manifest_recorded": "7a1757e1c81486078f0a982a9d3e71d3a3ea34e95d26d6147b2aa40ad0f6dd4b",
 "manifest_replayed": "7a1757e1c81486078f0a982a9d3e71d3a3ea34e95d26d6147b2aa40ad0f6dd4b",
 "common": [
  0,
  0
 ],
 "native": [
  -1,
  -1
 ],
 "same": true
}
```
