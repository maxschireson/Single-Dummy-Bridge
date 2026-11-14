"""BenLstmBidder reads the output layer under either name Keras saves it: `layers/dense` (the house bidders) or
`layers/time_distributed/layer` (BEN's own TF2 bidders, e.g. GIB-BBO-8742, which wrap the same Dense in
TimeDistributed). Synthetic weights only: no third-party net is needed or stored."""
import io
import zipfile

import h5py
import numpy as np
import pytest

from bridge_harness.system_bidders import BenLstmBidder
from bridge_harness.system_fit import deal, simulate

UNITS = 8


def _weights(rng):
    w = {}
    for i, n in enumerate(('lstm', 'lstm_1', 'lstm_2')):
        w[f'layers/{n}/cell/vars/0'] = rng.normal(0, 0.3, (193 if i == 0 else UNITS, 4 * UNITS))
        w[f'layers/{n}/cell/vars/1'] = rng.normal(0, 0.3, (UNITS, 4 * UNITS))
        w[f'layers/{n}/cell/vars/2'] = rng.normal(0, 0.1, (4 * UNITS,))
    for n in ('batch_normalization', 'batch_normalization_1', 'batch_normalization_2'):
        w[f'layers/{n}/vars/0'] = rng.uniform(0.5, 1.5, UNITS)
        w[f'layers/{n}/vars/1'] = rng.normal(0, 0.1, UNITS)
        w[f'layers/{n}/vars/2'] = rng.normal(0, 0.1, UNITS)
        w[f'layers/{n}/vars/3'] = rng.uniform(0.5, 1.5, UNITS)
    return w


def _keras(path, weights, out):
    buf = io.BytesIO()
    with h5py.File(buf, 'w') as f:
        for k, v in weights.items():
            f[k] = v.astype(np.float32)
        if out:
            f[f'{out}/0'] = weights['_wd'].astype(np.float32)
            f[f'{out}/1'] = weights['_bd'].astype(np.float32)
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('model.weights.h5', buf.getvalue())
    return str(path)


def test_dense_and_time_distributed_layouts_bid_alike(tmp_path):
    rng = np.random.default_rng(7)
    w = _weights(rng)
    w['_wd'], w['_bd'] = rng.normal(0, 0.5, (UNITS, 40)), rng.normal(0, 0.1, 40)
    core = {k: v for k, v in w.items() if not k.startswith('_')}
    house = BenLstmBidder(_keras(tmp_path / 'house.keras', dict(core, _wd=w['_wd'], _bd=w['_bd']), 'layers/dense/vars'))
    ben = BenLstmBidder(_keras(tmp_path / 'ben.keras', dict(core, _wd=w['_wd'], _bd=w['_bd']),
                               'layers/time_distributed/layer/vars'))
    assert np.array_equal(house.wd, ben.wd) and np.array_equal(house.bd, ben.bd)
    hands, dealer, vul = deal(np.random.default_rng(3), 64)
    a, b = simulate([house, house], hands, dealer, vul), simulate([ben, ben], hands, dealer, vul)
    calls_a = a[0] if isinstance(a, tuple) else a['calls']
    calls_b = b[0] if isinstance(b, tuple) else b['calls']
    assert np.array_equal(calls_a, calls_b)


def test_missing_output_layer_is_named(tmp_path):
    rng = np.random.default_rng(8)
    w = _weights(rng)
    with pytest.raises(KeyError, match='no output layer'):
        BenLstmBidder(_keras(tmp_path / 'none.keras', w, None))
