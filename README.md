# Single-Dummy Bridge

A research bridge engine combining learned bidding and hidden-hand inference with double-dummy search and a learned card selector. The project measures changes through paired play, preserves reproducible model/run identities, and publishes an arena dashboard.

**Start here:** [contributor guide](docs/onboarding.md) · [current system](docs/current-system.md) · [generations](docs/generations/README.md) · [backlog](docs/backlog.md) · [arena](https://maxschireson.github.io/Single-Dummy-Bridge/arena/?source=latest)

## Where to begin

| Your goal | Read |
| --- | --- |
| Understand the project in ten minutes | [Onboarding](docs/onboarding.md), then [architecture](docs/architecture.md) |
| Run a small local example | [Quick start](docs/onboarding.md#run-a-small-local-example) |
| Work out which bot/configuration is current | [Current system and authority](docs/current-system.md) |
| Find code, models, data or an old experiment | [Repository map](docs/repository-map.md) and [branch inventory](docs/branch-inventory.md) |
| Operate or recover a collector | [Operations](docs/operations.md) |
| Run a Gen 8 collector | [Notice: what was built and measured, plans and launch steps](docs/gen8_candidate_2026-11-12.md) |
| See what each generation was and how it scored | [Generations](docs/generations/README.md) |
| Decide what needs doing | [Backlog](docs/backlog.md) |
| Work with an agent | [AGENTS.md](AGENTS.md) and [contribution workflow](CONTRIBUTING.md) |

## Current baseline

As of 12 November 2026 the arena runs **Gen 8**: the Gen 7.1 bot with the play read from the
first trick, the opponents' plays read by who they are and each side's calls read by the system
it declares, and a second bot that bids the project's own rule system (Precision). They are
cross-matched against Gen 7.1, BEN and older bots. `main` contains the deployed Gen 8 source
(`792c4cb` and the two collector branches built on it) and the Gen 6 and Gen 7 sources. Gen 7
is closed: [results](docs/generations/gen7/README.md#results).

[Current system](docs/current-system.md) lists the authorities; each run's frozen manifest
takes precedence over prose. Each generation change ends with a
[cleanup](docs/generation-cleanup.md) that closes out the old generation and brings the new
one onto main.

## Repository structure

| Location | Purpose |
| --- | --- |
| `bridge_harness/` | Engine, information boundaries, learned inference, collection and scoring |
| `native/`, `vendor/dds/` | DDS integration and attributed upstream source |
| `configs/` | Versioned experiment and deployment recipes |
| `models/` | Model releases, reconstruction instructions and provenance |
| `scripts/` | Build, training and offline analysis commands |
| `ops/` | Collector preparation, supervision, export and recovery |
| `tests/` | Automated checks |
| `docs/` | Contributor guides, architecture, operations; `docs/generations/` holds one page per generation |
| `reports/` | Dated experimental evidence and validation snapshots |
| `web/` | Dashboard source assets; deployed site is on `gh-pages` |

Result feeds, recovery capsules, transfer datasets and box-control channels live on
separately named branches. They are not development branches and are never merged into main.
[Data and branch guide](docs/repository-map.md).

## Project status

This is active research, not a packaged production release. Offline prediction
or double-dummy gains do not by themselves establish stronger played bridge.
Use the live arena for published observations and exact snapshots for comparisons;
do not infer worker health from an old report marked “running.”

[Documentation index](docs/README.md) · [Credits](CREDITS.md) · [License](LICENSE)
