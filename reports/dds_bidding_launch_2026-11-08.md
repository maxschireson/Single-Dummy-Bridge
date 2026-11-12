# DDS bidding loop launch validation — 8 November 2026

Implemented a separate neural-only bidding campaign initialized from external
BEN `GIB-BBO-8742_2026-10-23-E30.keras`. Learning uses paired duplicate IMP rewards
from complete DDS tables, PPO updates to both partners, a frozen opponent league,
and development/confirmation gates. There are no real card-play results in the
reward. See [the implementation and run guide](../docs/dds_bidding_loop.md).

## Evidence before launch

- External BEN compatibility audit: **64 complete auctions, 656 decisions**;
  feature arrays, legal-call masks and network probabilities match exactly.
- Identical greedy BEN bidders: **8 duplicate pairs, all zero IMPs**.
- DDS tables: full-suit analytic positions checked, plus five strain/declarer
  entries on a random deal cross-checked with independent opening-lead solves.
- PPO test: rewarding a call increases its probability; saving and loading
  restores model predictions and every Adam optimizer variable.
- Real-model smoke campaign: interrupted after eight training pairs, resumed
  from its saved optimizer checkpoint, and completed **32 training pairs** and
  two eight-deal development screens. Both screens tied and correctly caused
  no promotion. These tiny screens are plumbing checks, not strength evidence.
- Full existing-and-new test suite passed before launch; exact console counts
  are reported in the launch response. No logs or training data enter this commit.

Eight full DDS tables took 1.90 seconds on one persistent solver context
(0.237 seconds/deal). This is a small microbenchmark; end-to-end training includes
auction inference, gradient updates, checkpoint I/O and two solver workers.

## Campaign settings

Training stages: 10,000 / 50,000 / 250,000 unique training deals per candidate
attempt, with 128 paired deals per update batch. Each pair contains two auctions.
Development: 1,000 fresh pairs. Confirmation: 10,000 fresh pairs if the screen
is positive. Successful candidates are archived as B1, B2, etc. The initial
campaign is capped at 20 candidate attempts and supports interruption/resumption.

No bidding improvement has been established at launch. The first substantive
strength result will be the 10,000-deal candidate's held-out evaluation.
