#!/usr/bin/env python3
"""Keep the deals of a built set whose family is in none of the reference sets, and mark them all held out.

  python fresh_set.py BUILT.npz OUT.npz REFERENCE.npz [REFERENCE.npz ...]

Policy 4.1 holds no deal back: its held-out rows are boards that reached the feeds after the training set was
fetched. A later board can repeat an earlier deal (two runs drawing on one capsule), so those are dropped here.
"""
import json
import sys

import numpy as np

src, out, refs = sys.argv[1], sys.argv[2], sys.argv[3:]
seen = set()
for r in refs:
    with np.load(r) as z:
        seen.update(z['family'].tolist())
with np.load(src) as z:
    d = {k: z[k] for k in z.files}
family = d['family']
keep = np.array([f not in seen for f in family.tolist()], bool)
rows = keep[d['deal']]
index = np.cumsum(keep) - 1
o = {k: d[k][rows] for k in ('state', 'order', 'legal', 'ctx', 'auction', 'shown', 'gap', 'owner', 'meta')}
o['deal'] = index[d['deal'][rows]].astype(np.int32)
o['family'] = family[keep]
o['deal_split'] = np.ones(int(keep.sum()), np.int8)
for k in ('bank_length', 'bank_hon', 'bank_log_weight', 'meta_columns'):
    o[k] = d[k]
np.savez(out, **o)
print(json.dumps(dict(deals_in=len(family), deals_kept=int(keep.sum()), dropped_as_seen=int((~keep).sum()), examples=int(rows.sum()))))
