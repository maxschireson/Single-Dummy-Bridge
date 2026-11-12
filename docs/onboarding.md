# Contributor onboarding

## First ten minutes

1. Read [current system](current-system.md) to identify the active actors and configurations.
2. Read [architecture](architecture.md) for the decision flow and information boundary.
3. Use [repository map](repository-map.md) to find your subsystem.
4. Pick an explicit item from [backlog](backlog.md), or create a scoped issue for new work.
5. Read [CONTRIBUTING](../CONTRIBUTING.md) before changing a run or reporting evidence.

You do not need to digest every research branch. `main` is the shared development
baseline. Frozen collectors keep the exact source and artifacts in their manifests,
even after new development lands.

## Run a small local example

Python 3.11+ is required. Start with a shallow single-branch clone: the repository
also contains large model/data histories on other branches.

```sh
git clone --depth 1 --single-branch --branch main https://github.com/maxschireson/Single-Dummy-Bridge.git
cd Single-Dummy-Bridge
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m bridge_harness generate --count 2 --seed 20261111 --out my_results/onboarding/deals.jsonl
python -m bridge_harness match my_results/onboarding/deals.jsonl --mode partnership --candidate greedy --baseline random --limit 2 --out my_results/onboarding/smoke.jsonl
python -m bridge_harness replay my_results/onboarding/smoke.jsonl
```

This exercises generation, legal play, paired scoring and replay without DDS,
BEN or model downloads. It is a functionality smoke test, not a strength test.
Use a fresh output path on another run; `--resume` requires identical settings.

## Add double-dummy search

Install a C++20 compiler (on macOS, Apple's command-line developer tools), then:

```sh
python scripts/build_dds.py
python -m bridge_harness match my_results/onboarding/deals.jsonl --mode partnership --candidate pimc --baseline greedy --samples 8 --limit 2 --out my_results/onboarding/pimc.jsonl
python -m bridge_harness replay my_results/onboarding/pimc.jsonl
```

## Learned engine and training

```sh
python -m pip install -e '.[loop]'
# Only when working on fitting models or Keras bidding:
python -m pip install -e '.[loop-training]'
```

The minimal CLI's `pimc` player is not a Gen6 actor. Gen6 is instantiated through
the arena runtime with frozen model artifacts and a complete actor spec. Follow
[operations](operations.md) and the [release READMEs](../models) for restoration;
do not improvise missing model paths or launch a new live run just to test setup.
BEN is a separate runtime with its own source, models and configuration.

For a dependency-light rules check:

```sh
PYTHONPATH=tests:. python -m unittest test_system.CoreTests -v
```

After installing the relevant dependencies and building DDS, the broader suite is:

```sh
python -m unittest discover -s tests -v
```

Some tests exercise native DDS, learned inference or runtime integrations; report
missing dependencies separately from test failures. Do not call a smoke test a full
Gen6 validation.

## Terminology

| Term | Meaning |
| --- | --- |
| DDS / double dummy | Solver that sees a sampled complete deal |
| Single dummy | Acting player knows only its legal observation |
| PIMC | Score candidate cards across sampled complete deals with DDS |
| Belief / scorer | Estimate which hidden layouts fit the observed auction and play |
| Policy | Learned choice among eligible cards; active Gen6 uses ties only |
| Common auction | Shared bidder condition used to isolate cardplay comparisons |
| Native auction | Each partnership uses its own bidder |
| Deal family | Unit used to preserve related data splits and avoid duplicate evidence |
| Feed | Published observations and recovery artifacts, not source to merge |
