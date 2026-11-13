#!/usr/bin/env python3
"""Fetch rollout net v1 from its transfer branch (it is not kept in git here) and check its hashes.

  python restore.py            # writes policy_ft.npz and policy_scratch.npz next to this file

The nets were trained by the plan session (training/rollout-net-v1-20261113/chain.sh) and published on
transfer/rollout-net-v1-20261113 (runs/ft/policy.npz, runs/scratch/policy.npz).
"""
import hashlib
from pathlib import Path
import subprocess
import tempfile

REPO = 'https://github.com/maxschireson/Single-Dummy-Bridge'
BRANCH = 'transfer/rollout-net-v1-20261113'
FILES = {'policy_ft.npz': ('runs/ft/policy.npz', 'b15b5e2be7599b0898d9c9ba9f6bea22075373e726cb06d1ab1fb7f0e60bec3b'),
         'policy_scratch.npz': ('runs/scratch/policy.npz', 'b13349de9fcfaa1c6025678b8fdcc0e76a00dd0ccbc05327a71022da951e7c6c')}
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    need = {k: v for k, v in FILES.items() if not (HERE / k).exists() or sha(HERE / k) != v[1]}
    if need:
        with tempfile.TemporaryDirectory() as tmp:
            run = lambda *a: subprocess.run(['git', '-C', tmp, *a], check=True, capture_output=True)
            run('init', '-q')
            run('fetch', '-q', '--depth=1', REPO, BRANCH)
            for name, (path, _) in need.items():
                data = subprocess.run(['git', '-C', tmp, 'show', f'FETCH_HEAD:{path}'], check=True, capture_output=True).stdout
                (HERE / name).write_bytes(data)
    for name, (_, want) in FILES.items():
        got = sha(HERE / name)
        if got != want:
            raise SystemExit(f'{name}: sha256 {got}, expected {want}')
        print(name, 'ok')


if __name__ == '__main__':
    main()
