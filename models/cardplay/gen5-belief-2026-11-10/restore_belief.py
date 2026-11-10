"""Restore the promoted dense v5 belief component from checked 512 KiB parts."""
import hashlib
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / 'manifest.json').read_text())
    data = bytearray()
    for part in manifest['parts']:
        chunk = (root / part['file']).read_bytes()
        if len(chunk) != part['size_bytes'] or hashlib.sha256(chunk).hexdigest() != part['sha256']:
            raise ValueError('Invalid model part: ' + part['file'])
        data.extend(chunk)
    if len(data) != manifest['size_bytes'] or hashlib.sha256(data).hexdigest() != manifest['sha256']:
        raise ValueError('Reconstructed model does not match the promoted checkpoint')
    output = root / manifest['output']
    temporary = output.with_suffix('.tmp')
    temporary.write_bytes(data)
    temporary.replace(output)
    print('Dense v5 belief restored and SHA256 verified: ' + str(output))


if __name__ == '__main__':
    main()
