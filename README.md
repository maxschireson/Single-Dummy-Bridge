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
| Run a Gen 7 collector | [Phase 1 notice: mix, plans and launch steps](docs/gen7_candidate_2026-11-11.md) |
| See what each generation was and how it scored | [Generations](docs/generations/README.md) |
| Decide what needs doing | [Backlog](docs/backlog.md) |
| Work with an agent | [AGENTS.md](AGENTS.md) and [contribution workflow](CONTRIBUTING.md) |

## Current baseline

As of 12 November 2026 the arena runs **Gen 7 phase 1**: Gen 6 fast with a new policy net
(v4) and a shallow tree search at tricks 3–6, cross-matched against Gen 6 fast, BEN and
older bots. Phase 2 (self-play volume) is not authorized. `main` contains the deployed
Gen 7 source (`fe382f9b`) and the Gen 6 source. Gen 6 is closed:
[results](docs/generations/gen6/README.md#results).

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
