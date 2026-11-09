"""Reassemble and verify the experimental belief+ checkpoint from GitHub parts."""
import argparse,hashlib,json
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=Path(__file__).resolve().parents[1]/'models/cardplay/belief-plus-2026-11-09');a=p.parse_args()
    m=json.loads((a.directory/'manifest.json').read_text());chunks=[]
    for part in m['parts']:
        raw=(a.directory/part['file']).read_bytes()
        if len(raw)!=part['size'] or hashlib.sha256(raw).hexdigest()!=part['sha256']:raise ValueError('Invalid model part: '+part['file'])
        chunks.append(raw)
    raw=b''.join(chunks)
    if len(raw)!=m['size'] or hashlib.sha256(raw).hexdigest()!=m['sha256']:raise ValueError('Reassembled checkpoint mismatch')
    path=a.directory/m['filename']
    if path.exists() and path.read_bytes()!=raw:raise ValueError('Refusing to replace a different checkpoint')
    path.write_bytes(raw);print(path)
if __name__=='__main__':main()
