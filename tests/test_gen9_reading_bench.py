"""scripts/gen9_reading_bench.py on two tables: pools at the house bots' decisions, Gen 8 and Gen 9 readings, the bench's report.

The two bench tests need data and skip without it: GEN7_CAPSULE (the Gen 7 capture capsule's recovery folder, with
its episodes for the relabelled test) and BEN_FEEDS (a folder holding BEN feed checkouts, `<feed>/recovery/episodes`),
and the Gen 5 policy and hand-fit scorer restored in models/cardplay (their restore scripts)."""
import glob
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPSULE = Path(os.environ.get('GEN7_CAPSULE', '/home/claude/data/g7a1/recovery'))
FEEDS = sorted(glob.glob(os.environ.get('BEN_FEEDS', '/home/claude/data/ben') + '/*/recovery/episodes'))
NEEDS = [ROOT / 'models/cardplay/gen5-2026-11-10/policy.npz', ROOT / 'models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz']


@pytest.mark.skipif(not (CAPSULE / 'manifest.json').exists() or not FEEDS or not all(p.exists() for p in NEEDS),
                    reason='needs the Gen 7 capsule, a BEN feed and the restored Gen 5 policy and hand-fit scorer')
def test_two_tables(tmp_path):
    run = [sys.executable, str(ROOT / 'scripts' / 'gen9_reading_bench.py')]
    out = tmp_path / 'bench'
    subprocess.run(run + ['pools', '--feeds', *FEEDS, '--opponent', 'ben', '--tables', '2', '--pool', '32', '--out', str(out)], check=True, cwd=ROOT)
    subprocess.run(run + ['readings', '--feeds', *FEEDS, '--out', str(out), '--source', str(CAPSULE), '--reading', 'g8=8x-32', '--reading', 'g9=r9b-32'],
                   check=True, cwd=ROOT)
    spec = importlib.util.spec_from_file_location('bench', ROOT / 'scripts' / 'gen8_reading_bench.py')
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    rows, names = bench.read_all(out)
    assert names == ['v4', 'g8', 'g9'] and rows
    tables = json.loads((out / 'tables.json').read_text())['tables']
    for r in rows:                                       # only house bots decide: BEN's own decisions are not stored
        info = bench.load(next(out.glob('pools-*.npz')))[1][int(r['table'])]
        assert info['bots'].count('ben') == 2
        v4, g8, g9 = r['fit']['v4'], r['fit']['g8'], r['fit']['g9']
        assert np.allclose(g8[1], v4[1], atol=1e-5)               # partner's plays: in full
        assert np.allclose(g8[2], .3 * v4[2], atol=1e-4)          # BEN's: Gen 8's factor for an unknown opponent
        assert np.allclose(g9[1], g8[1], atol=1e-5)
    assert any(not np.allclose(r['fit']['g9'][2], r['fit']['g8'][2]) for r in rows)   # the emission model reads BEN's defenders
    assert len(tables) == 2
    report = subprocess.run(run + ['report', '--out', str(out), '--against', 'g8', '--json', str(tmp_path / 'r.json')],
                            check=True, cwd=ROOT, capture_output=True, text=True)
    result = json.loads((tmp_path / 'r.json').read_text())
    assert 'paired | g9' in result['groups'] and 'as built | g9' in result['groups'], report.stdout


@pytest.mark.skipif(not (CAPSULE / 'episodes').is_dir() or not all(p.exists() for p in NEEDS), reason='needs the Gen 7 capsule with its episodes')
def test_relabelled_table(tmp_path):
    run = [sys.executable, str(ROOT / 'scripts' / 'gen9_reading_bench.py')]
    out = tmp_path / 'rel'
    subprocess.run(run + ['relabel', '--source-episodes', str(CAPSULE / 'episodes'), '--cell', 'std-80', '--tables', '1', '--seed', '9', '--out', str(out)],
                   check=True, cwd=ROOT)
    subprocess.run(run + ['pools', '--episodes', str(out / 'episodes'), '--deciders', 'declarer', '--tables', '1', '--pool', '32', '--out', str(out)],
                   check=True, cwd=ROOT)
    subprocess.run(run + ['readings', '--out', str(out), '--source', str(CAPSULE), '--reading', 'g8=8x-32@c-std-80', '--reading', 'full=8x-32@7s-32',
                          '--reading', 'g9=r9-32@c-std-80'], check=True, cwd=ROOT)
    spec = importlib.util.spec_from_file_location('bench', ROOT / 'scripts' / 'gen8_reading_bench.py')
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    rows, names = bench.read_all(out)
    assert rows and all(bool(r['declaring']) for r in rows)
    for r in rows:
        v4, g8, full = r['fit']['v4'], r['fit']['g8'], r['fit']['full']
        assert np.allclose(full, v4, atol=1e-4)                  # house bots met as themselves: the net in full
        assert np.allclose(g8[2], .3 * v4[2], atol=1e-4)         # an outside player Gen 8 does not know: 0.3


def test_touching_and_equal_classes():
    sys.argv = ['x']
    sys.path.insert(0, str(ROOT / 'scripts'))
    import gen9_reading_bench as g

    class O:
        pass
    o = O()
    o.history = [(1, 9), (2, 6), (3, 20), (0, 10)]          # the jack and eight of spades gone; the queen played
    r = g.ClassReading.__new__(g.ClassReading)
    r.kind = 'touching'
    held = np.zeros((2, 52), bool)
    held[0, [11, 10, 7, 5, 30]] = True                     # K Q 9 7 of spades: Q touches K only (the ten is out)
    held[1, [12, 10, 8, 30]] = True                        # A Q T: Q touches T through the gone jack, and not the A (K out)
    K = r.klass(o, 3, held)
    assert sorted(np.flatnonzero(K[0])) == [10, 11]
    assert sorted(np.flatnonzero(K[1])) == [8, 10]
    o.history[3] = (0, 7)                                  # the nine: touches the seven through the gone eight
    assert sorted(np.flatnonzero(r.klass(o, 3, held)[0])) == [5, 7]
    r.kind, r.equal, r.table_id = 'equal', {'t': {'3': [7, 30]}}, 't'
    K = r.klass(o, 3, held)
    assert sorted(np.flatnonzero(K[0])) == [7, 30]          # the listed set; the reader then keeps what the layout holds
