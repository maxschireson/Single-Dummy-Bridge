#!/usr/bin/env python3
"""The ladder at the top of the arena page: every bot's strength against its introduction date (G9-D9).

Gen 9 work (dave). Read-only; decides nothing.

  collect   every published board of every registered feed, with the per-board decision timing,
            into one rows file (the dashboard's sources: gh-pages arena/gen6-sources.json merged
            over the list built into arena/reporting.js, as the page does)
  fit       arena/ladder.json from the rows, configs/ladder-bots.json (parents and bench priors)
            and configs/ladder-feature-impacts.json

  python scripts/arena_ladder.py collect --out rows.jsonl.gz [--cache DIR]
  python scripts/arena_ladder.py fit --rows rows.jsonl.gz --out arena/ladder.json

Strength is ratings-v1 (bridge_harness/arena_ratings.py) on the native condition (each side bids
with its own bidder: the whole bot), in IMPs a board, made Bayesian: each bot has a prior, a bench
or match estimate relative to its parent where one exists (prior mean = the parent's strength +
the estimate), otherwise a weak prior at the field mean. Details in docs/gen9/ladder.md.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
import math
import posixpath
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'scripts'))
import arena_feed_rows as afr  # noqa: E402
from bridge_harness import arena_ratings as ar  # noqa: E402

RAW = afr.RAW
CANONICAL = {'P': '4p', 'Q': '4b'}          # reporting.js canonical()
HIDDEN = {'ben32'}                          # reporting.js hiddenDashboardActors
ACCIDENTAL = {'497d7f2c2e90d37c271ee7d700371c94f93d0f6717f530082742e80d24b2eb63',
              'e891c0a5c780c509a81df08c15397b6c7c6a24a8a266da499c6223d73bd24177'}


# ---- sources -----------------------------------------------------------------------------------

def builtin_sources(reporting_js: str):
    """The source list built into arena/reporting.js (`const sources=[...]`), as dicts."""
    body = re.search(r'const sources=\[(.*?)\n \];', reporting_js, re.S).group(1)
    out = []
    for obj in re.findall(r'\{[^{}]*\}', body):
        js = re.sub(r'([{,])\s*([A-Za-z_]\w*)\s*:', r'\1"\2":', obj).replace("'", '"')
        js = re.sub(r'\btrue\b', 'true', js)
        out.append(json.loads(js))
    return out


def dashboard_sources(registry, reporting_js):
    """The page's merge: registry entries replace built-in entries with the same key, new keys are added."""
    sources = builtin_sources(reporting_js)
    for e in registry['sources']:
        k = next((n for n, s in enumerate(sources) if s['key'] == e['key']), None)
        if k is None:
            sources.insert(0, dict(e))
        else:
            sources[k] = {**sources[k], **e}
    return sources


def members(p):
    return [CANONICAL.get(x, x) for x in (p.split('~') if '~' in p else list(p))]


def _timing(dt):
    """{bot: [decisions, forced, seconds]} from a record's decision_timing."""
    out = {}
    for bot, row in ((dt or {}).get('by_bot') or {}).items():
        out[CANONICAL.get(bot, bot)] = [row.get('decisions') or 0, row.get('forced_decisions') or 0,
                                        round(row.get('total_seconds') or 0.0, 4)]
    return out


def source_rows(s, ref, cache):
    data = afr.fetch(cache, ref, 'arena/data.json')
    if data['manifest_identity'] != s['cohort']:
        raise ValueError(f"{s['key']}: run identity at {ref} is not the registered cohort")
    ipath = f"arena/replays/data/{s['cohort']}/index.json"
    index = afr.fetch(cache, ref, ipath)
    records = list(index.get('records') or [])
    for shard in index.get('record_shards') or []:
        records += afr.fetch(cache, ref, posixpath.normpath(posixpath.join(posixpath.dirname(ipath), shard)))
    try:
        manifest = afr.fetch(cache, ref, 'arena/manifest.json')
    except Exception:
        manifest = {}
    native_ok = bool(data.get('own_views')) and index.get('supports_own_bidding') is not False
    rows = []
    for r in records:
        rows.append(dict(source=s['key'], generation=s.get('generation'), variant=s.get('variant'),
                         environment=s.get('environment'), cohort=s['cohort'], ref=ref,
                         retired=bool(s.get('retired')), allowed_pairs=s.get('allowed_pairs'),
                         snapshot_epoch=data['generated_epoch'], pair=r['pair'], index=r.get('index'),
                         family=r.get('family'), completed_epoch=r['completed_epoch'], common=r.get('imps'),
                         native=r.get('own_imps'), native_ok=native_ok, timing=_timing(r.get('decision_timing'))))
    versions = {CANONICAL.get(k, k): v for k, v in (index.get('versions') or data.get('versions') or {}).items()}
    bots = {}
    for k, spec in (manifest.get('bots') or {}).items():
        bots[CANONICAL.get(k, k)] = spec
    meta = dict(source=s['key'], name=s.get('name'), ref=ref, generation=s.get('generation'), variant=s.get('variant'),
                environment=s.get('environment'), cohort=s['cohort'], retired=bool(s.get('retired')),
                records=len(rows), labels=data.get('labels') or {}, versions=versions,
                feed_timing=_timing(data.get('decision_timing')), bots=bots,
                common_bidder=manifest.get('common_bidder'))
    return rows, meta


def collect(args):
    registry = json.loads(urllib.request.urlopen(f'{RAW}/gh-pages/arena/gen6-sources.json', timeout=60).read())
    reporting = urllib.request.urlopen(f'{RAW}/gh-pages/arena/reporting.js', timeout=60).read().decode()
    sources = dashboard_sources(registry, reporting)
    branch_heads = afr.heads()
    jobs = []
    for s in sources:
        ref = s.get('revision') or branch_heads.get(s['branch'])
        if ref is None:
            print(f"{s['key']}: branch {s['branch']} not found; skipped", file=sys.stderr)
            continue
        jobs.append((s, ref))
    rows, metas, failed = [], [], []
    with ThreadPoolExecutor(args.workers) as pool:
        futures = [(s, ref, pool.submit(source_rows, s, ref, args.cache)) for s, ref in jobs]
        for s, ref, f in futures:
            try:
                got, meta = f.result()
            except Exception as e:
                print(f"{s['key']}: {type(e).__name__}: {e}"[:300], file=sys.stderr)
                failed.append(dict(source=s['key'], ref=ref, error=repr(e)[:300]))
                continue
            rows += got
            metas.append(meta)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.out, 'wt') as f:
        for r in rows:
            f.write(json.dumps(r, separators=(',', ':')) + '\n')
    meta = dict(computed_utc=time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime()),
                registry_sha256=hashlib.sha256(json.dumps(registry, sort_keys=True).encode()).hexdigest(),
                rows=len(rows), sources=metas, failed=failed)
    meta_path = args.out.with_suffix('').with_suffix('.meta.json')
    meta_path.write_text(json.dumps(meta, indent=1))
    print(f'{len(rows):,} rows from {len(metas)} sources ({len(failed)} failed) -> {args.out}, {meta_path}')


# ---- specs, variants and features --------------------------------------------------------------

DROP_KEYS = {'id', 'label', 'identity'}
PATHLIKE = re.compile(r'(\.(npz|keras|json|h5|pt|onnx|txt)$)|/')


def flat(d, p=''):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(flat(v, f'{p}.{k}' if p else str(k)))
    else:
        out[p] = json.dumps(d) if isinstance(d, list) else d
    return out


def spec_settings(spec):
    """A bot's published spec without names, identities and file paths: what it plays with."""
    if not spec:
        return None
    return {k: v for k, v in flat(spec).items()
            if k.split('.')[0] not in DROP_KEYS and not (isinstance(v, str) and PATHLIKE.search(v))}


def fingerprint(settings):
    if settings is None:
        return 'unpublished'
    return hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()[:6]


# Feature names in words, by key prefix; the first match wins. Keys of one feature are reported together.
FEATURES = [
    ('gen7.opponent_play_weight', 'per-opponent reading factors'),
    ('gen7.early_', 'early play reading (from trick 1, before the deal list)'),
    ('gen7.play_weight', 'play reading weight (deal-list exponent)'),
    ('gen7.search_from_trick', 'play read from trick'),
    ('gen7.tree', 'tree breadth and depth'),
    ('gen7.tie_break', 'tie-break rule'),
    ('gen7.net_sample', 'random draw from the policy net'),
    ('gen7.play_', 'play reading settings'),
    ('gen7.tree_audit', 'tree audit'),
    ('gen7', 'Gen 7 search settings'),
    ('artifact_sha256.gen7_policy', 'card policy net version'),
    ('artifact_sha256.system_scorer', 'system scorer (reads other systems\' auctions)'),
    ('artifact_sha256.scorer', 'auction reading (hand-fit scorer)'),
    ('artifact_sha256.bidding', 'bidder version'),
    ('artifact_sha256.belief', 'belief net version'),
    ('artifact_sha256.policy', 'policy net version (Gen 3 to 6 policy)'),
    ('artifact_sha256.lead_belief', 'opening-lead belief net'),
    ('artifact_sha256.lead_state_bidder', 'bidder used to rebuild the auction for the opening lead'),
    ('artifact_sha256.config', 'BEN configuration'),
    ('artifact_sha256', 'model files'),
    ('bidder.', 'rule bidder: system and settings'),
    ('lead_systems', 'systems the opening lead reads'),
    ('layout_reduction', 'layout reduction (clustered samples)'),
    ('gen6.lead_source', 'opening-lead source'),
    ('gen6.mid_samples', 'mid-play samples'),
    ('gen6.list_', 'deal list (exhaustive layouts) settings'),
    ('gen6', 'Gen 6 search settings'),
    ('samples', 'layouts sampled a decision'),
    ('near_tie', 'near-tie margin (policy breaks near-ties)'),
    ('exploration', 'exploration'),
    ('belief_kind', 'belief kind'),
    ('policy_role', 'role of the policy net'),
    ('engine', 'search engine generation'),
]


def feature_name(key):
    for prefix, name in FEATURES:
        if key == prefix or key.startswith(prefix):
            return name
    return key


HEX64 = re.compile(r'^[0-9a-f]{64}$')


def short(v, n=90):
    if v is None:
        return 'none'
    if isinstance(v, str) and HEX64.match(v):
        return 'file ' + v[:8]
    s = json.dumps(v) if not isinstance(v, str) else v
    return s if len(s) <= n else s[:n - 1] + '…'


def features(settings, parent_settings, impacts):
    """The bot's settings against its parent's, grouped into named features, each with its known impacts."""
    if settings is None:
        return [dict(feature='settings not published by its feeds', keys=[], impacts=[])]
    if parent_settings is None:
        return []
    base = parent_settings or {}
    changed = sorted(k for k in set(settings) | set(base) if settings.get(k) != base.get(k))
    groups = {}
    for k in changed:
        groups.setdefault(feature_name(k), []).append(k)
    out = []
    for name, keys in groups.items():
        row = dict(feature=name, keys=keys)
        if len(keys) == 1:
            row.update(parent_value=short(base.get(keys[0])), value=short(settings.get(keys[0])))
        else:
            row.update(parent_value=f'{sum(k in base for k in keys)} settings', value=f'{len(keys)} settings changed or added')
        added = not any(k in base for k in keys)
        row['impacts'] = [i for i in impacts if name in i.get('features', [])
                          and i.get('when', 'any') in ('any', 'added' if added else 'changed')]
        out.append(row)
    return out


# ---- results -----------------------------------------------------------------------------------

def kept(r):
    """The page's counting rules for a record (reporting.js archivedPair, cutoff, allowed pairs)."""
    if r['completed_epoch'] > r['snapshot_epoch']:
        return False
    a, b = members(r['pair'])
    if a in HIDDEN or b in HIDDEN:
        return False
    if sorted((a, b)) == sorted(('6-32', 'ben')) and r['cohort'] in ACCIDENTAL:
        return False
    if r['allowed_pairs'] and r['pair'] not in r['allowed_pairs']:
        return False
    return True


def native_results(rows, who):
    """[(i, j, x)] on the native condition, players named by who(source, bot); a deal family counts once per pair,
    earliest completion first; self-play and records without a trusted native column left out."""
    items = []
    for r in rows:
        if not kept(r) or not r['native_ok'] or r['native'] is None:
            continue
        a, b = members(r['pair'])
        i, j = who(r['source'], a), who(r['source'], b)
        if i == j:
            continue
        items.append((r['completed_epoch'], r['family'], i, j, r['native']))
    items.sort(key=lambda x: x[0])
    seen, out = set(), []
    for t, fam, i, j, x in items:
        key = (fam, min(i, j), max(i, j))
        if fam is not None and key in seen:
            continue
        seen.add(key)
        out.append((i, j, x))
    return out


# ---- the Bayesian fit ----------------------------------------------------------------------------

MU = '__field__'


def bayes_fit(pairs, players, anchor, priors, weak_sd, t2=None, drop=None):
    """ratings-v1 with priors. priors: {player: (parent, estimate, sd)}, parent None for the weak prior at the field
    mean (a free parameter). The anchor is fixed at 0 and takes no prior. drop: leave this player's prior out.
    Returns (s, C, t2, details) over `players` (anchor row and column 0)."""
    free = [p for p in players if p != anchor]
    use_mu = any(pr[0] is None for p, pr in priors.items() if p != anchor and p != drop)
    params = free + ([MU] if use_mu else [])
    col = {p: k for k, p in enumerate(params)}
    P = len(params)
    A = np.zeros((len(pairs), P))
    for r, q in enumerate(pairs):
        if q.i != anchor: A[r, col[q.i]] += 1
        if q.j != anchor: A[r, col[q.j]] -= 1
    m = np.array([q.mean for q in pairs], float)
    e2 = np.array([q.se2() for q in pairs], float)
    prow, pm, pv = [], [], []
    for p, (parent, est, sd) in priors.items():
        if p == anchor or p == drop or p not in col:
            continue
        a = np.zeros(P); a[col[p]] += 1
        other = MU if parent is None else parent
        if other != anchor:
            a[col[other]] -= 1
        prow.append(a); pm.append(0.0 if parent is None else est); pv.append(sd ** 2)
    Ap = np.array(prow).reshape(-1, P); pm = np.array(pm); Wp = 1 / np.array(pv) if pv else np.zeros(0)
    Mp = Ap.T @ (Wp[:, None] * Ap); bp = Ap.T @ (Wp * pm)
    details = {}
    if t2 is None:
        t2 = 0.0
        if len(pairs) >= ar.T2_MIN_PAIRS:
            W0 = 1 / e2
            M = A.T @ (W0[:, None] * A) + Mp
            s0 = np.linalg.solve(M, A.T @ (W0 * m) + bp)
            resid = m - A @ s0
            Q = float(np.sum(W0 * resid ** 2))
            df = len(pairs) - np.linalg.matrix_rank(A)
            denom = float(W0.sum() - np.trace(np.linalg.solve(M, A.T @ ((W0 ** 2)[:, None] * A))))
            if df > 0 and denom > 0:
                t2 = min(max((Q - df) / denom, 0.0), ar.T2_CAP)
            details.update(Q=Q, df=int(df))
    W = 1 / (e2 + t2)
    M = A.T @ (W[:, None] * A) + Mp
    Cp = np.linalg.inv(M)
    sp = Cp @ (A.T @ (W * m) + bp)
    k = len(players)
    s = np.zeros(k); C = np.zeros((k, k))
    idx = [players.index(p) for p in free]
    s[idx] = sp[:len(free)]
    C[np.ix_(idx, idx)] = Cp[:len(free), :len(free)]
    if use_mu:
        details['field_mean'] = float(sp[-1]); details['field_mean_se'] = float(math.sqrt(Cp[-1, -1]))
    return s, C, float(t2), details


def fit_population(results, players, anchor, priors, weak_sd):
    """Fit, then each player's share of information from its own prior (1 - variance with it / variance without)."""
    pairs = [q for q in ar.summarise(results) if q.n > 0]
    s, C, t2, details = bayes_fit(pairs, players, anchor, priors, weak_sd)
    share = {}
    for k, p in enumerate(players):
        if p == anchor:
            share[p] = 0.0
            continue
        try:
            _, C0, _, _ = bayes_fit(pairs, players, anchor, priors, weak_sd, t2=t2, drop=p)
            v0 = C0[k, k]
            share[p] = float(max(0.0, 1 - C[k, k] / v0)) if v0 > 0 else 1.0
        except np.linalg.LinAlgError:
            share[p] = 1.0
    boards = {p: 0 for p in players}
    for q in pairs:
        boards[q.i] += q.n; boards[q.j] += q.n
    return dict(pairs=pairs, s=s, C=C, t2=t2, details=details, share=share, boards=boards)


def contrast(fit, players, i, j):
    a = np.zeros(len(players)); a[players.index(i)] += 1; a[players.index(j)] -= 1
    return float(a @ fit['s']), float(math.sqrt(max(a @ fit['C'] @ a, 0.0)))


# ---- the ladder file ---------------------------------------------------------------------------------

def prior_sd(p, cfg):
    sd = p['se']
    if p.get('tricks'):
        est = p['estimate']
        sd = math.sqrt(sd ** 2 + (cfg['conversion_error'] * est) ** 2)
    return sd


def arrival_estimate(control, cand, base):
    """cand against base on the arrival run's direct boards (native, a family once), from cand's side."""
    sys.path.insert(0, str(ROOT))
    from bridge_harness import arena9
    xs, seen = [], set()
    for r in arena9.read_results(control):
        if r.get('failed') or r.get('native') is None or {r['candidate'], r['opponent']} != {cand, base}:
            continue
        if r['family'] in seen:
            continue
        seen.add(r['family'])
        xs.append(r['native'] if r['candidate'] == cand else -r['native'])
    n = len(xs)
    m = sum(xs) / n
    v = sum((x - m) ** 2 for x in xs) / (n - 1)
    return dict(boards=n, mean=m, se=math.sqrt(v / n))


def utc(t):
    return time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(t)) if t else None


def fit_command(args):
    with gzip.open(args.rows, 'rt') as f:
        rows = [json.loads(line) for line in f]
    meta = json.loads(args.rows.with_suffix('').with_suffix('.meta.json').read_text())
    cfg = json.loads(args.bots.read_text())
    impacts = json.loads(args.impacts.read_text())['rows'] if args.impacts.exists() else []
    anchor, weak = cfg['anchor'], cfg['weak_prior_sd']
    smeta = {m['source']: m for m in meta['sources']}
    labels = {}
    for m in meta['sources']:
        for k, v in m['labels'].items():
            labels.setdefault(CANONICAL.get(k, k), v)

    # Variants: a bot's settings as each feed publishes them.
    settings, fp = {}, {}
    for m in meta['sources']:
        for k, spec in m['bots'].items():
            settings[(m['source'], k)] = spec_settings(spec)
    natives = native_results(rows, lambda s, b: (s, b))
    vboards = {}
    for i, j, _ in natives:
        vboards[i] = vboards.get(i, 0) + 1; vboards[j] = vboards.get(j, 0) + 1
    bots = sorted({b for _, b in vboards})
    fps = {}
    for (s, b), n in vboards.items():
        fp[(s, b)] = fingerprint(settings.get((s, b)))
        fps.setdefault(b, {}).setdefault(fp[(s, b)], [0, []])
        fps[b][fp[(s, b)]][0] += n; fps[b][fp[(s, b)]][1].append(s)
    main_fp = {b: max(v, key=lambda f: (f != 'unpublished', v[f][0])) for b, v in fps.items()}

    def vid(s, b):
        f = fp.get((s, b))
        if f is None or len(fps.get(b, {})) < 2 or f == main_fp[b]:
            return b
        return f'{b}#{f}'

    def priors_for(players, main_of):
        out, notes = {}, {}
        for p in players:
            b = p.split('#')[0]
            c = cfg['bots'].get(b, {})
            pr, parent = c.get('prior'), c.get('parent')
            if p == b and pr and parent and main_of(parent) in players:
                out[p] = (main_of(parent), pr['estimate'], prior_sd(pr, cfg))
            else:
                out[p] = (None, 0.0, weak)
                if p == b and pr:
                    notes[p] = 'parent has no boards on the registered feeds: weak prior used'
        return out, notes

    # 1. Fit every variant separately.
    vres = native_results(rows, vid)
    vplayers = sorted({x for i, j, _ in vres for x in (i, j)})
    vpri, _ = priors_for(vplayers, lambda b: b)
    vfit = fit_population(vres, vplayers, anchor, vpri, weak)
    merged, variant_rows = {}, {}
    for b, v in fps.items():
        if len(v) < 2:
            continue
        total = sum(n for n, _ in v.values())
        for f, (n, srcs) in sorted(v.items(), key=lambda kv: -kv[1][0]):
            p = b if f == main_fp[b] else f'{b}#{f}'
            row = dict(id=p, fingerprint=f, boards=n, share=round(n / total, 3), sources=sorted(srcs))
            if p != b:
                d, se = contrast(vfit, vplayers, p, b)
                if f == 'unpublished':
                    # No published settings: nothing says the configuration differs, so the variant joins the point
                    # unless the boards themselves tell it apart.
                    ok, rule = abs(d) < 2 * se, 'settings not published: merged unless the boards tell it apart (2 SE)'
                else:
                    ok, rule = abs(d) < 0.1 and abs(d) < 2 * se, 'merged when under 0.1 IMPs a board and under 2 SE'
                merged[p] = ok
                base, other = settings.get((v[main_fp[b]][1][0], b)), settings.get((srcs[0], b))
                diff = sorted(k for k in set(base or {}) | set(other or {}) if (base or {}).get(k) != (other or {}).get(k))
                row.update(difference=round(d, 4), se=round(se, 4), merged=ok, rule=rule,
                           differs_in=[feature_name(k) for k in diff][:8] if other is not None else ['settings not published'])
            variant_rows.setdefault(b, []).append(row)

    def pid(s, b):
        v = vid(s, b)
        return b if v == b or merged.get(v) else v

    # 2. The ladder: merged variants are one point.
    res = native_results(rows, pid)
    players = sorted({x for i, j, _ in res for x in (i, j)})
    pri, pnotes = priors_for(players, lambda b: b)
    F = fit_population(res, players, anchor, pri, weak)
    field_mean = F['details'].get('field_mean')

    # Timing and introduction, per point.
    tim, intro, envs = {}, {}, {}
    by_source = {}
    for r in rows:
        if kept(r):
            by_source.setdefault(r['source'], []).append(r)
    for s, rs in by_source.items():
        env = smeta[s].get('environment') or 'unknown'
        for r in rs:
            for b in set(members(r['pair'])):
                p = pid(s, b)
                intro[p] = min(intro.get(p, float('inf')), r['completed_epoch'])
        per_record = all(r.get('timing') for r in rs)
        items = [r['timing'] for r in rs] if per_record else [smeta[s].get('feed_timing') or {}]
        for t in items:
            for b, (dec, forced, sec) in t.items():
                p = pid(s, b)
                a = tim.setdefault(p, [0, 0, 0.0]); a[0] += dec; a[1] += forced; a[2] += sec
                e = envs.setdefault(p, {}).setdefault(env, [0, 0, 0.0]); e[0] += dec; e[1] += forced; e[2] += sec

    def timing(p):
        if p not in tim or tim[p][0] - tim[p][1] <= 0:
            return None
        dec, forced, sec = tim[p]
        return dict(seconds_per_choice=round(sec / (dec - forced), 3), decisions_with_choice=dec - forced, forced_decisions=forced,
                    by_environment={e: round(v[2] / (v[0] - v[1]), 3) for e, v in sorted(envs[p].items()) if v[0] > v[1]},
                    source='records\' decision_timing (the data behind the page\'s decision-timing.js): wall-clock seconds of card '
                           'decisions, forced moves\' time included; no bidding; host-dependent')

    def rep_settings(p):
        b = p.split('#')[0]
        f = p.split('#')[1] if '#' in p else main_fp.get(b)
        for (s, bb), ff in fp.items():
            if bb == b and ff == f:
                return settings.get((s, b))
        return None

    points = []
    for k, p in enumerate(players):
        b = p.split('#')[0]
        c = cfg['bots'].get(b, {})
        parent = b if p != b else c.get('parent')
        s, var = float(F['s'][k]), float(F['C'][k, k])
        se = math.sqrt(max(var, 0.0))
        parent_pt = parent if parent in players else None
        pr = pri[p]
        if pr[0] is None:
            prior = dict(kind='weak', estimate=None, sd=weak, mean=round(field_mean, 4) if field_mean is not None else None,
                         source='weak prior at the field mean', note=pnotes.get(p))
        else:
            pc = c['prior']
            prior = dict(kind='parent', parent=pr[0], estimate=pc['estimate'], sd=round(pr[2], 4),
                         mean=round(float(F['s'][players.index(pr[0])]) + pc['estimate'], 4), boards=pc.get('boards'),
                         source=pc['source'], url=pc.get('url'), note=pc.get('note'))
        t = timing(p)
        label = c.get('label') or labels.get(b) or b
        if p != b:
            label += f' (variant {p.split("#")[1]})'
        vp = None
        if parent_pt:
            d, dse = contrast(F, players, p, parent_pt)
            vp = dict(parent=parent_pt, mean=round(d, 4), se=round(dse, 4))
        early = c.get('introduced') if p == b else None       # played before its first registered board (Max, 13 Nov 05:00)
        point = dict(id=p, label=label, group=c.get('group', 'other'), parent=parent,
                     introduced_utc=early['utc'] if early else utc(intro.get(p)), first_registered_board_utc=utc(intro.get(p)),
                     introduced_source=early if early else 'first board on a registered feed',
                     boards=F['boards'][p], strength=round(s, 4), se=round(se, 4),
                     ci95=[round(s - 1.96 * se, 4), round(s + 1.96 * se, 4)], prior=prior,
                     prior_share=round(F['share'][p], 3), hollow=F['share'][p] > 0.5, timing=t,
                     point_label=f"{label}, {t['seconds_per_choice']:.2f} s" if t else label,
                     vs_parent=vp, variants=[v for v in variant_rows.get(b, []) if p == b and (v['id'] == b or merged.get(v['id']))]
                     if p == b else [v for v in variant_rows.get(b, []) if v['id'] == p],
                     features=features(rep_settings(p), rep_settings(parent) if parent else None, impacts),
                     candidate=False)
        if p == anchor:
            point['anchor'] = True
        points.append(point)
    points.sort(key=lambda x: x['introduced_utc'] or '')

    # Optional candidates, not in the arena: parent's posterior plus an outside estimate.
    candidates = []
    for cid, c in (cfg.get('candidates') or {}).items():
        if c.get('estimate_source') == 'arrival':        # recompute from an arena9 control directory
            if not args.arrival:
                continue
            est = arrival_estimate(args.arrival, cid, c.get('vs', '8p-32'))
        else:                                           # the estimate as written in the config
            est = dict(boards=c.get('boards'), mean=c['estimate'], se=c['se'])
        vs = c.get('vs')
        par = c['parent']
        k = players.index(par)
        m = float(F['s'][k]) + est['mean']
        se = math.sqrt(float(F['C'][k, k]) + est['se'] ** 2)
        candidates.append(dict(id=cid, label=c['label'], group=c['group'], parent=par, introduced_utc=c.get('introduced_utc'),
                               boards=est['boards'], strength=round(m, 4), se=round(se, 4),
                               ci95=[round(m - 1.96 * se, 4), round(m + 1.96 * se, 4)], prior=None, prior_share=None,
                               hollow=False, timing=None, point_label=c['label'],
                               estimate=dict(vs=vs, placed_on=par, mean=round(est['mean'], 4), se=round(est['se'], 4),
                                             boards=est['boards'], source=c['source'], url=c.get('url'), note=c.get('note')),
                               features=[], variants=[], candidate=True))

    split = sorted(v for v, ok in merged.items() if not ok)
    doc = dict(
        schema='arena-ladder-v1', computed_utc=time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime()),
        anchor=anchor, condition='native', unit='IMPs a board',
        model=dict(name='ratings-v1 with priors (bridge_harness/arena_ratings.py; scripts/arena_ladder.py)',
                   t2=round(F['t2'], 5), Q=round(F['details'].get('Q', float('nan')), 2), df=F['details'].get('df'),
                   field_mean=round(field_mean, 4) if field_mean is not None else None,
                   weak_prior_sd=weak, imps_per_trick=cfg['imps_per_trick'], conversion_error=cfg['conversion_error']),
        sources=dict(feeds=len(meta['sources']), failed=len(meta.get('failed', [])), boards_fetched=meta['rows'],
                     boards_fitted=len(res), collected_utc=meta['computed_utc'], registry_sha256=meta['registry_sha256']),
        notes=[
            f"Strength: IMPs a board against {labels.get(anchor, anchor)}, the anchor (fixed at 0). {cfg['anchor_note']}",
            'Introduced: a bot\'s first board on a registered feed, unless it is known to have played earlier (introduced_source gives the evidence; Gen 1 predates the arena).',
            'Each side bids with its own bidder (the native condition): the whole bot. Common-auction boards are not used.',
            'Counting is the page\'s: records after a feed\'s snapshot, the hidden BEN (32) and the accidental cohorts are out; '
            'a feed\'s allowed pairs are respected; a deal family counts once per pair, earliest first; self-play carries no strength.',
            'Priors come only from estimates outside the registered feeds (box matches), so no board counts twice; every other bot has '
            f'a weak prior (SD {weak} IMPs a board) at the field mean, a free parameter. A hollow point takes more than half its '
            'information from its own prior: prior share = 1 - (variance with its prior) / (variance without it).',
            'Time per decision: wall-clock seconds per card decision with a choice, from the records\' decision timing; card play only, '
            'host-dependent (Azure boxes, Codex and ChatGPT sandboxes differ), not CPU time.',
            'Variants: a bot whose published settings differ between feeds (file paths and names ignored) is fitted per variant; a variant '
            'is merged into the bot\'s point when it differs by under 0.1 IMPs a board and by under two standard errors; a variant whose '
            'feed publishes no settings is merged unless its boards differ by two standard errors.'
            + (f" Not merged: {', '.join(split)}." if split else ''),
            'Candidates are not in the arena: placed at a registered bot\'s strength plus an outside match estimate, and marked.'],
        points=points, candidates=candidates)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=1) + '\n')
    print(f"{len(points)} points, {len(candidates)} candidates, {len(res):,} boards, t2 {F['t2']:.4f}; split variants: {split} -> {args.out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('collect')
    c.add_argument('--out', type=Path, required=True)
    c.add_argument('--cache', type=Path, default=Path.home() / '.cache' / 'arena-feeds')
    c.add_argument('--workers', type=int, default=8)
    f = sub.add_parser('fit')
    f.add_argument('--rows', type=Path, required=True)
    f.add_argument('--bots', type=Path, default=ROOT / 'configs' / 'ladder-bots.json')
    f.add_argument('--impacts', type=Path, default=ROOT / 'configs' / 'ladder-feature-impacts.json')
    f.add_argument('--arrival', type=Path, help='an arena9 control directory with the 9a-32 candidate\'s results')
    f.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    if args.cmd == 'collect':
        collect(args)
    else:
        fit_command(args)


if __name__ == '__main__':
    main()
