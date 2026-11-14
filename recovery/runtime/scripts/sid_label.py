#!/usr/bin/env python3
"""Label recorded decisions with the exact line finder's answers (experiments/sid_loop/SPEC.md, Part A).

  python scripts/sid_label.py --episodes DIR --out DIR --cells BIN --scorer hand_fit_v0.npz
                              [--cards 7] [--workers 8] [--full] [--limit N] [--mass 0.99] [--maxnodes 20000000]

DIR holds *.json.gz episode files, as scripts/gen7_build_dataset.py reads them. For every decision that builder keeps
with --policy-only in which the actor holds --cards or fewer cards, one row of labels (see
experiments/sid_loop/sidlabel.py for what they are). One sidecar file per episode, OUT/<episode name>.npz:

  key [m, 3]        (entry of unique_tables in file order, table, action): the row's place in the episode
  role, held [m]    0 declaring side / 1 defender; cards the actor holds
  slots [m, 8]      the legal cards in rising order (-1 beyond them); the label arrays follow these slots
  need [m, 3]       tricks the declaring side still needs for one down, the contract, an overtrick
  guar, single, cert [m, 8, 3] int8   per slot and target; -1 = no label
  floor, ceil [m, 8, 3] float16       NaN = none
  ms, nodes [m]     wall time and solver nodes of the row

The run can be stopped and started again: an episode with a sidecar is not labelled twice. OUT/manifest.json records
what the labels were made with; a second run with other settings into the same OUT is refused. OUT/stats.jsonl has one
line per episode (rows, seconds, cost by cards held and role), OUT/errors.jsonl the episodes that failed.
--full also labels the other cards where some card guarantees a target outright (for scoring a student; the
training labels leave them unasked, as the specification's cost assumes).
"""
import argparse
import gzip
import hashlib
import json
from multiprocessing import Pool
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments' / 'sid_loop'))

LAB = None
OUT = None


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def start(cells, scorer, cards, mass, maxnodes, full, out):
    global LAB, OUT
    import sidlabel
    LAB = sidlabel.Labeller(cells, scorer, cards=cards, mass=mass, maxnodes=maxnodes, full=full)
    OUT = Path(out)


def label(path):
    import sidlabel
    name = path.name[:-len('.json.gz')]
    t0 = time.time()
    try:
        with gzip.open(path, 'rt') as f:
            d = json.load(f)
        before = dict(LAB.count)
        rows = LAB.episode(d)
        arrays = sidlabel.pack(rows)
        tmp = OUT / (name + '.tmp.npz')
        np.savez_compressed(tmp, **arrays, family=np.array(d.get('family') or ''))
        tmp.replace(OUT / (name + '.npz'))
        by = {}
        for h in range(1, 14):
            for r, role in enumerate(('declaring', 'defender')):
                m = (arrays['held'] == h) & (arrays['role'] == r)
                if m.any():
                    by[f'{h} {role}'] = [int(m.sum()), round(float(arrays['ms'][m].sum()), 1), int(arrays['nodes'][m].sum())]
        return dict(episode=name, rows=len(rows), seconds=round(time.time() - t0, 3), by=by,
                    capped=LAB.count['capped'] - before['capped'], positions=LAB.count['positions'] - before['positions'])
    except Exception as err:                                    # one bad episode must not stop the run
        try:
            LAB.restart()                                       # the solver may hold half a question
        except Exception:
            pass
        return dict(episode=name, error=repr(err), trace=traceback.format_exc()[-1500:], seconds=round(time.time() - t0, 3))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--episodes', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--cells', type=Path, required=True)
    p.add_argument('--scorer', type=Path, required=True)
    p.add_argument('--cards', type=int, default=7)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--mass', type=float, default=.99)
    p.add_argument('--maxnodes', type=int, default=20_000_000)
    p.add_argument('--full', action='store_true')
    p.add_argument('--limit', type=int, default=0)
    p.add_argument('--stride', type=int, default=1, help='with --offset: label every stride-th episode (a sample by deal)')
    p.add_argument('--offset', type=int, default=0)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    try:
        commit = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = ''
    manifest = dict(schema='sid-labels-v1', cards=a.cards, targets=[-1, 0, 1], w_src='scorer', mass=a.mass, named=0, full=a.full,
                    solver='experiments/sure_tricks/cells/cells.cpp', solver_flags=['--def', 'ends', '--maxnodes', str(a.maxnodes)],
                    solver_sha256=sha256(a.cells), solver_source_sha256=sha256(ROOT / 'experiments/sure_tricks/cells/cells.cpp'),
                    scorer_sha256=sha256(a.scorer), must='every run (declaring rows)', slots=8)
    mf = a.out / 'manifest.json'
    if mf.exists():
        old = json.loads(mf.read_text())
        if {k: old.get(k) for k in manifest} != manifest:
            raise SystemExit(f'{mf} was made with other settings; use another --out')
    else:
        mf.write_text(json.dumps(dict(manifest, repo_commit=commit, started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())), indent=1))
    files = sorted(a.episodes.glob('*.json.gz'))
    files = [f for i, f in enumerate(files) if i % a.stride == a.offset]
    if a.limit:
        files = files[:a.limit]
    todo = [f for f in files if not (a.out / (f.name[:-len('.json.gz')] + '.npz')).exists()]
    print(f'{len(files)} episodes, {len(files) - len(todo)} already labelled, {len(todo)} to do, {a.workers} workers', flush=True)
    started = time.time()
    done = rows = failed = 0
    with Pool(a.workers, initializer=start, initargs=(str(a.cells), str(a.scorer), a.cards, a.mass, a.maxnodes, a.full, str(a.out))) as pool, \
            open(a.out / 'stats.jsonl', 'a') as stats, open(a.out / 'errors.jsonl', 'a') as errors:
        for r in pool.imap_unordered(label, todo, chunksize=2):
            done += 1
            if 'error' in r:
                failed += 1
                errors.write(json.dumps(r) + '\n')
                errors.flush()
            else:
                rows += r['rows']
                stats.write(json.dumps(r) + '\n')
            if done % 200 == 0 or done == len(todo):
                stats.flush()
                el = time.time() - started
                print(f'{done} of {len(todo)} episodes, {rows} rows, {failed} failed, {round(el)} s, '
                      f'{1000 * el * a.workers / max(rows, 1):.2f} core-ms a row, about {round(el / done * (len(todo) - done) / 60)} min left', flush=True)
    print(json.dumps(dict(episodes=done, rows=rows, failed=failed, seconds=round(time.time() - started))))


if __name__ == '__main__':
    main()
