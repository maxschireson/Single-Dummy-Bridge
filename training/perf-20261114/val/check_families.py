#!/usr/bin/env python3
"""Fail if a training set holds a deal family that a frozen validation set reserves.

    check_families.py --exclude v1_families.txt [--exclude more.txt] SET.npz [SET.npz ...]

SET.npz: any rows file of scripts/gen7_build_dataset.py, or one joined by merge_sets.py / sample_set.py (they keep
`family` per deal and `deal` per row). Only the families of deals that have rows count. Exit status 1 and the
offending families on a hit, 0 and a one-line summary per file otherwise. For round scripts: run it on train.npz (and
on replay.npz or any part) before training, and stop the round on a non-zero exit.
"""
import argparse
import sys
import zipfile

import numpy as np


def families_used(path):
    with zipfile.ZipFile(path) as z:
        names = {n[:-4] for n in z.namelist()}
    if 'family' not in names or 'deal' not in names:
        raise SystemExit(f'{path}: no family/deal arrays')
    z = np.load(path, mmap_mode='r')
    deal = np.asarray(z['deal'])
    fam = np.asarray(z['family'])
    used = np.unique(deal)
    return {str(f) for f in fam[used]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exclude', action='append', required=True)
    ap.add_argument('sets', nargs='+')
    a = ap.parse_args()
    reserved = set()
    for f in a.exclude:
        reserved |= {ln.split()[0] for ln in open(f) if ln.strip() and not ln.startswith('#')}
    bad = 0
    for path in a.sets:
        used = families_used(path)
        hit = sorted(used & reserved)
        print(f'{path}: {len(used)} families, {len(hit)} reserved', flush=True)
        for h in hit[:20]:
            print(f'  reserved family in training data: {h}')
        bad += len(hit)
    if bad:
        print(f'FAIL: {bad} reserved families in the training data', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
