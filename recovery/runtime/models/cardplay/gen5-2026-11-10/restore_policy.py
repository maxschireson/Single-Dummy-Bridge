from pathlib import Path
import json, hashlib
root=Path(__file__).resolve().parent
m=json.loads((root/'manifest.json').read_text())
b=b''.join((root/p).read_bytes() for p in m['parts'])
assert len(b)==m['size_bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
p=root/m['output']
if p.exists() and p.read_bytes()!=b:raise ValueError('Refusing to replace different weights')
p.write_bytes(b)
print(p)
