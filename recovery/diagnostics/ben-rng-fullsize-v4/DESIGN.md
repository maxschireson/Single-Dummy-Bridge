# V4 full-size storage diagnostic — 12 November 2026

This uses the unchanged V4 journal in its existing synthetic-scaling mode. The
real-record protocol remains e6e29e8c36ba4c18bf7d95b7a34290d251b73704b3baa14a0dfd81e0572805eb.
The synthetic protocol has a distinct identity, recorded in result.json.

Each payload contains byte-for-byte archived gzip episode data followed by a
unique synthetic gzip member. All 2,015 production episode templates are cycled
in sorted filename order. These are opaque storage fixtures, not valid newly
played episode JSON. The private _append storage primitive is exercised; the
real validator is deliberately not used. Synthetic export is rejected. Every
thirteenth index advances a private Python RNG once; this is not BEN inference.

8,128 entries stored 1,302,896,731 payload bytes in 25,011 content-addressed
objects totaling 1,313,083,526 bytes. A snapshot captured 2,015 accepted entries
while the writer continued. Fresh-process continuation reproduced the identical
head, RNG and entire sorted object inventory at 8,128, then accepted entry 8,129.
Full read took 6.54 seconds, CURRENT remained 275 bytes, observed peak RSS was
1,382,584 KiB. Full reads retain payloads in memory: this memory cost remains
relevant when combined with live workers.

All frozen files, 2,015 production pairs, 656 retained receipts and failure003062
were reverified afterward. No production launch, RNG change, failure clearance,
new game, actual exporter integration, crash/powerloss test or cleanup test. The
self1934 fingerprint discrepancy is unresolved; the equivalence gate is intact.

Reproduction: run probe.py from the restored checkout with its local venv. The
unique /tmp work directory must be absent. It removes only its own generated
synthetic payloads after all checks; driver, 2,015 template hashes, result and
log are retained. Original archive records and prior diagnostic evidence remain.

Next: robust process ownership/cleanup and accepted-marker-only scanner
integration, plus real-record pipeline scaling. No production adoption.
