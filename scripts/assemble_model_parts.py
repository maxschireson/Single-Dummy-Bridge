"""Assemble a chunked experimental checkpoint and verify its manifest hashes."""
import argparse,hashlib,json
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args()
    m=json.loads((a.directory/'manifest.json').read_text());chunks=[]
    for part in m['parts']:
        raw=(a.directory/part['file']).read_bytes()
        if len(raw)!=part['size'] or hashlib.sha256(raw).hexdigest()!=part['sha256']:raise ValueError('Invalid part: '+part['file'])
        chunks.append(raw)
    raw=b''.join(chunks)
    if len(raw)!=m['size'] or hashlib.sha256(raw).hexdigest()!=m['sha256']:raise ValueError('Invalid checkpoint')
    path=a.directory/m['filename']
    if path.exists() and path.read_bytes()!=raw:raise ValueError('Refusing to replace a different checkpoint')
    path.write_bytes(raw);print(path)
if __name__=='__main__':main()
