#!/usr/bin/env python3
"""Write a policy net as a model folder in the repository's chunked form (parts, manifest.json, restore.py).

  python package_net.py POLICY.npz MODEL_DIR OUTPUT_NAME.npz SCORER.npz [METRICS.json]

The same layout as models/cardplay/gen7-policy-v4-2026-11-11: 512 KiB parts with their hashes, and a
restore.py that verifies them and rebuilds the file. README.md is written by hand afterwards.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np

policy, folder, name, scorer = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
metrics = Path(sys.argv[5]) if len(sys.argv) > 5 else None
folder.mkdir(parents=True, exist_ok=True)
data = policy.read_bytes()
sha = lambda b: hashlib.sha256(b).hexdigest()
parts = []
for i in range(0, len(data), 524288):
    chunk = data[i:i + 524288]
    part = f'{name}.part{i // 524288:03d}'
    (folder / part).write_bytes(chunk)
    parts.append(dict(file=part, size_bytes=len(chunk), sha256=sha(chunk)))
with np.load(policy) as f:
    count = int(sum(f[k].size for k in f.files if k not in ('kind', 'bank_length', 'bank_hon', 'bank_log_weight')))
manifest = dict(schema='chunked-gen7-policy-artifact-v1', status='research prototype: no arena bot uses it',
                description="Gen 7 policy net: Gen 6's card from one seat's view (prototype); see README.md",
                parameters=count, scorer_sha256=sha(scorer.read_bytes()),
                files=[dict(output=name, size_bytes=len(data), sha256=sha(data), parts=parts)])
(folder / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
template = Path(__file__).resolve().parents[2] / 'models/cardplay/gen7-policy-v4-2026-11-11/restore.py'
(folder / 'restore.py').write_text(template.read_text().replace('gen7_policy_v4.npz', name))
if metrics:
    shutil.copy(metrics, folder / 'metrics.json')
print(json.dumps(dict(folder=str(folder), output=name, size_bytes=len(data), sha256=sha(data), parts=len(parts), parameters=count)))
