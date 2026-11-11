"""Verify the exact, pinned receipts carried through a runtime-only transition."""
import json
from bridge_harness.loop_registry import sha


def verify_retained(root, manifest):
    if not manifest.get('retained_receipts'):
        return {}
    path = root / manifest['retained_receipts']
    if sha(path) != manifest['retained_receipts_sha256']:
        raise ValueError('Changed retained receipt inventory')
    inventory = json.loads(path.read_text())
    for name, checksum in inventory.items():
        if sha(root / 'receipts' / name) != checksum:
            raise ValueError('Changed retained receipt: ' + name)
    return inventory


def allowed_identity(manifest, identity):
    return identity == manifest['identity'] or identity in manifest.get('retained_manifests', [manifest.get('retained_manifest')])
