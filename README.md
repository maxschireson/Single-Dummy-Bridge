# Added: older Gen 2 / Gen 3 training data

Run this in addition to the original restore command below:

    python restore_legacy.py --output /workspace/non-v4-policy-legacy

Use --group gen2-gen3 to restore only the older model data, or --group pimc for only the raw baseline play. The default restores both groups.

Verified additions:

- **1,913 Gen 2 / Gen 3 era deal families:** 21,413 policy rows and 197,838 belief rows, in five disjoint increments from transfer/gen3-training-feed pinned at 3ddf598944dee097a530c2dd2c3804627fb26bad. All participating policies have SHA256 8c62c88b0f2041ce78273e072d0b5530598255cc39b482826901ff1660e064f5 (Gen3) or 02b6885e8f07da473970052d7f9ea9dc2a10fa34505ad60186e4a14d02218c60 (prior selector/Gen2). None uses the Gen4 policy.
- **9,000 original plain-PIMC self-play games:** full compressed episodes, original manifests, outcomes, logged probabilities and estimates for 369,184 non-forced decisions. This is an additional baseline dataset, not mislabeled Gen2 or Gen3 play. GitHub Actions artifacts and original commit IDs are recorded in each transfer manifest. Every game was replayed to its final score.
- No canonical families overlap between these two additions or the preceding 972-family export. Together the available groups contain 11,885 distinct families. Additional trajectories and tensor rows do not increase that count.

The Gen2/Gen3 policy tensors include the PIMC q values and complete model inputs. Their y target is an **audited chosen-minus-reference IMP contrast**, not observed remaining tricks. Keep them as a separate loss/dataset if training a predictive trick policy; do not reinterpret y as tricks. The raw PIMC games and the original 1,944 games below provide chosen-action trick outcomes for the Gen3-style predictive recipe. The legacy belief tensors are included unchanged for future use.

All part, archive and tensor checksums were verified. Original files, schema manifests, source hashes and family splits are retained. The legacy raw PIMC data retains its original train/validation/test membership. Preserve that membership when assessing held-out strength; a family used for fitting is no longer independent evaluation evidence.

The additions are under legacy/. Exact counts, active policy hashes and source IDs are in legacy/manifest.json. Increments snapshot-0006 onward are intentionally omitted because they introduced Gen4 policy records. The original stopped 8,315-board v2 collection and the old 3,700-board migration ZIP are not available in this environment or the reachable repository; this package does not claim those absent raw archives. Their eligible records can be appended if the original archives are recovered.

---

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
