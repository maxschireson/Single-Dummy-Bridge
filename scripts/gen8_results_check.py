#!/usr/bin/env python3
"""Every match on the Gen 8 result branches, recomputed from its results.jsonl alone.

  python scripts/gen8_results_check.py --repo CLONE --ref azure1=REF [--ref ...] [--families v41_training_families.txt.gz]
                                       [--pair BOX/MATCH BOX/MATCH ...] [--bots] [--json OUT]

Written to check the Gen 8 session's gate table without its tools (box/coordination, 12 Nov 2026, Task 3). For each
match directory under each ref (a commit or branch already fetched into CLONE):

- boards, and IMPs a board for the first-named bot with a standard error (boards as units), in the common regime (both
  bots bid alike) and the native one (each bids its own way), with boards won, flat and lost; by declared systems when
  the rows carry them;
- the same from the match's own summary.json. A summary written before the last rows is compared with the first rows
  of the file that it counts ("agrees at N");
- checks of the rows: each board index and each deal family once; boards missing below the last one played; the IMPs
  of every board equal to the standard IMP scale applied to its score difference; how many deals are in a list of
  families (--families: the deals a net trained on);
- across matches: which share deals (deals are a function of seed and index), and for the same pair of bots on the same
  deals, whether the two boxes produced the same boards;
- --pair A B: the first match minus the second on the deals both played, and how the two correlate board by board;
- --bots: the settings in which the two bots of each match differ, from its manifest.

The result files hold one line a board (IMPs, score difference, contract), not the tables, so the scores themselves
cannot be recomputed from them; this checks the arithmetic above them. A manifest names a bot's policy net by path
and carries no hash of it, so which file a box loaded is not checked here either.
"""
import argparse
import collections
import gzip
import json
import math
import subprocess

IMP_STEPS = (20, 50, 90, 130, 170, 220, 270, 320, 370, 430, 500, 600, 750, 900, 1100, 1300, 1500, 1750, 2000, 2250, 2500, 3000, 3500, 4000)


def imps(score):
    return int(math.copysign(sum(abs(score) >= s for s in IMP_STEPS), score)) if score else 0


def git(repo, *a):
    return subprocess.run(['git', '-C', repo, *a], capture_output=True, text=True).stdout


def stats(x):
    n = len(x)
    mean = sum(x) / n
    se = math.sqrt(sum((v - mean) ** 2 for v in x) / (n - 1) / n) if n > 1 else float('nan')
    return dict(boards=n, mean=mean, se=se, won=sum(v > 0 for v in x), flat=sum(v == 0 for v in x), lost=sum(v < 0 for v in x))


def agrees(own, rows):
    """Does a summary.json say what its first `boards` rows say?"""
    for k in ('common', 'native'):
        o = own[k]
        s = stats([float(r[k]) for r in rows[:o['boards']]])
        if not (abs(o['imps_per_board'] - s['mean']) < 6e-5 and abs(o['se'] - s['se']) < 6e-5 and o['boards'] == s['boards']
                and (o['won'], o['flat'], o['lost']) == (s['won'], s['flat'], s['lost'])):
            return False
    return True


def flat(d, pre=''):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(flat(v, pre + k + '.'))
        else:
            out[pre + k] = v
    return out


def fmt(s):
    return f"{s['mean']:+.3f} +- {s['se']:.3f} ({s['won']}/{s['flat']}/{s['lost']})"


def correlation(x, y):
    mx, my = sum(x) / len(x), sum(y) / len(y)
    sxx, syy = sum((u - mx) ** 2 for u in x), sum((v - my) ** 2 for v in y)
    return sum((u - mx) * (v - my) for u, v in zip(x, y)) / math.sqrt(sxx * syy) if sxx and syy else float('nan')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--ref', action='append', required=True, metavar='NAME=REF')
    ap.add_argument('--families')
    ap.add_argument('--pair', nargs=2, action='append', default=[], metavar='BOX/MATCH')
    ap.add_argument('--bots', action='store_true')
    ap.add_argument('--json')
    a = ap.parse_args()
    trained = set()
    if a.families:
        with gzip.open(a.families, 'rt') as f:
            trained = set(f.read().split())
    matches = {}
    for spec in a.ref:
        box, ref = spec.split('=', 1)
        print(f"{box}: {ref} committed {git(a.repo, 'log', '-1', '--format=%cI', ref).strip()}")
        for path in git(a.repo, 'ls-tree', '-r', '--name-only', ref).split():
            if not path.endswith('results.jsonl'):
                continue
            name = path.rsplit('/', 1)[0]
            rows = [json.loads(x) for x in git(a.repo, 'show', f'{ref}:{path}').splitlines() if x.strip()]
            own = git(a.repo, 'show', f'{ref}:{name}/summary.json')
            man = git(a.repo, 'show', f'{ref}:{name}/manifest.json')
            if len(rows) >= 3:
                matches[f'{box}/{name}'] = dict(box=box, name=name, rows=rows, own=json.loads(own) if own.strip() else None, man=json.loads(man) if man.strip() else {})
    out = {}
    print(f"\n{'match':33s}{'pair':30s}{'seed':>5s}{'boards':>7s}  {'common IMPs a board':30s}{'native':30s}{'own summary':15s}row checks")
    for key, m in matches.items():
        rows = m['rows']
        pair = f"{rows[0].get('candidate')}~{rows[0].get('opponent')}"
        common, native = stats([float(r['common']) for r in rows]), stats([float(r['native']) for r in rows])
        index, fam = collections.Counter(r['index'] for r in rows), collections.Counter(r['family'] for r in rows)
        bad_imps = sum(imps(r['common_score']) != r['common'] for r in rows) + sum(imps(r['native_score']) != r['native'] for r in rows)
        seen = sum(f in trained for f in fam)
        first = m['man'].get('first', 0) or 0
        missing = sorted(set(range(first, max(index) + 1)) - set(index))
        own = 'none'
        if m['own']:
            n = m['own']['common']['boards']
            own = ('agrees' if n == len(rows) else f'agrees at {n}') if agrees(m['own'], rows) else 'DIFFERS'
        checks = []
        if max(index.values()) > 1:
            checks.append(f"{sum(v > 1 for v in index.values())} board indices repeated")
        if max(fam.values()) > 1:
            checks.append(f"{sum(v > 1 for v in fam.values())} deals repeated")
        if bad_imps:
            checks.append(f"{bad_imps} boards whose IMPs are not the scale of their score")
        if missing:
            checks.append(f"{len(missing)} missing below the last board played")
        if trained and seen:
            checks.append(f"{seen} DEALS IN THE FAMILY LIST")
        same = 'same as common' if all(r['common'] == r['native'] for r in rows) else fmt(native)
        print(f"{key[:32]:33s}{pair[:29]:30s}{str(m['man'].get('seed')):>5s}{len(rows):7d}  {fmt(common):30s}{same:30s}{own:15s}{'; '.join(checks) or 'clean'}")
        kinds = collections.defaultdict(list)
        for r in rows:
            if r.get('systems'):
                kinds[r['systems']].append(r)
        by = {}
        for kind, v in sorted(kinds.items()) if len(kinds) > 1 else ():
            by[kind] = dict(common=stats([float(r['common']) for r in v]), native=stats([float(r['native']) for r in v]))
            print(f"{'':33s}  tables {kind:36s}{len(v):7d}  {fmt(by[kind]['common'])}")
        out[key] = dict(box=m['box'], match=m['name'], pair=pair, seed=m['man'].get('seed'), first=first, last=max(index), common=common, native=native,
                        own_summary=own, by_systems=by, repeated_indices=sum(v > 1 for v in index.values()), repeated_deals=sum(v > 1 for v in fam.values()),
                        imps_not_scale=bad_imps, missing_below_last=len(missing), deals_in_family_list=seen if trained else None,
                        source_commit=m['man'].get('source_commit'))
    if trained:
        total = len({r['family'] for m in matches.values() for r in m['rows']})
        hit = len({r['family'] for m in matches.values() for r in m['rows']} & trained)
        print(f"\n{hit} of the {total} distinct deals played are among the {len(trained)} families of the list")

    print('\nmatches on the same deals (same seed, overlapping board indices):')
    seeds = collections.defaultdict(list)
    for key, m in matches.items():
        seeds[m['man'].get('seed')].append(key)
    shared = []
    for seed, keys in sorted(seeds.items(), key=lambda kv: str(kv[0])):
        if len(keys) > 1:
            print(f"  seed {seed}: " + ', '.join(f"{k} ({out[k]['first']}-{out[k]['last']})" for k in keys))
        for i, x in enumerate(keys):
            for y in keys[i + 1:]:
                fx, fy = {r['family']: r for r in matches[x]['rows']}, {r['family']: r for r in matches[y]['rows']}
                both = sorted(set(fx) & set(fy))
                if not both:
                    continue
                same_pair = out[x]['pair'] == out[y]['pair']
                same_rows = sum(fx[f]['common'] == fy[f]['common'] and fx[f]['native'] == fy[f]['native'] and fx[f].get('contract') == fy[f].get('contract') for f in both)
                shared.append(dict(a=x, b=y, deals=len(both), same_pair=same_pair, identical_boards=same_rows if same_pair else None))
                if same_pair:
                    print(f"    THE SAME PAIR OF BOTS: {x} and {y} share {len(both)} deals; {same_rows} of them have the same contract and IMPs in both")
    pairs = []
    if a.pair:
        print('\nfirst minus second on the deals both played (IMPs a board, common regime), and their correlation board by board:')
    for x, y in a.pair:
        if x not in matches or y not in matches:
            print(f'  {x} or {y}: no such match')
            continue
        fx, fy = {r['family']: float(r['common']) for r in matches[x]['rows']}, {r['family']: float(r['common']) for r in matches[y]['rows']}
        both = sorted(set(fx) & set(fy))
        if len(both) < 3:
            print(f'  {x} and {y}: {len(both)} deals in common')
            continue
        s = stats([fx[f] - fy[f] for f in both])
        rho = correlation([fx[f] for f in both], [fy[f] for f in both])
        pairs.append(dict(a=x, b=y, deals=len(both), difference=s['mean'], se=s['se'], correlation=rho))
        print(f"  {x} minus {y}: {s['mean']:+.3f} +- {s['se']:.3f} on {len(both)} deals; correlation {rho:+.2f}")

    if a.bots:
        print('\nwhere the two bots of each match differ (manifest; first | second):')
        for key, m in matches.items():
            bots = m['man'].get('bots') or {}
            roster = m['man'].get('roster') or []
            if len(roster) != 2 or any(b not in bots for b in roster):
                continue
            x, y = flat(bots[roster[0]]), flat(bots[roster[1]])
            diff = sorted(k for k in set(x) | set(y) if x.get(k) != y.get(k) and k not in ('id', 'identity', 'table_opponent', 'label'))
            groups = collections.OrderedDict()
            for k in diff:
                head = k.split('.')[0] + '.' + k.split('.')[1] if k.startswith(('gen7.opponent_play_weight.', 'bidder.options.')) else k
                groups.setdefault(head, []).append(k)
            def short(v):
                v = str(v)
                v = v.split('/models/cardplay/')[-1] if '/models/cardplay/' in v else v
                return v if len(v) < 48 else v[:22] + '..' + v[-22:]
            text = []
            for head, ks in groups.items():
                if len(ks) > 1 or head != ks[0]:
                    text.append(f"{head}.* ({len(ks)} settings, {'first' if any(k in x for k in ks) else 'second'} only)" if not all(k in x and k in y for k in ks) else f"{head}.* ({len(ks)} settings differ)")
                else:
                    text.append(f"{head}: {short(x.get(head, '-'))} | {short(y.get(head, '-'))}")
            print(f"  {key} [{str(m['man'].get('source_commit'))[:7]}] {roster[0]} ~ {roster[1]}: " + ('; '.join(text) or 'nothing'))
            out[key]['bots_differ'] = diff
    if a.json:
        with open(a.json, 'w') as f:
            json.dump(dict(matches=list(out.values()), shared=shared, pairs=pairs), f, indent=1)


if __name__ == '__main__':
    main()
