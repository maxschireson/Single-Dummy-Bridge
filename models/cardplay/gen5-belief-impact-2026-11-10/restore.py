"""Verify chunk hashes and reconstruct the selected inference/checkpoint files."""
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
    manifest = json.loads((ROOT/'manifest.json').read_text())
    for spec in manifest['files']:
        output = ROOT/spec['output']
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix+'.tmp')
        with temporary.open('wb') as destination:
            for part in spec['parts']:
                source = ROOT/part['file']
                if source.stat().st_size != part['size_bytes'] or sha(source) != part['sha256']:
                    raise ValueError('Part verification failed: '+part['file'])
                with source.open('rb') as stream:
                    for block in iter(lambda: stream.read(1 << 20), b''):
                        destination.write(block)
        if temporary.stat().st_size != spec['size_bytes'] or sha(temporary) != spec['sha256']:
            raise ValueError('Reconstructed file verification failed: '+spec['output'])
        temporary.replace(output)
    index = manifest['checkpoint_index']; path = ROOT/index['file']
    if path.stat().st_size != index['size_bytes'] or sha(path) != index['sha256']:
        raise ValueError('Checkpoint index verification failed')
    print(json.dumps({'status':'all-checksums-verified','selected_epoch':manifest['selected_epoch']},indent=2))

if __name__ == '__main__':
    main()
