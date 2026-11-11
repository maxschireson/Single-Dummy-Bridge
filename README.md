# Single-Dummy Bridge

A research bridge engine combining learned bidding and hidden-hand inference with double-dummy search and a learned card selector. The project measures changes through paired play, preserves reproducible model/run identities, and publishes an arena dashboard.

**Start here:** [contributor guide](docs/onboarding.md) · [current system](docs/current-system.md) · [backlog](docs/backlog.md) · [arena](https://maxschireson.github.io/Single-Dummy-Bridge/arena/?source=latest)

## Where to begin

| Your goal | Read |
| --- | --- |
| Understand the project in ten minutes | [Onboarding](docs/onboarding.md), then [architecture](docs/architecture.md) |
| Run a small local example | [Quick start](docs/onboarding.md#run-a-small-local-example) |
| Work out which bot/configuration is current | [Current system and authority](docs/current-system.md) |
| Find code, models, data or an old experiment | [Repository map](docs/repository-map.md) and [branch inventory](docs/branch-inventory.md) |
| Operate or recover a collector | [Operations](docs/operations.md) |
| Decide what needs doing | [Backlog and PR dispositions](docs/backlog.md) |
| Work with an agent | [AGENTS.md](AGENTS.md) and [contribution workflow](CONTRIBUTING.md) |

## Current baseline

As of 11 November 2026, `main` includes the Gen6 source previously maintained on
`codex/launch-gen6-20261111`. Gen6 uses the graded-alternative bidder, a lead-belief
network, a hand-fit scorer, DDS, and the retained Gen5 policy for PIMC ties.
Fast and medium are different compute profiles; **medium plays BEN16**.

The exact [active mix](configs/gen6-active-mix.json), [primary configuration](configs/round6-codex.json),
and each run's frozen manifest take precedence over old launch prose.
The general `configs/round6.json` is an earlier staging recipe, not the active primary plan.
See [current system](docs/current-system.md) for the profiles and evidence limits.

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
| `docs/` | Contributor guides, architecture, operations and historical designs |
| `reports/` | Dated experimental evidence and validation snapshots |
| `web/` | Dashboard source assets; deployed site is on `gh-pages` |

Result feeds, recovery capsules and transfer datasets live on separately named
branches. They are not development branches or independent sources of extra boards.
[Data and branch guide](docs/repository-map.md).

## Project status

This is active research, not a packaged production release. Offline prediction
or double-dummy gains do not by themselves establish stronger played bridge.
Use the live arena for published observations and exact snapshots for comparisons;
do not infer worker health from an old report marked “running.”

[Documentation index](docs/README.md) · [Credits](CREDITS.md) · [License](LICENSE)
