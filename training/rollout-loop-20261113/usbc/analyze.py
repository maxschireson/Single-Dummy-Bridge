#!/usr/bin/env python3
"""Tricks lost against double dummy in the USBCs: by event, category and stage, by player, raw and normalized, with checks
of which measure is steadiest (Max, 07:12 to 07:53 UTC on 14 November 2026). TEST DATA ONLY.

  python3 analyze.py LT_DIR [LT_DIR ...] [--player NAME] [--min-boards 40] [--json OUT.json]

Input: lost_tricks.py's files (*.lt2.json.gz). A table's decisions are split three ways: declarer (declarer's own and
dummy's cards, and a claim's shortfall), defense (each defender's cards after the opening lead, and half each of an
accepted claim's excess), and the opening lead. Per role, per board in that role:
  tricks   tricks lost against double dummy               plays   cards that lost a trick or more
  imps     the cards' double-dummy cost in IMPs             turned  cards that changed make or set
Normalized:
  vs field   the same deal's other tables in the same role (left-one-out mean): the board's difficulty taken out. It
             compares players within an event (the field), not events with each other.
  vs danger  each card's loss over what a random legal card would have lost there, pooled: the share of the position's
             danger that was realized. It needs no field, so events and bots go on one scale.
Checks: split-half reliability (each player's boards split by deal; the two halves' player means correlated across
players, then Spearman-Brown) and, for players in two events or more, how well one event's score predicts another's.
"""
import argparse, collections, glob, gzip, json, math, re
from pathlib import Path

import numpy as np

ROLE = {'D': 'declarer', 'CD': 'declarer', 'F': 'defense', 'CF': 'defense', 'L': 'lead'}


def category(event, text):
    s = f'{event} {text}'
    for name, pat in (('Junior U16', r'U-?16'), ('Junior U21', r'U-?21'), ('Junior U26', r'U-?26'), ('Junior', r'Junior|JUSBC|Seamon|Amer'),
                      ("Women's", r"Women|Palmer|WUSBC"), ('Senior', r'Senior|SUSBC'), ('Mixed', r'Mixed|MUSBC'), ('Open', r'Open|USBC')):
        if re.search(pat, s, re.I):
            return name
    return 'Other'


def stage(event):
    s = event or ''
    for name, pat in (('Final', r'(?<!Semi)(?<!Quarter)Final'), ('Semifinal', r'Semi'), ('Quarterfinal', r'Quarter'), ('Round of 16', r'Round of 16|R16'),
                      ('Round of 32', r'Round of 32'), ('Round robin', r'Round Robin|RR\b|Qualif'), ('Knockout', r'Knockout|KO')):
        if re.search(pat, s, re.I):
            return name
    return 'Other'


def load(dirs):
    tables = []
    for d in dirs:
        for f in sorted(glob.glob(str(Path(d) / '*.lt2.json.gz'))):
            for line in gzip.open(f, 'rt'):
                r = json.loads(line)
                if 'error' in r or not r.get('decisions'):
                    continue
                r['year'] = (r.get('start') or '????')[:4]
                r['category'] = category(r.get('event') or '', r.get('text') or '')
                r['stage'] = stage(r.get('event') or '')
                tables.append(r)
    seen, out = set(), []
    for r in tables:                                            # the same table fetched twice (two boxes) counts once
        key = (r['sid'], r['board'], r.get('room'))
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def units(tables):
    """One row per player and board in a role: (table index, role, seat, player id, name, tricks, plays, imps, turned, rand)."""
    rows = []
    for i, r in enumerate(tables):
        dec = r['dec']
        dseats = {dec, 'NESW'[('NESW'.index(dec) + 2) % 4]}
        acc = collections.defaultdict(lambda: [0., 0, 0., 0, 0., 0])
        for d in r['decisions']:
            role = ROLE[d[2]]
            imp, turned = (d[7], d[8]) if len(d) > 8 else (None, None)
            if d[2] == 'CD':
                keys = [(role, dec)]
            elif d[2] == 'CF':
                keys = [(role, s) for s in 'NESW' if s not in dseats]
            else:
                keys = [(role, dec if role == 'declarer' else d[1])]
            for k in keys:
                share = 1. / len(keys)
                a = acc[k]
                a[0] += d[3] * share
                a[1] += int(d[3] > 0) if d[2] not in ('CD', 'CF') else 0
                a[2] += (imp or 0) * share
                a[3] += turned or 0
                a[4] += d[4] or 0.
                a[5] += 1
        for s in 'NESW':                                        # every defender and the declarer has a row, errors or not
            if s in dseats and s != dec:
                continue
            for role in (('declarer',) if s == dec else ('defense', 'lead') if s == 'NESW'[('NESW'.index(dec) + 1) % 4] else ('defense',)):
                a = acc[(role, s)]
                name = ((r.get('names') or {}).get(s) or '').strip()
                who = ' '.join(name.lower().split()) or (r.get('pids') or {}).get(s)     # players are matched across events by name
                rows.append((i, role, s, who, name, *a))
    return rows


def stat(x):
    x = np.asarray(x, float)
    if len(x) < 2:
        return float('nan'), float('nan'), len(x)
    return float(x.mean()), float(x.std(ddof=1) / math.sqrt(len(x))), len(x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--player', default='Schireson')
    ap.add_argument('--min-boards', type=int, default=40)
    ap.add_argument('--json')
    a = ap.parse_args()
    tables = load(a.dirs)
    U = units(tables)
    print(f'{len(tables)} tables, {len({t["deal"] for t in tables})} deals, {len({(t["sid"]) for t in tables})} sessions, '
          f'{len({u[3] for u in U if u[3]})} players')
    # field baselines: the same deal, the same role and seat relative to declarer, other tables
    rel = lambda t, s: 'D' if s == t['dec'] else 'L' if s == 'NESW'[('NESW'.index(t['dec']) + 1) % 4] else 'R'
    groups = collections.defaultdict(list)
    for k, u in enumerate(U):
        t = tables[u[0]]
        groups[(t['deal'], u[1], rel(t, u[2]))].append(k)
    field = np.full((len(U), 4), np.nan)                        # left-one-out field mean of tricks, plays, imps, turned
    for ks in groups.values():
        if len(ks) < 2:
            continue
        v = np.array([[U[k][5], U[k][6], U[k][7], U[k][8]] for k in ks], float)
        tot = v.sum(0)
        for j, k in enumerate(ks):
            field[k] = (tot - v[j]) / (len(ks) - 1)
    # 1. by category, year and stage, raw per board in the role; the danger-normalized share
    print('\n1. Raw, per board in the role (a defense row is one defender; the lead is the opening leader)')
    print(f'{"category":12s} {"year":4s} {"stage":13s} | {"declarer: tricks plays imps turned":38s} | {"defense (each)":26s} | {"lead":18s} | danger share D/F/L')
    by = collections.defaultdict(list)
    for k, u in enumerate(U):
        t = tables[u[0]]
        by[(t['category'], t['year'], t['stage'])].append(k)
    rows_out = []
    for key in sorted(by):
        ks = by[key]
        line = {}
        for role in ('declarer', 'defense', 'lead'):
            rr = [U[k] for k in ks if U[k][1] == role]
            if rr:
                v = np.array([[r[5], r[6], r[7], r[8], r[9]] for r in rr], float)
                line[role] = dict(n=len(rr), tricks=v[:, 0].mean(), plays=v[:, 1].mean(), imps=v[:, 2].mean(), turned=v[:, 3].mean(),
                                  danger=v[:, 0].sum() / max(v[:, 4].sum(), 1e-9))
        rows_out.append(dict(category=key[0], year=key[1], stage=key[2], **line))
        D, F, L = line.get('declarer', {}), line.get('defense', {}), line.get('lead', {})
        print(f'{key[0]:12s} {key[1]:4s} {key[2]:13s} | {D.get("tricks", 0):.3f} {D.get("plays", 0):.3f} {D.get("imps", 0):.2f} {D.get("turned", 0):.3f} ({D.get("n", 0):5d}) | '
              f'{F.get("tricks", 0):.3f} {F.get("plays", 0):.3f} {F.get("imps", 0):.2f} | {L.get("tricks", 0):.3f} {L.get("imps", 0):.2f} | '
              f'{D.get("danger", 0):.3f} {F.get("danger", 0):.3f} {L.get("danger", 0):.3f}')
    # 2. per player: raw, vs field, vs danger; split-half reliability; across events
    print(f'\n2. Players with at least {a.min_boards} boards in the role: which measure is steadiest')
    report = {}
    for role in ('declarer', 'defense', 'lead'):
        ks = [k for k, u in enumerate(U) if u[1] == role and u[3]]
        per = collections.defaultdict(list)
        for k in ks:
            per[U[k][3]].append(k)
        players = [p for p, v in per.items() if len(v) >= a.min_boards]
        print(f'  {role}: {len(players)} players')
        measures = {}
        for name, col in (('tricks', 5), ('plays', 6), ('imps', 7), ('turned', 8)):
            for norm in ('raw', 'vs field', 'vs danger'):
                if norm == 'vs danger' and name != 'tricks':
                    continue
                halves = []
                for p in players:
                    h = [[], []]
                    for k in per[p]:
                        t = tables[U[k][0]]
                        g = int(t['deal'][-1], 16) % 2
                        if norm == 'raw':
                            h[g].append((U[k][col], 1.))
                        elif norm == 'vs field':
                            if not np.isnan(field[k][col - 5]):
                                h[g].append((U[k][col] - field[k][col - 5], 1.))
                        else:
                            h[g].append((U[k][5], U[k][9]))
                    if min(len(h[0]), len(h[1])) < 5:
                        continue
                    f = (lambda xs: sum(x for x, _ in xs) / max(sum(w for _, w in xs), 1e-9)) if norm == 'vs danger' else (lambda xs: sum(x for x, _ in xs) / len(xs))
                    halves.append((f(h[0]), f(h[1])))
                if len(halves) > 10:
                    x = np.array(halves)
                    r = float(np.corrcoef(x[:, 0], x[:, 1])[0, 1])
                    measures[(name, norm)] = dict(players=len(halves), split_half=r, reliability=2 * r / (1 + r) if r > -1 else float('nan'))
        for (name, norm), m in sorted(measures.items(), key=lambda kv: -kv[1]['reliability']):
            print(f'    {name:7s} {norm:9s} split-half r {m["split_half"]:+.3f}  reliability {m["reliability"]:+.3f}  ({m["players"]} players)')
        report[role] = {f'{k[0]} {k[1]}': v for k, v in measures.items()}
        # across events: players in two events or more (an event is a category and a year), the danger measure and vs field
        ev = collections.defaultdict(lambda: collections.defaultdict(list))
        for k in ks:
            t = tables[U[k][0]]
            ev[U[k][3]][(t['category'], t['year'])].append(k)
        for norm in ('vs danger', 'vs field', 'raw'):
            pairs = []
            for p, e in ev.items():
                es = [v for v in e.values() if len(v) >= a.min_boards // 2]
                if len(es) < 2:
                    continue
                sc = []
                for v in es[:2]:
                    if norm == 'vs danger':
                        sc.append(sum(U[k][5] for k in v) / max(sum(U[k][9] for k in v), 1e-9))
                    elif norm == 'vs field':
                        vv = [U[k][5] - field[k][0] for k in v if not np.isnan(field[k][0])]
                        sc.append(sum(vv) / max(len(vv), 1))
                    else:
                        sc.append(sum(U[k][5] for k in v) / len(v))
                pairs.append(sc)
            if len(pairs) > 10:
                x = np.array(pairs)
                print(f'    across events, tricks {norm:9s}: r {np.corrcoef(x[:, 0], x[:, 1])[0, 1]:+.3f} ({len(pairs)} players in two events)')
    # 3. one player
    mine = {u[3] for u in U if u[4] and a.player.lower() in u[4].lower()}
    if mine:
        print(f'\n3. {a.player}: player ids {sorted(mine)}')
        for role in ('declarer', 'defense', 'lead'):
            ks = [k for k, u in enumerate(U) if u[1] == role and u[3] in mine]
            if not ks:
                continue
            v = np.array([[U[k][5], U[k][6], U[k][7], U[k][9]] for k in ks], float)
            fv = [U[k][5] - field[k][0] for k in ks if not np.isnan(field[k][0])]
            events = collections.Counter((tables[U[k][0]]['category'], tables[U[k][0]]['year'], tables[U[k][0]]['stage']) for k in ks)
            # the same events' other players, per player, for the standing
            others = collections.defaultdict(list)
            for k, u in enumerate(U):
                t = tables[u[0]]
                if u[1] == role and u[3] and (t['category'], t['year'], t['stage']) in events:
                    others[u[3]].append(k)
            share = {p: sum(U[k][5] for k in v_) / max(sum(U[k][9] for k in v_), 1e-9) for p, v_ in others.items() if len(v_) >= 10}
            me = v[:, 0].sum() / max(v[:, 3].sum(), 1e-9)
            sd = np.std([s for p, s in share.items() if p not in mine]) if len(share) > 3 else float('nan')
            mean = np.mean([s for p, s in share.items() if p not in mine]) if len(share) > 3 else float('nan')
            print(f'  {role}: {len(ks)} boards in {dict(events)} | tricks {v[:, 0].mean():.3f} a board, plays {v[:, 1].mean():.3f}, imps {v[:, 2].mean():.2f} | '
                  f'vs field {np.mean(fv) if fv else float("nan"):+.3f} | danger share {me:.3f} against the same events\' players {mean:.3f} (SD {sd:.3f}, '
                  f'{len(share)} players with 10+ boards): {(me - mean) / sd if sd == sd and sd > 0 else float("nan"):+.2f} SD (positive = loses more)')
    if a.json:
        Path(a.json).write_text(json.dumps(dict(events=rows_out, reliability=report), indent=1, default=float))


if __name__ == '__main__':
    main()
