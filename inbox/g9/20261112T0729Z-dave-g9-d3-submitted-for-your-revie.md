G9-D3 submitted for your review: Rating table fitted to the published Gen 5 to Gen 7 feeds

dave, 12 Nov 07:29 UTC. Task G9-D3.

PR #21 (stacked on #17). ratings-v1 for native and for common under each common bidder (Gen 5's and Gen 6's networks differ, so common results are two conditions). 60,966 records from the 62 registry sources and the 5 Gen 5 feeds outside the registry. Every pair reproduced within its 95% interval (64); none out of line after Holm (59 testable, 1 raw p<0.05); detectable pair effects 0.3-1.2 IMPs, smaller ones not excluded. The out-of-line test re-estimates t2 without the pair under test (a planted 1.0 effect hid itself otherwise). Also found: identities hash artifact paths (1 and 5RZ32 each have two identities for the same artifacts); ben64 has two BEN configs under one id.

Branch: feature/gen9-arena-ratings, commit ce77aeb.

Accept: `workq.py resolve G9-D3 --resolution accepted`. Send back: `workq.py reopen G9-D3 --note ...` (add `--same-holder` to return it to dave).
