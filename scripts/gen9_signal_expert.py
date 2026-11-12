#!/usr/bin/env python3
"""E9-15: honesty by situation, and a signal expert per known opponent (BEN first). bridge_harness/signal_expert.py.

Gen 9 work in progress (sam, signals). Prediction evidence. Data and split are E9-7's (scripts/gen9_ben_reading.py).

  extract   Every occasion of tricks 1 to 9 (a defender's choice among two or more spots of a suit, in a situation with a
            key, the second round of a suit included) on every table against BEN, for BEN's defenders and, as the control,
            the house bots' defenders, from the recorded hands. Stored with what M0 (E9-7's symmetric honesty) and E9-7's
            emission tables give the card played.
  fit       Per BEN version, on 50, 200 and 1,000 fit tables (5 random subsets each) and on all: M1 (emission rows), M2
            (finer cells, alpha by 3-fold cross-validation over tables) and M3 (the expert, penalty by the same). The house
            control on all its fit tables.
  occasions Held-out log-likelihood per occasion of the card played (against a uniform choice in the class), every model
            and size; the reliability of the high card by situation; BEN's effective honesty by public situation, with
            intervals from resampling tables.
  score     At the house declarer's decisions on E9-7's 300 held-out tables a version (tricks 1 to 6, pool 256, seed 9):
            the true layout's gain in nats when BEN's defenders are read by Gen 8 (the net at 0.3), by E9-7's model, or by
            the class term at 0.3 plus M1, M2 or M3 of each size.

  python scripts/gen9_signal_expert.py FEED_EPISODES_DIRS... --source CAPSULE/recovery --fit E9-7.fit.json --out DIR
"""
import os
for _name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_name, '1')
import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
from pathlib import Path
import sys
import time
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.core import Game, card  # noqa: E402
from bridge_harness.gen6 import View  # noqa: E402
from bridge_harness.gen7 import hidden_plays  # noqa: E402
from bridge_harness.gen9_play import SignalPlayer  # noqa: E402
from bridge_harness.signal_expert import KEYS, M1, M2, M3, Occasion, Symmetric, effective_honesty, occasion  # noqa: E402
from bridge_harness.signals import SignalModel  # noqa: E402
from gen9_ben_reading import BEN_CARD, ben_tables, load  # noqa: E402
from gen9_reading_gain import gains, pool_layouts  # noqa: E402

LAST_TRICK = 9
UNTIL = 7
SIZES = (50, 200, 1000)
SUBSETS = 5
ALPHAS = (2., 5., 10., 20., 50., 100.)
LAMS = (.1, .3, 1., 3., 10., 30., 100., 300.)
STATE = {}


def e97_models(fit, ben):
    f = fit[ben]
    emit = SignalModel(BEN_CARD, f['emission']['honesty'], .05, emission={k: np.array(v) for k, v in f['emission']['emission'].items()})
    sym = SignalModel(BEN_CARD, f['honesty']['honesty'], .05)
    return emit, sym


def extract(job):
    path, key, ben, fit = job
    board, actions, ben_side = load(path, key)
    if board is None or ben_side is None:
        return []
    c = board.contract
    game = Game(board)
    for a in actions:
        if game.done:
            break
        game.play(card(a['card']))
    history = tuple(game.history)
    out = []
    for i, (seat, x) in enumerate(history[:4 * LAST_TRICK]):
        if seat in (c.declarer, c.dummy):
            continue
        original = np.zeros((1, 52), bool)
        original[0, list(board.hands[seat])] = True
        oc = occasion(history, i, c, board.hands[c.dummy], original)
        if oc is None or oc.n[0] < 2:
            continue
        side = 'ben' if seat % 2 == ben_side else 'house'
        row = dict(key=oc.key, suit=oc.suit, played=oc.played, public=oc.public, n=int(oc.n[0]), pos=int(oc.pos[0]),
                   hand={k: (bool(v[0]) if v.dtype == bool else int(v[0])) for k, v in oc.hand.items()}, side=side, trick=i // 4 + 1)
        if side == 'ben':
            emit, sym = e97_models(fit, ben)
            led_suit = history[i - i % 4][1] // 13
            row['p_m0'] = float(Symmetric(sym).probability(oc, c, led_suit, original)[0])
            if oc.key.endswith('.r2'):
                row['p_e97'] = 1. / oc.n[0]
            else:
                row['p_e97'] = float(emit.probabilities(oc.key, emit.signal(oc.key), oc.played, oc.K, original, oc.suit, c.trump, led_suit, c.trump == 4)[0])
        out.append(row)
    return out


def as_occasion(r):
    """An Occasion of one layout from a stored row."""
    hand = {k: np.array([v]) for k, v in r['hand'].items()}
    return Occasion(r['key'], r['suit'], r['played'], r['public'], None, np.array([r['n']]), np.array([r['pos']]), hand)


def log_lik(model, occ):
    return np.array([np.log(model.probability(o)[0]) for o in occ])


def fit_models(occ, tables, seed):
    """(M1, M2, M3, cross-validation log) on the occasions `occ` (with their tables)."""
    m1 = M1.fit(occ)
    ug = np.unique(tables)
    rng = np.random.default_rng(seed)
    fold_of = dict(zip(ug, rng.permutation(len(ug)) % 3))
    fold = np.array([fold_of[t] for t in tables])
    cv2, cv3 = {a: 0. for a in ALPHAS}, {lam: 0. for lam in LAMS}
    for k in range(3):
        tr = [o for o, f in zip(occ, fold) if f != k]
        te = [o for o, f in zip(occ, fold) if f == k]
        if not tr or not te:
            continue
        b = M1.fit(tr)
        base = log_lik(b, te)
        for a in ALPHAS:
            cv2[a] += float((log_lik(M2.fit(tr, b, a), te) - base).sum())
        w = None
        for lam in sorted(LAMS, reverse=True):
            w = M3.fit(tr, b, lam, w)
            cv3[lam] += float((log_lik(w, te) - base).sum())
    a = max(ALPHAS, key=lambda x: cv2[x])
    lam = max(LAMS, key=lambda x: cv3[x])
    m2 = M2.fit(occ, m1, a)
    m3 = None
    for l_ in sorted(LAMS, reverse=True):
        if l_ < lam:
            break
        m3 = M3.fit(occ, m1, l_, m3)
    return m1, m2, m3, dict(alpha=a, lam=lam, cv2={str(k): v / len(occ) for k, v in cv2.items()}, cv3={str(k): v / len(occ) for k, v in cv3.items()})


def fit_job(job):
    ben, name, rows, seed = job
    t0 = time.time()
    occ = [as_occasion(r) for r in rows]
    m1, m2, m3, log = fit_models(occ, np.array([r['t'] for r in rows]), seed)
    log.update(ben=ben, name=name, occasions=len(rows), tables=len({r['t'] for r in rows}), seconds=round(time.time() - t0, 1))
    return ben, name, dict(m1={k: v.tolist() for k, v in m1.table.items()}, m2=m2.to_json(), m3=m3.w.tolist()), log


def build(spec):
    m1 = M1(spec['m1'])
    return dict(m1=m1, m2=M2(spec['m2']['counts'], m1, spec['m2']['alpha']), m3=M3(np.array(spec['m3']), m1))


def occasion_report(rows, models, out):
    """Held-out log-likelihood per occasion, reliability and effective honesty by situation."""
    report = dict(loglik={}, honesty={}, reliability={})
    for ben in ('ben', 'ben64'):
        other = 'ben64' if ben == 'ben' else 'ben'
        held = [r for r in rows if r['ben'] == ben and r['held'] and r['side'] == 'ben']
        occ = [as_occasion(r) for r in held]
        tables = np.array([r['t'] for r in held])
        uni = -np.log([r['n'] for r in held])
        res = {'m0 (E9-7 symmetric)': np.log([r['p_m0'] for r in held]) - uni, 'E9-7 tables': np.log([r['p_e97'] for r in held]) - uni}
        for name, spec in models[ben].items():
            for m in ('m1', 'm2', 'm3'):
                res[f'{m} {name}'] = log_lik(spec[m], occ) - uni
        for m in ('m1', 'm2', 'm3'):
            res[f'{m} other version'] = log_lik(models[other]['all'][m], occ) - uni
        keys = np.array([r['key'] for r in held])
        entry = {}
        for name, v in res.items():
            entry[name] = dict(all=clustered(v, tables), **{k: clustered(v[keys == k], tables[keys == k]) for k in KEYS if (keys == k).sum() >= 30})
        report['loglik'][ben] = dict(occasions=len(held), tables=int(len(np.unique(tables))), models=entry)
        # effective honesty and bits by situation: held-out tables (the measurement), and every table (a description)
        report['honesty'][ben] = honesty_table(held)
        report.setdefault('honesty_all_tables', {})[ben] = honesty_table([r for r in rows if r['ben'] == ben and r['side'] == 'ben'])
        # reliability: predicted against observed rate of the high card, by key, under M1 and M3 (all)
        rel = {}
        for m in ('m1', 'm3'):
            pred = np.array([models[ben]['all'][m].positions(o)[0] for o in occ])
            for k in KEYS:
                sel = keys == k
                if sel.sum() < 30:
                    continue
                obs = np.array([r['pos'] == 1 for r in np.array(held, dtype=object)[sel]], float)
                ph = pred[sel, 1] / np.where(np.array([r['n'] for r in np.array(held, dtype=object)[sel]]) >= 3, pred[sel].sum(axis=1), pred[sel, :2].sum(axis=1))
                bins = np.digitize(ph, [.1, .2, .3, .5])
                rel[f'{m} | {k}'] = [dict(bin=int(b), n=int((bins == b).sum()), predicted=float(ph[bins == b].mean()), observed=float(obs[bins == b].mean()))
                                     for b in np.unique(bins) if (bins == b).sum() >= 20]
        report['reliability'][ben] = rel
    # the house control: their own models, on their held-out occasions
    report['house'] = {}
    for ben in ('ben', 'ben64'):
        held = [r for r in rows if r['ben'] == ben and r['held'] and r['side'] == 'house']
        if not held or 'house' not in models:
            continue
        occ = [as_occasion(r) for r in held]
        tables = np.array([r['t'] for r in held])
        uni = -np.log([r['n'] for r in held])
        spec = models['house'][ben]
        report['house'][ben] = dict(occasions=len(held), **{m: clustered(log_lik(spec[m], occ) - uni, tables) for m in ('m1', 'm2', 'm3')},
                                    m3_over_m1=clustered(log_lik(spec['m3'], occ) - log_lik(spec['m1'], occ), tables),
                                    honesty=honesty_table(held))
    Path(out).write_text(json.dumps(report, indent=1))
    return report


def bits(rs):
    """I(parity; position of the card in its class: lowest, highest, middle) in bits, the plug-in estimate less the
    Miller-Madow bias ((2 - 1)(3 - 1) / (2 N ln 2))."""
    joint = np.zeros((2, 3))
    for r in rs:
        joint[int(r['hand']['parity']), r['pos']] += 1
    n = joint.sum()
    if n == 0:
        return float('nan')
    p = joint / n
    px, py = p.sum(axis=1, keepdims=True), p.sum(axis=0, keepdims=True)
    nz = p > 0
    mi = float((p[nz] * np.log2(p[nz] / (px @ py)[nz])).sum())
    used = (joint.sum(axis=0) > 0).sum()
    return mi - (used - 1) / (2 * n * np.log(2))


def honesty_table(rs_all):
    """{situation: honesty_cell} for every cell with 200 or more occasions."""
    cells = {}
    for r in rs_all:
        p = r['public']
        labels = [r['key'], f"{r['key']} | {'NT' if p['nt'] else 'suit'}",
                  f"{r['key']} | led by {['declarer', 'dummy', 'partner', 'self'][p['leader']]}",
                  f"{r['key']} | {'can win' if not r['hand']['decided'] else 'cannot win'}",
                  f"{r['key']} | {r['n']} spots" if r['n'] < 4 else f"{r['key']} | 4+ spots",
                  f"{r['key']} | trick {'1' if r['trick'] == 1 else '2-3' if r['trick'] <= 3 else '4+'}",
                  f"{r['key']} | {['', 'second', 'third', 'fourth'][p['position']]} hand",
                  f"{r['key']} | dummy holds {min(p['dummy_now'], 4)}{'+' if p['dummy_now'] >= 4 else ''} now"]
        if p['dummy_long_no_entry']:
            labels.append(f"{r['key']} | dummy's long suit, no entry outside")
        if r['key'].endswith('.r2'):
            labels.append(f"{r['key']} | first card {['lowest', 'highest', 'middle', 'an honour', 'forced', ''][r['hand']['first']]}")
        for label in labels:
            cells.setdefault(label, []).append(r)
    return {label: honesty_cell(rs) for label, rs in sorted(cells.items()) if len(rs) >= 200}


def honesty_cell(rs, boots=200, seed=0):
    """P(high | even), P(high | odd), prior of even, effective honesty and the information in bits a signal, each with a
    90% interval from resampling tables."""
    def stats(sel):
        even = np.array([r['hand']['parity'] for r in sel])
        high = np.array([r['pos'] == 1 for r in sel])
        a, b, q = high[even].mean() if even.any() else np.nan, high[~even].mean() if (~even).any() else np.nan, even.mean()
        return a, b, q
    a, b, q = stats(rs)
    by_table = {}
    for r in rs:
        by_table.setdefault(r['t'], []).append(r)
    groups = list(by_table.values())
    rng = np.random.default_rng(seed)
    hs, bs = [], []
    for _ in range(boots):
        pick = [x for g in rng.choice(len(groups), len(groups)) for x in groups[g]]
        ra, rb, rq = stats(pick)
        if np.isfinite(ra) and np.isfinite(rb):
            hs.append(effective_honesty(ra, rb, rq))
        bs.append(bits(pick))
    h = effective_honesty(a, b, q) if np.isfinite(a) and np.isfinite(b) else float('nan')
    return dict(occasions=len(rs), tables=len(groups), p_high_even=float(a), p_high_odd=float(b), even=float(q), honesty=h,
                interval=[float(np.quantile(hs, .05)), float(np.quantile(hs, .95))] if hs else None,
                bits=bits(rs), bits_interval=[float(np.quantile(bs, .05)), float(np.quantile(bs, .95))])


def clustered(v, tables):
    v = np.asarray(v, float)
    if len(v) == 0:
        return [float('nan'), float('nan'), 0]
    _, inv = np.unique(tables, return_inverse=True)
    tot, cnt = np.bincount(inv, v), np.bincount(inv)
    m = tot.sum() / cnt.sum()
    k = len(cnt)
    se = np.sqrt(((tot - m * cnt) ** 2).sum() * k / (k - 1)) / cnt.sum() if k > 1 else float('nan')
    return [float(m), float(se), int(len(v))]


# ---- scoring at the house declarer's decisions ---------------------------------------------------------------------

def scored(job):
    path, key, source, bot, pool, seed, fit, ben, specs = job
    if 'p' not in STATE:
        m = json.loads((Path(source) / 'manifest.json').read_text())
        STATE['p'] = SignalPlayer(dict(m['bots'][bot], gen9={}), source)
    p = STATE['p']
    board, actions, ben_side = load(path, key)
    if board is None or ben_side is None or ben_side == board.contract.declarer % 2:
        return []
    c = board.contract
    emit, sym = e97_models(fit, ben)
    models = {name: build(s) for name, s in specs.items()}
    rng = np.random.default_rng(zlib.crc32(f'{Path(path).name}/{key}/{seed}'.encode()))
    truth = tuple(tuple(sorted(h)) for h in board.hands)
    game = Game(board)
    rows = []
    for a in actions:
        if game.done or len(game.history) // 4 + 1 >= UNTIL:
            break
        o = game.observation()
        if o.controller % 2 != ben_side and o.history and len(o.legal) > 1:
            view = View(o)
            hidden = hidden_plays(o, True)
            if len(view.hidden) == 2 and hidden:
                src, assign = pool_layouts(p, o, view, truth, pool, rng)
                n = len(assign)
                card_part, class_part, sig_e, sig_h = (np.zeros(n) for _ in range(4))
                sig = {f'{m} {name}': np.zeros(n) for name in models for m in ('m1', 'm2', 'm3')}
                occasions = 0
                for play in hidden:
                    i, seat, chooser = play
                    lc, lk, le = p.signal_row(o, view, assign, *play, emit)
                    _, _, lh = p.signal_row(o, view, assign, *play, sym)
                    card_part += lc
                    class_part += lk
                    sig_e += le
                    sig_h += lh
                    original = view.original(assign, view.hidden.index(chooser)).astype(bool)
                    oc = occasion(o.history, i, c, o.original_hand(c.dummy), original)
                    for name, ms in models.items():
                        for m, model in ms.items():
                            sig[f'{m} {name}'] += le if oc is None else np.log(model.probability(oc))
                    occasions += oc is not None
                g = {'gen8 (net 0.3)': gains(.3 * card_part), 'E9-7 symmetric': gains(.3 * class_part + sig_h), 'E9-7 tables': gains(.3 * class_part + sig_e)}
                g.update({k: gains(.3 * class_part + v) for k, v in sig.items()})
                rows.append(dict(episode=Path(path).name, table=key, ben=ben, trick=len(o.history) // 4 + 1, source=src, occasions=occasions,
                                 gains={k: round(v, 5) for k, v in g.items()}))
        game.play(card(a['card']))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('episodes', nargs='+')
    ap.add_argument('--source', required=True)
    ap.add_argument('--fit', required=True)
    ap.add_argument('--bot', default='7s-32')
    ap.add_argument('--tables', type=int, default=300)
    ap.add_argument('--pool', type=int, default=256)
    ap.add_argument('--seed', type=int, default=9)
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--out', required=True)
    ap.add_argument('--stop-after', choices=('extract', 'fit', 'occasions', 'score'), default='score')
    ap.add_argument('--score-sizes', default='all,n200.0,n1000.0', help='the fitted models scored at the decisions')
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    fit = json.loads(Path(args.fit).read_text())
    tables = ben_tables(args.episodes)
    cache = out / 'occasions.jsonl.gz'
    with ProcessPoolExecutor(args.workers) as pool:
        if cache.exists():
            rows = [json.loads(line) for line in gzip.open(cache, 'rt')]
        else:
            t0 = time.time()
            rows = []
            for t, ((p_, k, ben, held), got) in enumerate(zip(tables, pool.map(extract, [(p_, k, b, fit) for p_, k, b, _ in tables], chunksize=16))):
                rows += [dict(r, t=t, ben=ben, held=held) for r in got]
                if (t + 1) % 1000 == 0:
                    print(f'extract: {t + 1}/{len(tables)} tables', flush=True)
            with gzip.open(cache, 'wt') as f:
                for r in rows:
                    f.write(json.dumps(r) + '\n')
            print(f'extracted {len(rows)} occasions in {time.time() - t0:.0f} s', flush=True)
        if args.stop_after == 'extract':
            return
        mfile = out / 'models.json'
        if mfile.exists():
            models = json.loads(mfile.read_text())['models']
        else:
            rng = np.random.default_rng(args.seed)
            jobs = []
            for ben in ('ben', 'ben64'):
                fr = [r for r in rows if r['ben'] == ben and not r['held'] and r['side'] == 'ben']
                ts = np.unique([r['t'] for r in fr])
                for n in [x for x in SIZES if x < len(ts)]:
                    for s in range(SUBSETS):
                        pick = set(rng.choice(ts, n, replace=False).tolist())
                        jobs.append((ben, f'n{n}.{s}', [r for r in fr if r['t'] in pick], args.seed))
                jobs.append((ben, 'all', fr, args.seed))
                jobs.append((f'house|{ben}', 'all', [r for r in rows if r['ben'] == ben and not r['held'] and r['side'] == 'house'], args.seed))
            jobs.sort(key=lambda j: -len(j[2]))
            models, log = {}, []
            for ben, name, spec, entry in pool.map(fit_job, jobs, chunksize=1):
                if ben.startswith('house|'):
                    models.setdefault('house', {})[ben[6:]] = spec
                else:
                    models.setdefault(ben, {})[name] = spec
                log.append(entry)
                print(json.dumps({k: v for k, v in entry.items() if k not in ('cv2', 'cv3')}), flush=True)
            mfile.write_text(json.dumps(dict(models=models, log=log)))
        built = {ben: {name: build(s) for name, s in ms.items()} for ben, ms in models.items() if ben != 'house'}
        built['house'] = {ben: build(s) for ben, s in models.get('house', {}).items()}
        occasion_report(rows, built, out / 'occasions_report.json')
        if args.stop_after == 'occasions':
            return
        sizes = args.score_sizes.split(',')
        with open(out / 'rows.jsonl', 'w') as f:
            for ben in ('ben', 'ben64'):
                held = [(p_, k) for p_, k, b, h in tables if b == ben and h][:args.tables]
                specs = {name: models[ben][name] for name in sizes if name in models[ben]}
                jobs = [(p_, k, str(Path(args.source).resolve()), args.bot, args.pool, args.seed, fit, ben, specs) for p_, k in held]
                for done, got in enumerate(pool.map(scored, jobs, chunksize=1), 1):
                    for r in got:
                        f.write(json.dumps(r) + '\n')
                    if done % 50 == 0:
                        print(f'{ben}: {done}/{len(jobs)} held-out tables', flush=True)


if __name__ == '__main__':
    main()
