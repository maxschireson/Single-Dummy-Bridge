"""Verify chunk hashes and reconstruct gen7_policy_v4.npz."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    for spec in manifest['files']:
        output = ROOT / spec['output']
        temporary = output.with_suffix(output.suffix + '.tmp')
        with temporary.open('wb') as destination:
            for part in spec['parts']:
                source = ROOT / part['file']
                if source.stat().st_size != part['size_bytes'] or sha(source) != part['sha256']:
                    raise ValueError('Part verification failed: ' + part['file'])
                destination.write(source.read_bytes())
        if temporary.stat().st_size != spec['size_bytes'] or sha(temporary) != spec['sha256']:
            raise ValueError('Reconstructed file verification failed: ' + spec['output'])
        temporary.replace(output)
    print(json.dumps({'status': 'all-checksums-verified', 'files': [s['output'] for s in manifest['files']]}, indent=2))


if __name__ == '__main__':
    main()
