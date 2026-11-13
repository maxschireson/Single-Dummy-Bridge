#!/usr/bin/env python3
"""Join built sets into one uncompressed .npz, one array of one part in memory at a time.

  python merge_sets.py OUT.npz PART.npz [PART.npz ...]

Rows keep the order of the parts; deal numbers are shifted so that they index the joined family list, and the
bots' rows (meta columns 8 and 9) are renumbered into the union of the parts' `bot_names`. The result is what
scripts/gen7_build_dataset.py would have written for all the episodes at once.
"""
import json
import sys
import zipfile

import numpy as np

ROWS = ('state', 'order', 'legal', 'ctx', 'auction', 'shown', 'gap', 'owner', 'meta', 'deal')
FIXED = ('bank_length', 'bank_hon', 'bank_log_weight', 'meta_columns')
out, parts = sys.argv[1], sys.argv[2:]
info, families, splits, names = [], [], [], []
for p in parts:
    with np.load(p) as z:
        info.append((len(z['deal']), len(z['family'])))
        families.append(z['family'])
        splits.append(z['deal_split'])
        names.append([str(x) for x in z['bot_names']])
vocab = [''] + sorted({n for part in names for n in part} - {''})
lookup = [np.array([vocab.index(n) for n in part], np.int32) for part in names]
total = sum(rows for rows, _ in info)
with np.load(parts[0]) as z:
    shapes = {k: (z[k].shape[1:], z[k].dtype) for k in ROWS}
    fixed = {k: z[k] for k in FIXED}
with zipfile.ZipFile(out, 'w', zipfile.ZIP_STORED, allowZip64=True) as zf:
    for k in ROWS:
        tail, dtype = shapes[k]
        with zf.open(k + '.npy', 'w', force_zip64=True) as f:
            np.lib.format.write_array_header_2_0(f, dict(descr=np.lib.format.dtype_to_descr(dtype), fortran_order=False, shape=(total, *tail)))
            offset = 0
            for p, (rows, deals), table in zip(parts, info, lookup):
                with np.load(p) as z:
                    x = z[k]
                if k == 'meta':
                    x = x.copy()
                    x[:, 8], x[:, 9] = table[x[:, 8]], table[x[:, 9]]
                if x.shape != (rows, *tail) or x.dtype != dtype:
                    raise SystemExit(f'{p}: {k} is {x.dtype}{x.shape}, expected {dtype}{(rows, *tail)}')
                if k == 'deal':
                    x = (x + offset).astype(dtype)
                f.write(np.ascontiguousarray(x).data)
                offset += deals
    for name, x in (('family', np.concatenate(families)), ('deal_split', np.concatenate(splits)), ('bot_names', np.array(vocab)),
                    *fixed.items()):
        with zf.open(name + '.npy', 'w', force_zip64=True) as f:
            np.lib.format.write_array(f, x, allow_pickle=False)
deals = sum(d for _, d in info)
by = np.bincount(np.concatenate(splits), minlength=3)
print(json.dumps(dict(parts=len(parts), deals=deals, bots=vocab[1:], unique_families=len(set(np.concatenate(families).tolist())), examples=total,
                      deals_by_hash_split=[int(v) for v in by])))
