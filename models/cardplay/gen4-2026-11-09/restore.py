import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent
m=json.loads((root/'manifest.json').read_text())
for name,entry in m['artifacts'].items():
    chunks=[]
    for part in entry['parts']:
        b=(root/part['path']).read_bytes()
        assert len(b)==part['size'] and hashlib.sha256(b).hexdigest()==part['sha256']
        chunks.append(b)
    b=b''.join(chunks)
    assert len(b)==entry['size'] and hashlib.sha256(b).hexdigest()==entry['sha256']
    (root/name).write_bytes(b)
    print(name,len(b),entry['sha256'])
