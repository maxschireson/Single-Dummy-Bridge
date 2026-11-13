#!/usr/bin/env python3
"""int8 for the card-play nets, beside bf16 (today's collection path): speed on one core, and how far the choices move
from fp32, on held-out rows.

  python training/rollout-loop-20261113/bench/int8.py --rows VAL.npz NET.npz [NET.npz ...]

int8 is torch's dynamic quantization (fbgemm, which uses the AVX512-VNNI instructions where the CPU has them): weights
stored as int8 with one scale per output column, activations quantized to uint8 per call. Variants:
  bf16        gen7_net.Bf16Forward, the collection's path since 19:56 UTC on 13 November
  int8        every layer int8
  int8 mixed  int8 for the hidden layers; the decoder's last layer (52 cards x 5 heads) in fp32
Agreement against fp32 NumPy, as bench/bf16.py measures it.
"""
import argparse, sys, time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from bridge_harness import gen7_net as G  # noqa: E402
import torch  # noqa: E402
from torch import nn  # noqa: E402

torch.set_num_threads(1)
torch.backends.quantized.engine = 'fbgemm' if 'fbgemm' in torch.backends.quantized.supported_engines else torch.backends.quantized.engine


def load(path):
    with np.load(path) as z:
        return {k: z[k] for k in z.files if k not in G.BANK_KEYS and k != 'bot_vocab'}


def linear(w, b=None):
    m = nn.Linear(w.shape[0], w.shape[1], bias=b is not None)
    with torch.no_grad():
        m.weight.copy_(torch.from_numpy(np.ascontiguousarray(w.T.astype(np.float32))))
        if b is not None:
            m.bias.copy_(torch.from_numpy(np.asarray(b, np.float32)))
    return m


class Net(nn.Module):
    """The suit-shared forward as nn.Linear layers, so torch can quantize them."""
    def __init__(self, P, last_fp32=False):
        super().__init__()
        e = P['ws1'].shape[1]; t = P['wt1'].shape[1]
        self.s0, self.s1 = linear(P['ws0'], P['bs0']), linear(P['ws1'], P['bs1'])
        self.t0, self.t1 = linear(P['wt0'], P['bt0']), linear(P['wt1'], P['bt1'])
        self.d0s, self.d0h = linear(P['wd0'][:e], P['bd0']), linear(P['wd0'][e:e + t])
        self.slot = torch.from_numpy(np.ascontiguousarray(P['wd0'][e + t:e + t + 4].astype(np.float32)))
        self.d1 = linear(P['wd1'], P['bd1'])
        self.emb = torch.from_numpy((P['emb_own'][0] + P['emb_other'][0]).astype(np.float32)) if 'emb_own' in P else None
        self.last_fp32 = last_fp32

    def forward(self, s, g, n):
        s = torch.relu(self.s1(torch.relu(self.s0(s))))            # [4n, e]
        e = s.shape[1]
        h = self.t0(torch.cat([s.reshape(n, 4 * e), g], dim=1))
        if self.emb is not None:
            h = h + self.emb
        h = torch.relu(self.t1(torch.relu(h)))
        d = torch.relu(self.d0s(s).reshape(n, 4, -1) + self.d0h(h)[:, None, :] + self.slot[None]).reshape(n * 4, -1)
        return self.d1(d)


def inputs(batch):
    cards, g = G.features(batch)
    n = cards.shape[0]
    shown = np.asarray(batch['shown']).astype(np.float32).reshape(n, 4, G.SEAT_SHOWN)[:, :, :G.SUIT_SHOWN * 4]
    about = np.transpose(shown.reshape(n, 4, G.SUIT_SHOWN, 4), (0, 3, 1, 2)).reshape(n, 4, 4 * G.SUIT_SHOWN)
    s = np.ascontiguousarray(np.concatenate([cards.reshape(n, 4, 13 * G.CARD_FEATURES), about], axis=2).reshape(n * 4, -1))
    return torch.from_numpy(s), torch.from_numpy(np.ascontiguousarray(g)), n


def run(model, batch):
    s, g, n = inputs(batch)
    with torch.inference_mode():
        out = model(s, g, n).float().reshape(n, 4, 13, 5)[..., 0].reshape(n, 52).numpy()
    return np.where(batch['legal'], out, -1e9)


def log_softmax(x):
    x = x - x.max(axis=1, keepdims=True)
    return x - np.log(np.exp(x).sum(axis=1, keepdims=True))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('nets', nargs='+', type=Path)
    p.add_argument('--rows', type=Path, required=True)
    p.add_argument('--n', type=int, default=24576)
    a = p.parse_args()
    z = np.load(a.rows, allow_pickle=True)
    pick = np.sort(np.random.default_rng(0).choice(len(z['deal']), min(a.n, len(z['deal'])), replace=False))
    rows = {k: z[k][pick] for k in G.INPUTS}
    gap, legal = z['gap'][pick].astype(np.float32), z['legal'][pick].astype(bool)
    rated = legal & (gap >= 0)
    has = (z['meta'][pick][:, 10] == 1) & rated.any(1)
    print(f'{len(pick)} held-out rows; quantized engine {torch.backends.quantized.engine}; torch {torch.__version__}')
    for path in a.nets:
        P = load(path)
        ref = np.concatenate([np.asarray(G.forward(P, {k: v[i:i + 4096] for k, v in rows.items()})['policy']) for i in range(0, len(pick), 4096)])
        lp_ref = log_softmax(ref); p_ref = np.exp(lp_ref); first_ref = lp_ref.argmax(1)
        bf = G.Bf16Forward.make(P)
        variants = {'bf16': lambda b: np.asarray(bf(b)['policy'])}
        q_all = torch.ao.quantization.quantize_dynamic(Net(P), {nn.Linear}, dtype=torch.qint8)
        net_mixed = Net(P)
        q_mixed = torch.ao.quantization.quantize_dynamic(net_mixed, {'s0', 's1', 't0', 't1', 'd0s', 'd0h'}, dtype=torch.qint8)
        variants['int8'] = lambda b: run(q_all, b)
        variants['int8 mixed'] = lambda b: run(q_mixed, b)

        def clock(f, b, reps=30):
            f(b); s = time.perf_counter()
            for _ in range(reps):
                f(b)
            return (time.perf_counter() - s) / reps
        print(f'\n{path.parent.name}/{path.name}')
        for size in (512, 128):
            b = {k: v[:size] for k, v in rows.items()}
            t0 = clock(lambda x: G.forward(P, x), b)
            line = [f'fp32 {size / t0:.0f}']
            for name, f in variants.items():
                line.append(f'{name} {size / clock(f, b):.0f} ({t0 / clock(f, b):.2f}x)')
            print(f'  rows/s at {size} rows a call, one thread: ' + ' | '.join(line))
        for name, f in variants.items():
            got = np.concatenate([f({k: v[i:i + 4096] for k, v in rows.items()}) for i in range(0, len(pick), 4096)])
            lp = log_softmax(got); pr = np.exp(lp); first = lp.argmax(1)
            dl = np.abs(np.where(legal, lp - lp_ref, 0)); tv = .5 * np.abs(pr - p_ref).sum(1)
            reg = np.where(rated[np.arange(len(pick)), first], gap[np.arange(len(pick)), first], np.nan)[has]
            print(f'  {name:10s} first card same {100 * (first == first_ref).mean():6.2f}% | log-prob change mean {dl.sum() / legal.sum():.4f} '
                  f'max {dl.max():.3f} | TV mean {tv.mean():.4f} | tricks given up {np.nanmean(reg):.4f} (fp32 {gap[np.arange(len(pick)), first_ref][has].mean():.4f})')


if __name__ == '__main__':
    main()
