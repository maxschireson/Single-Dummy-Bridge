# Policy-clean play export for Gen 3 style training

Snapshot: 2026-11-09 23:28:22 UTC. This is a fixed export of all eligible complete local records available at that cutoff.

- 1,944 complete games, 972 distinct canonical deal families.
- 80,305 actions with original per-card PIMC estimates; 64,914 eligible policy decisions.
- 767 training families, 205 validation families, retaining the source split.
- Both partnerships avoid the Gen4 policy artifact. Includes 4b-vs-3 and 3-vs-2 games, plus the clean 4b-vs-3 games from the initial matched diagnostic. Gen4 belief is allowed. Gen4 and 4p games are excluded.
- All games were legally replayed and final scores verified. Missing PIMC fields occur only on forced/fixed actions. Original estimates, candidate support, behavior probabilities, chosen cards, outcomes, auctions and public play history are preserved.

## Restore

Clone this branch and run:

    python restore.py --output /workspace/non-v4-policy-play

Restoration uses only Python's standard library. Every archive part, the joined archive and all extracted files are verified with SHA256. The archive has no credentials, caches, running processes or trained Gen4 policy weights.

## What ChatGPT should ingest

Each runs/RUN/manifest.json is the exact original run manifest. Its episodes/*.json.gz files are unmodified complete per-room random-fork-audit-v1 game dictionaries extracted from the clean source records, flattened so the Gen3 preparer can read them directly. They are not dashboard-only replays: full decision estimates and probabilities remain present.

The original manifest includes unused bot specs for provenance; that does not mean those bots played an exported game. provenance.json explicitly records each game's active actor-to-bot mapping, active policy hashes, source file SHA256, source game path, family and split. In the mix Q means 4b. All exported active policy hashes differ from e179a71ed132dcd0f9ca06b486ec087e9f5b26edb4210e99ed2e04c9439b21ed.

export.json contains counts and selection rules. family-splits.json keeps every room/view of a family together. FILE_SHA256.json verifies every payload file. There are 972 source deals and 1,944 rooms, not 1,944 independent training families. These frozen deals overlap the original arena cohort: merge by canonical family and do not duplicate old training experience.

## Gen 3 recipe reference

recipe-source/scripts/prepare_policy_bootstrap.py and train_policy_bootstrap.py are the historical predictive auction-aware policy recipe, with their Python module dependencies included. The policy inputs use public observations, auction/history, and the logged PIMC estimates. The regression target is observed remaining acting-partnership tricks for the chosen action. Unplayed actions have no outcome label. The preparer samples up to 16 eligible positions per trajectory, deduplicates trajectories, and uses uniform-target correction only when behavior has full support; deterministic logged policies remain partial-coverage predictive examples.

sources.relative.json lists the two clean episode directories. Convert those paths to absolute paths before giving them to the preparer. Preserve these family splits AND all parent/legacy training-family exclusions from your existing data. The historical preparer requires the legacy training shards (--legacy) to protect those exclusions; this upload does not claim to contain that older dataset or all other environments' records. This export does not fit a network or change a deployed model.

The later Gen4 audited-IMP-contrast trainer is a different objective. These games provide Gen3-style predictive play data, not invented IMP contrasts.
