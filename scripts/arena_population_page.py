#!/usr/bin/env python3
"""The arena page for a population (G9-D10): static HTML from an arena-population-v1 file.

    python scripts/arena_ladder.py fit --rows ROWS --out arena/ladder.json --population arena/population.json
    python scripts/arena_population_page.py --population arena/population.json --out SITE

Writes SITE/index.html (members by role and strength, the cells matrix as a heat map ordered by strength with pairs
out of line marked, the champion: field score, Nash average, worst cell, exploitability, the panel over time, and
the champion's boards by opponent role) and SITE/members/<id>.html (one page per member: its cells by the opponent's
role). Self-contained: inline CSS and SVG, native tooltips, no scripts. The registered feeds keep no experience, so
"what Gen 9 has learned" about a member is on the arena9 population pages (scripts/arena9_page.py) of runs that do.
"""
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import arena9_page as P  # noqa: E402

ROLES = ['champion', 'candidate', 'control', 'past champion', 'league', 'outside panel', 'self-play', 'other']
ROLE_SLOT = {'champion': 1, 'candidate': 5, 'control': 2, 'past champion': 3, 'league': 4, 'outside panel': 7, 'self-play': 6, 'other': 8}


def sw(role):
    return f'<span class="sw" style="background:var(--series-{ROLE_SLOT.get(role, 6)})"></span>'


def mfile(pid):
    return pid.replace('#', '_') + '.html'


def members_table(doc, link):
    st, lab = doc['strength'], doc['labels']
    rows = sorted(doc['members'], key=lambda m: -st[m['id']]['strength'])
    out = ['<table><tr><th>Member</th><th>Role</th><th class="num">Boards</th><th class="num">Strength (95%)</th>'
           '<th class="num">Field score</th><th class="num">Nash average</th><th>Worst cell</th></tr>']
    for m in rows:
        s = st[m['id']]
        name = P.esc(lab.get(m['id'], m['id']))
        name = f'<a href="{link}{mfile(m["id"])}">{name}</a>' if link is not None else name
        w = m['worst']
        out.append(f'<tr><td>{sw(m["role"])}{name}</td><td>{P.esc(m["role"])}</td><td class="num">{s["boards"]:,}</td>'
                   f'<td class="num">{P.fmt(s["strength"])} ± {1.96 * s["se"]:.2f}</td><td class="num">{P.fmt(m["field_score"])}</td>'
                   f'<td class="num">{P.fmt(m["nash_average"])}</td><td>{P.esc(lab.get(w["opponent"], w["opponent"]))} '
                   f'{P.fmt(w["cell"])} ± {1.96 * w["se"]:.2f}</td></tr>')
    out.append('</table>')
    return ''.join(out)


def heat_map(doc):
    st = doc['strength']
    order = sorted(doc['players'], key=lambda p: -st[p]['strength'])
    cells = {(c['player'], c['opponent']): (c['cell'], c['se']) for c in doc['cells']}
    direct = {tuple(sorted((c['player'], c['opponent']))) for c in doc['cells'] if c['played']}
    flagged = {tuple(sorted(r['pair'].split('~'))) for r in doc['pairs'] if r['out_of_line']}
    return P.matrix_chart(order, cells, flagged, direct)


def bins_axis(bins, W, left, right):
    n = len(bins)
    step = (W - left - right) / max(n - 1, 1)
    return {b: left + step * k for k, b in enumerate(bins)}


def panel_chart(doc):
    """The champion's cumulative native mean against each panel member, with its 95% interval, by time bin."""
    series = doc['champion_against_panel']
    bins = sorted({x['bin'] for s in series.values() for x in s})
    if not bins:
        return '<p class="muted">The champion has no boards against the panel.</p>'
    W, H, left, right, top, bottom = 760, 220, 52, 120, 12, 36
    vals = [x['mean'] + sgn * 1.96 * (x['se'] or 0) for s in series.values() for x in s for sgn in (-1, 1)]
    lo, hi = min(min(vals), 0) - 0.1, max(max(vals), 0) + 0.1
    y = lambda v: top + (hi - v) / (hi - lo) * (H - top - bottom)
    xs = bins_axis(bins, W, left, right)
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Champion against the panel over time">']
    step = 0.5 if hi - lo <= 3 else 1.0
    for t in [k * step for k in range(math.ceil(lo / step), math.floor(hi / step) + 1)]:
        out.append(f'<line x1="{left}" x2="{W - right}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="var(--{"axis" if t == 0 else "grid"})"/>'
                   f'<text x="{left - 6}" y="{y(t) + 4:.1f}" text-anchor="end">{t:+.1f}</text>')
    ends = []
    for b in bins:
        out.append(f'<text x="{xs[b]:.1f}" y="{H - 14}" text-anchor="middle">{b[5:10]} {b[11:16]}</text>')
    for k, (opp, s) in enumerate(sorted(series.items())):
        color = f'var(--series-{[7, 3, 4, 5][k % 4]})'
        band = [(xs[x['bin']], y(x['mean'] + 1.96 * (x['se'] or 0))) for x in s] + \
               [(xs[x['bin']], y(x['mean'] - 1.96 * (x['se'] or 0))) for x in reversed(s)]
        out.append(f'<polygon points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in band)}" fill="{color}" opacity="0.15"/>')
        out.append(f'<polyline points="{" ".join(f"{xs[x["bin"]]:.1f},{y(x["mean"]):.1f}" for x in s)}" fill="none" stroke="{color}" stroke-width="2"/>')
        for x in s:
            out.append(f'<g><title>{P.esc(doc["labels"].get(opp, opp))} to {x["bin"]}: {P.fmt(x["mean"])} ± {1.96 * (x["se"] or 0):.2f} over {x["boards"]:,} boards</title>'
                       f'<circle cx="{xs[x["bin"]]:.1f}" cy="{y(x["mean"]):.1f}" r="4" fill="{color}" stroke="var(--surface-1)" stroke-width="2"/></g>')
        last = s[-1]
        ends.append([y(last['mean']) + 4, xs[last['bin']] + 8, P.esc(doc['labels'].get(opp, opp))])
    ends.sort()
    for k in range(1, len(ends)):                       # end labels at least 13 px apart
        ends[k][0] = max(ends[k][0], ends[k - 1][0] + 13)
    for yy, xx, text in ends:
        out.append(f'<text class="lab" x="{xx:.1f}" y="{yy:.1f}">{text}</text>')
    out.append('</svg>')
    return ''.join(out)


def mix_chart(doc):
    """The champion's native boards in each time bin, stacked by the opponent's role."""
    mix = doc['champion_boards_by_role']
    bins = sorted(mix)
    if not bins:
        return ''
    roles = [r for r in ROLES if any(r in mix[b] for b in bins)]
    W, H, left, right, top, bottom = 760, 220, 52, 12, 12, 36
    total = max(sum(mix[b].values()) for b in bins)
    bw = (W - left - right) / len(bins)
    y = lambda v: top + (1 - v / total) * (H - top - bottom)
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Champion boards by opponent role">']
    for t in (0, total / 2, total):
        out.append(f'<line x1="{left}" x2="{W - right}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="var(--grid)"/>'
                   f'<text x="{left - 6}" y="{y(t) + 4:.1f}" text-anchor="end">{t:,.0f}</text>')
    for k, b in enumerate(bins):
        x0, acc = left + bw * k + 2, 0
        for r in roles:
            n = mix[b].get(r, 0)
            if not n:
                continue
            y1, y0 = y(acc + n), y(acc)
            out.append(f'<g><title>{b}: {n:,} boards against {P.esc(r)}</title><rect x="{x0:.1f}" y="{y1 + 1:.1f}" width="{bw - 4:.1f}" '
                       f'height="{max(y0 - y1 - 2, 0.5):.1f}" fill="var(--series-{ROLE_SLOT[r]})" rx="2"/></g>')
            acc += n
        out.append(f'<text x="{x0 + (bw - 4) / 2:.1f}" y="{H - 14}" text-anchor="middle">{b[5:10]} {b[11:16]}</text>')
    out.append('</svg><p>' + ' '.join(f'{sw(r)}{P.esc(r)}' for r in roles) + '</p>')
    return ''.join(out)


def index_page(doc):
    lab = doc['labels']
    champ = doc['champion']
    cm = next((m for m in doc['members'] if m['id'] == champ), None)
    eq = ', '.join(f'{P.esc(lab.get(p, p))} {w:.2f}' for p, w in sorted(doc['nash'].items(), key=lambda kv: -kv[1])) if doc['nash'] else 'not found'
    B = [f'<h1>The arena as a population</h1><p class="sub">Native boards of every registered feed, fitted {P.esc(doc["computed_utc"])}; '
         f'IMPs a board against {P.esc(lab.get(doc["anchor"], doc["anchor"]))} (fixed at 0). G9-D10 prototype: nothing here decides anything.</p>',
         '<nav><a href="#members">Members</a><a href="#cells">Cells</a><a href="#champion">Champion</a><a href="#mix">Boards by role</a><a href="#notes">Notes</a></nav>',
         '<h2 id="members">Members by role and strength</h2><div class="card">' + members_table(doc, 'members/') + '</div>',
         '<h2 id="cells">Cells: row member minus column member</h2>'
         '<p class="sub">Ordered by strength. A ring marks a pair that has played; ⚑ marks a pair out of line with the rest (Holm-adjusted). '
         f'{sum(1 for r in doc["pairs"] if r["out_of_line"])} of {sum(1 for r in doc["pairs"] if r["testable"])} testable pairs are out of line. '
         'Blue: the row member is stronger; red: weaker; the scale stops at ±2.5.</p>'
         '<div class="card">' + heat_map(doc) + '</div>',
         f'<h2 id="champion">The champion: {P.esc(lab.get(champ, champ))}</h2><div class="card"><table>'
         f'<tr><th>Field score (provisional field)</th><td class="num">{P.fmt(cm["field_score"]) if cm else "—"}</td></tr>'
         f'<tr><th>Nash average</th><td class="num">{P.fmt(cm["nash_average"]) if cm else "—"}</td></tr>'
         f'<tr><th>Worst cell</th><td>{P.esc(lab.get(cm["worst"]["opponent"], cm["worst"]["opponent"])) if cm else "—"} '
         f'{P.fmt(cm["worst"]["cell"]) if cm else ""} ± {1.96 * cm["worst"]["se"]:.2f}</td></tr>'
         f'<tr><th>Equilibrium of the cells</th><td>{eq}</td></tr>'
         '<tr><th>Exploitability report</th><td class="muted">not measured yet (E9-23)</td></tr></table></div>'
         '<h3>Against the outside panel, cumulative</h3><div class="card">' + panel_chart(doc) + '</div>',
         '<h2 id="mix">The champion\'s boards by opponent role</h2><div class="card">' + mix_chart(doc) + '</div>',
         '<h2 id="notes">Notes</h2><ul>' + ''.join(f'<li>{P.esc(n)}</li>' for n in doc['notes']) + '</ul>']
    return P.page('The arena as a population', ''.join(B), list(range(8)))


def member_page(doc, pid):
    lab, st = doc['labels'], doc['strength']
    m = next(x for x in doc['members'] if x['id'] == pid)
    flagged = {tuple(sorted(r['pair'].split('~'))) for r in doc['pairs'] if r['out_of_line']}
    cells = [c for c in doc['cells'] if c['player'] == pid]
    B = [f'<p><a href="../index.html">← The arena as a population</a></p><h1>{sw(m["role"])}{P.esc(lab.get(pid, pid))}</h1>'
         f'<p class="sub">{P.esc(m["role"])} · {st[pid]["boards"]:,} boards · strength {P.fmt(st[pid]["strength"])} ± {1.96 * st[pid]["se"]:.2f} · '
         f'field score {P.fmt(m["field_score"])} · Nash average {P.fmt(m["nash_average"])}</p>',
         '<p class="muted">Declared card: the registered feeds declare bidding systems only (house-gen6 for the house bots, BEN\'s for BEN). '
         'What Gen 9 has learned about a member is kept by the arena9 runs (profiles, honesty, play factor), not by these feeds.</p>']
    for role in ROLES:
        rows = sorted((c for c in cells if doc['roles'].get(c['opponent']) == role), key=lambda c: -c['cell'])
        if not rows:
            continue
        B.append(f'<h2>{sw(role)}Against {P.esc(role)}</h2><div class="card"><table><tr><th>Opponent</th><th class="num">Cell (95%)</th><th>Basis</th></tr>')
        for c in rows:
            key = tuple(sorted((pid, c['opponent'])))
            basis = ('played' if c['played'] else 'the model alone') + (' · <span class="flag">out of line</span>' if key in flagged else '')
            B.append(f'<tr><td><a href="{mfile(c["opponent"])}">{P.esc(lab.get(c["opponent"], c["opponent"]))}</a></td>'
                     f'<td class="num">{P.fmt(c["cell"])} ± {1.96 * c["se"]:.2f}</td><td>{basis}</td></tr>')
        B.append('</table></div>')
    return P.page(lab.get(pid, pid), ''.join(B), list(range(8)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--population', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    doc = json.loads(a.population.read_text())
    if doc.get('schema') != 'arena-population-v1':
        raise SystemExit('not an arena-population-v1 file')
    (a.out / 'members').mkdir(parents=True, exist_ok=True)
    (a.out / 'index.html').write_text(index_page(doc))
    for pid in doc['players']:
        (a.out / 'members' / mfile(pid)).write_text(member_page(doc, pid))
    print(f"{a.out / 'index.html'} and {len(doc['players'])} member pages")


if __name__ == '__main__':
    main()
