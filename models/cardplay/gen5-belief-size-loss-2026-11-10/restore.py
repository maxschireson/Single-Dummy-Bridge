"""Restore all four inference exports from verified 512 KiB parts."""
import hashlib,json
from pathlib import Path

def main():
    root=Path(__file__).resolve().parent
    manifest=json.loads((root/'manifest.json').read_text())
    for entry in manifest['files']:
        output=root/entry['output'];temporary=output.with_suffix('.tmp')
        with temporary.open('wb') as stream:
            for spec in entry['parts']:
                raw=(root/spec['file']).read_bytes()
                if len(raw)!=spec['size_bytes'] or hashlib.sha256(raw).hexdigest()!=spec['sha256']:
                    raise ValueError('Bad part: '+spec['file'])
                stream.write(raw)
        raw=temporary.read_bytes()
        if len(raw)!=entry['size_bytes'] or hashlib.sha256(raw).hexdigest()!=entry['sha256']:
            raise ValueError('Bad reconstructed model: '+entry['cell'])
        temporary.replace(output)
    print('All four model exports restored and SHA256-verified.')

if __name__=='__main__':main()
