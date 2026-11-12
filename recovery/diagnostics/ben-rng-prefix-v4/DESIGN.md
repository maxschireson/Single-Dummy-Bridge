# V4 nonempty-prefix live interruption diagnostic

Seeded an isolated V4 journal with the four accepted records from the previous live V4 test (BEN1082 and self1930/1931/1932). Actual three normal futures and a BEN worker/server then played self1933/1934/1935 and BEN2561. An external parent observed private claim RNG advance before BEN acceptance, killed the collector with SIGKILL, and killed only its dedicated diagnostic process group. Six records were accepted at interruption: the original four plus self1933 and self1934. All six observed child identities became inactive; zombies count as inactive, not reaped.

The original four episode/receipt/RNG/node tuples remained byte-identical, and the six-record accepted prefix survived snapshot/restore unchanged. A fresh process completed pending self1935 and BEN2561, yielding eight accepted records and the exact final claim RNG from V3.1. All eight full replays passed; the actual exporter reports eight records. Four completed records are newly played in this pass, four retained from the preceding diagnostic. No production commits.

Seven of eight captured fingerprints match V3.1; among the four newly completed records, three match. Self1934 has four additional audit nodes versus V3.1. Its root and all 33 common nodes are exact. This does not resolve the prior audit-volume mismatch or satisfy an all-eight exact gate. Historical semantics includes root/gap nodes despite its startswith-gap filter; references were preserved.

The immutable V4 protocol remains e6e29e8c36ba4c18bf7d95b7a34290d251b73704b3baa14a0dfd81e0572805eb. Each child verifies the driver/journal binding. Diagnostic caches were reused from the prior isolated V4 test; production cache and RNG were untouched.

The external supervisor survived and performed cleanup. Supervisor-loss/autonomous orphan cleanup, full-size 8128-record scaling, production scanner integration, and power loss remain untested. Isolated claim RNG is a diagnostic behavior change, not unchanged-production equivalence or recovery of the original dead server RNG. Production65a remains stopped with failure003062 intact; candidate1bd is not promoted.

GitHub main remains62bd8a. The coordination board relays Max's 04:09 instruction to stop Gen7-versus-Gen5/Gen1 and redirect to self-play; its tested successor was still being prepared at this pass's handoff check. Other producers retain ownership; no local65a cutover inferred.
