#!/usr/bin/env python3
"""Fetch Stu's round 4c rollout net from the loop's training box branch (it is not kept in git) and check its hash.

  python restore.py            # writes policy.npz next to this file

Trained by the loop session (training/rollout-loop-20261113 on research/rollout-loop-20261113) and published as
train-r4c/policy.npz on transfer/rollout-loop-azure5-20261113. The same file get_net.sh 4c <sha256> puts here.
"""
import hashlib
from pathlib import Path
import subprocess
import tempfile

REPO = 'https://github.com/maxschireson/Single-Dummy-Bridge'
BRANCH = 'transfer/rollout-loop-azure5-20261113'
FILES = {'policy.npz': ('train-r4c/policy.npz', 'e4b689c87db2f56b98221a491757dbf348ddaea066e016f06a9331fc671197f2')}
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
                (HERE / (name + '.tmp')).write_bytes(data)
                (HERE / (name + '.tmp')).replace(HERE / name)
    for name, (_, want) in FILES.items():
        got = sha(HERE / name)
        if got != want:
            raise SystemExit(f'{name}: sha256 {got}, expected {want}')
        print(name, 'ok')


if __name__ == '__main__':
    main()
