# Conditional claims: raw result lines (13 November 2026)

Artifact branch. Do not merge into source.

The result lines behind `experiments/sure_tricks/cells/README.md` on `research/conditional-claims-20261113`
(commit `2842075`), gzip-compressed, one JSON object a line. `MANIFEST.json` lists each file with its size, line
count and SHA-256, packed and unpacked. The scripts that wrote and read them are in that folder:

```
gunzip -k dual8_a.jsonl.gz dual8_b.jsonl.gz
python report.py dual8_a.jsonl dual8_b.jsonl
```

Evidence: a solver's analysis of recorded play from `arena-gen8-azure1-feed` (`210f7b2`), weighted by that feed's
hand-fit scorer. No bot has played with any of it.
