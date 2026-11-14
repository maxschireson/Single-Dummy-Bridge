#!/usr/bin/env python3
"""Tricks lost per average board, three ways, with validation inside adult categories. TEST DATA ONLY.

Difficulty of a board for a player in a role is estimated two ways:
  curve  expected tricks lost given the board's danger (what a random card would lose there, summed over the
         player's decisions), read off a curve fitted on all adult boards (25 quantile bins, interpolated)
  field  the same deal's other tables in the same role and seat relative to declarer (left-one-out mean)
Per average board = the player's mean (loss - expected) + the average adult board's loss. Also the proportional
danger scale (sum loss / sum danger * average danger), which assumes loss grows in proportion to danger.
Validation: split-half (deal parity) and two-event correlations, centred within category or event, so level
differences between categories do not count as reliability.
"""
import argparse, collections, math, sys
import numpy as np

sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from analyze import load, units  # noqa: E402

ADULT = ('Open', 'Senior', 'Mixed', "Women's")
ROLES = ('declarer', 'defense', 'lead')
MEASURES = ('raw', 'prop', 'curve', 'field', 'both')


def expectations(T, U):
    """Per unit: loss, danger, role, adult flag; curve, field and blended expectations; the average adult board
    per role; the same-deal groups (deal, role, seat relative to declarer)."""
    rel = lambda t, s: 'D' if s == t['dec'] else 'L' if s == 'NESW'[('NESW'.index(t['dec']) + 1) % 4] else 'R'
    adult = lambda u: T[u[0]]['category'] in ADULT
    loss = np.array([u[5] for u in U]); dng = np.array([u[9] for u in U]); role_of = np.array([u[1] for u in U])
    isad = np.array([adult(u) for u in U])

    # the average adult board and the curve, per role
    ref, exp_curve = {}, np.zeros(len(U))
    for role in ROLES:
        m = (role_of == role) & isad
        ref[role] = dict(loss=loss[m].mean(), danger=dng[m].mean())
        pos = m & (dng > 0)
        qs = np.quantile(dng[pos], np.linspace(0, 1, 26))
        xs, ys = [], []
        for lo, hi in zip(qs[:-1], qs[1:]):
            b = pos & (dng >= lo) & (dng <= hi)
            xs.append(dng[b].mean()); ys.append(loss[b].mean())
        zero = loss[m & (dng <= 0)].mean()
        r = role_of == role
        exp_curve[r] = np.where(dng[r] > 0, np.interp(dng[r], xs, ys), zero)
        ref[role]['curve'] = (xs, ys, zero)

    # field expectation (left-one-out, same deal, role, relative seat)
    groups = collections.defaultdict(list)
    for k, u in enumerate(U):
        groups[(T[u[0]]['deal'], u[1], rel(T[u[0]], u[2]))].append(k)
    exp_field = np.full(len(U), np.nan)
    for ks in groups.values():
        if len(ks) > 1:
            tot = loss[ks].sum()
            exp_field[ks] = (tot - loss[ks]) / (len(ks) - 1)
    # both: the field's mean shrunk toward the curve by the number of other tables (a simple empirical-Bayes blend)
    nf = np.array([len(groups[(T[u[0]]['deal'], u[1], rel(T[u[0]], u[2]))]) - 1 for u in U])
    exp_both = np.where(np.isnan(exp_field), exp_curve, 0.)
    for role in ROLES:
        m = (role_of == role) & isad & ~np.isnan(exp_field)
        # between-board variance of true difficulty around the curve, and per-table noise, from the adult data
        resid_var = np.var(loss[m] - exp_curve[m])            # one table's loss around the curve
        fv = np.var(exp_field[m] - exp_curve[m]) - np.mean(resid_var / np.maximum(nf[m], 1))   # field mean's true part
        tau2 = max(fv, 1e-6)
        r = (role_of == role) & ~np.isnan(exp_field)
        w = tau2 / (tau2 + resid_var / np.maximum(nf[r], 1))
        exp_both[r] = exp_curve[r] + w * (exp_field[r] - exp_curve[r])
        ref[role]['blend'] = (tau2, resid_var, float(np.median(w)))

    return dict(rel=rel, adult=adult, loss=loss, dng=dng, role_of=role_of, isad=isad, ref=ref, exp_curve=exp_curve,
                exp_field=exp_field, exp_both=exp_both, groups=groups, nf=nf)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--player', default='Schireson')
    a = ap.parse_args()
    T = load(a.dirs)
    U = units(T)
    E = expectations(T, U)
    rel, adult, loss, dng, role_of, isad, ref = (E[k] for k in ('rel', 'adult', 'loss', 'dng', 'role_of', 'isad', 'ref'))
    exp_curve, exp_field, exp_both, groups = (E[k] for k in ('exp_curve', 'exp_field', 'exp_both', 'groups'))

    def score(ks, how, role):
        ks = np.asarray(ks)
        L = ref[role]['loss']
        if how == 'raw':
            return loss[ks].mean()
        if how == 'prop':
            return loss[ks].sum() / max(dng[ks].sum(), 1e-9) * ref[role]['danger']
        e = {'curve': exp_curve, 'field': exp_field, 'both': exp_both}[how][ks]
        ok = ~np.isnan(e)
        return (loss[ks][ok] - e[ok]).mean() + L if ok.any() else float('nan')

    def se(ks, how, role):
        ks = np.asarray(ks)
        if how == 'raw':
            return loss[ks].std(ddof=1) / math.sqrt(len(ks))
        if how == 'prop':
            R = loss[ks].sum() / dng[ks].sum()
            return math.sqrt(((loss[ks] - R * dng[ks]) ** 2).sum() * len(ks) / (len(ks) - 1)) / dng[ks].sum() * ref[role]['danger']
        e = {'curve': exp_curve, 'field': exp_field, 'both': exp_both}[how][ks]
        d = (loss[ks] - e)[~np.isnan(e)]
        return d.std(ddof=1) / math.sqrt(len(d))

    print(f'{len(T)} tables. Average adult board: ' + '; '.join(f'{r} lost {ref[r]["loss"]:.3f}, danger {ref[r]["danger"]:.2f}' for r in ROLES))
    print('Blend weight on the field (median board): ' + ', '.join(f'{r} {ref[r]["blend"][2]:.2f}' for r in ROLES))

    # validation
    print('\nValidation inside adult categories (player scores centred on their category or event mean)')
    print(f'  {"":8s} {"measure":6s} | split-half reliability, 40+ boards | two events, 20+ boards each: r')
    for role in ROLES:
        for how in MEASURES:
            # split half: per (player, category), boards split by deal parity
            per = collections.defaultdict(list)
            for k, u in enumerate(U):
                if u[1] == role and u[3] and adult(u):
                    per[(u[3], T[u[0]]['category'])].append(k)
            H = collections.defaultdict(list)
            for (p, cat), ks in per.items():
                if len(ks) < 40:
                    continue
                h = [[k for k in ks if int(T[U[k][0]]['deal'][-1], 16) % 2 == g] for g in (0, 1)]
                if min(map(len, h)) < 10:
                    continue
                H[cat].append((score(h[0], how, role), score(h[1], how, role)))
            xs = []
            for cat, v in H.items():
                v = np.array(v)
                xs.extend(v - v.mean(0))
            xs = np.array(xs)
            r = np.corrcoef(xs[:, 0], xs[:, 1])[0, 1]
            rel_ = 2 * r / (1 + r)
            # two events: (category, year) as an event
            ev = collections.defaultdict(lambda: collections.defaultdict(list))
            for k, u in enumerate(U):
                if u[1] == role and u[3] and adult(u):
                    ev[u[3]][(T[u[0]]['category'], T[u[0]]['year'])].append(k)
            pairs, evs = [], collections.defaultdict(list)
            for p, e in ev.items():
                es = sorted([(key, ks) for key, ks in e.items() if len(ks) >= 20])
                if len(es) >= 2:
                    pairs.append((es[0][0], es[1][0], score(es[0][1], how, role), score(es[1][1], how, role)))
            for e1, e2, s1, s2 in pairs:
                evs[e1].append(s1); evs[e2].append(s2)
            mu = {e: np.mean(v) for e, v in evs.items()}
            x = np.array([(s1 - mu[e1], s2 - mu[e2]) for e1, e2, s1, s2 in pairs])
            r2 = np.corrcoef(x[:, 0], x[:, 1])[0, 1]
            print(f'  {role:8s} {how:6s} | {rel_:+.2f} ({len(xs)} player-categories) | {r2:+.2f} ({len(pairs)} players)')

    # the player and the field
    mine = {u[3] for u in U if u[4] and a.player.lower() in u[4].lower()}
    print(f'\n{a.player}: per average board, +- standard error; the same events\' other players (20+ boards in the role)')
    for role in ROLES:
        ks = [k for k, u in enumerate(U) if u[1] == role and u[3] in mine]
        if not ks:
            continue
        ev = {(T[U[k][0]]['category'], T[U[k][0]]['year'], T[U[k][0]]['stage']) for k in ks}
        same_deals = [k2 for k in ks for k2 in groups[(T[U[k][0]]['deal'], role, rel(T[U[k][0]], U[k][2]))] if U[k2][3] not in mine]
        per = collections.defaultdict(list)
        for k, u in enumerate(U):
            if u[1] == role and u[3] and u[3] not in mine and (T[u[0]]['category'], T[u[0]]['year'], T[u[0]]['stage']) in ev:
                per[u[3]].append(k)
        print(f'  {role}: {len(ks)} boards (raw {loss[ks].mean():.3f}; danger {dng[ks].mean():.2f} vs {ref[role]["danger"]:.2f} average; '
              f'curve expects {exp_curve[ks].mean():.3f}, the other tables lost {np.nanmean(exp_field[ks]):.3f}, average board {ref[role]["loss"]:.3f})')
        for how in MEASURES:
            sc = np.array([score(v, how, role) for v in per.values() if len(v) >= 20])
            noise = np.mean([se(v, how, role) ** 2 for v in per.values() if len(v) >= 20])
            true = math.sqrt(max(sc.var(ddof=1) - noise, 0.))
            me = score(ks, how, role)
            fd = score(same_deals, how, role)
            print(f'    {how:6s} him {me:.3f} +- {se(ks, how, role):.3f} | other tables, same deals {fd:.3f} | players {sc.mean():.3f}, '
                  f'SD {sc.std(ddof=1):.3f}, beyond luck {true:.3f} | him {(me - sc.mean()) / sc.std(ddof=1):+.2f} SD, '
                  f'{(sc < me).mean():.0%} lose less')


if __name__ == '__main__':
    main()
