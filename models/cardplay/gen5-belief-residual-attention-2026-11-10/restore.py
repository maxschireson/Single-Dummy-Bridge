import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent
for entry in json.loads((root/'manifest.json').read_text())['files']:
    data=bytearray()
    for part in entry['parts']:
        chunk=(root/part['file']).read_bytes()
        assert len(chunk)==part['size_bytes'] and hashlib.sha256(chunk).hexdigest()==part['sha256']
        data.extend(chunk)
    assert len(data)==entry['size_bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256']
    path=root/entry['output'];tmp=path.with_suffix('.tmp');tmp.write_bytes(data);tmp.replace(path)
print('All inference models restored and SHA256 verified.')
