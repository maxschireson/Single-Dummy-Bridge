# Gen7.1 authoritative training-family audit, 12 November2026

The model owner published the exact v4.1 training-family list at `transfer/gen7-policy-v4.1-families-20261112`, commit `1132bcf0aec10f8c4b16e2290d3f2bc01ea4567e`:34,029 families. The earlier conservative feed reconstruction had32,205;32,142 are shared,1,887 are newly identified, and63 earlier exclusions remain conservative additions. The promotion checker now uses their union (34,092), with the authoritative file's hash pinned in the mutable cutover/control metadata. The original32,205-family file and all earlier reports remain unchanged.

Both the complete frozen11,109-family evaluation corpus and the completed subset have zero overlap with the authoritative list. Consequently no play/model/allocation changes, corpus rewrite or new collection cohort are needed. The controller, actor, artifact, corpus and manifest hashes remain valid.

The13:53 checkpoint was independently recomputed from exactly its recorded feed commits using the expanded filter. Its4,276 families, mean and confidence interval are unchanged; no source errors occurred. The accompanying JSON contains the original and rechecked gate statistics, authoritative blob SHA-256, overlap audit and latest gate snapshot. The current promotion gate remains false. As before, the gate requires >=1,000 independent fresh native comparisons AND a positive nominal95% lower endpoint, with no source errors.

Two targeted gate tests pass, including additive union and rejection of a changed authority file. Collection and publication remain live; no other collector is changed.
