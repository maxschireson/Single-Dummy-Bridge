"""Restore the Gen 6 candidate bidder and verify every chunk and the final artifact."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
model = json.loads((root / 'manifest.json').read_text())['model']
parts = []
for part in model['chunks']:
    data = (root / part['file']).read_bytes()
    assert len(data) == part['bytes']
    assert hashlib.sha256(data).hexdigest() == part['sha256']
    parts.append(data)
data = b''.join(parts)
assert len(data) == model['bytes']
assert hashlib.sha256(data).hexdigest() == model['sha256']
target = root / model['file']
target.write_bytes(data)
print(target)
