#!/usr/bin/env python3
"""The arena's results page for a population (G9-D8 prototype): static HTML rendered from arena-results-v1 files.

    python scripts/arena9_page.py results --control RUN/control --players configs/players --reader 9a-32 --out DATA
    python scripts/arena9_page.py render --data DATA --out SITE [--title "The arrival run"]

`results` writes the data files (bridge_harness/arena9_results.py; format in docs/gen9/arena-results.md). `render`
writes SITE/index.html (roster, ratings, ratings over epochs, pair matrix, decisions by epoch, schedule, the panel
tracker) and SITE/players/<id>.html (one page per player), each self-contained (inline CSS and SVG, no scripts
beyond native tooltips), and copies the data files to SITE/data/. Experiments are not on this page.
"""
import argparse
import html
import json
import math
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SERIES_LIGHT = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
SERIES_DARK = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767']
NEUTRAL, POS, NEG = (0xf0, 0xef, 0xec), (0x2a, 0x78, 0xd6), (0xe3, 0x49, 0x48)

CSS = """
.viz-root{color-scheme:light;--surface-1:#fcfcfb;--page:#f9f9f7;--text-primary:#0b0b0b;--text-secondary:#52514e;--muted:#898781;
--grid:#e1e0d9;--axis:#c3c2b7;--border:rgba(11,11,11,.10);%(light)s}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])) .viz-root{color-scheme:dark;--surface-1:#1a1a19;--page:#0d0d0d;
--text-primary:#f0efec;--text-secondary:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);%(dark)s}}
body{margin:0;background:var(--page);color:var(--text-primary);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1080px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:22px;margin:0 0 4px} h2{font-size:17px;margin:32px 0 8px} h3{font-size:14px;margin:16px 0 6px}
.sub{color:var(--text-secondary);margin:0 0 16px} .muted{color:var(--muted)}
.card{background:var(--surface-1);border:1px solid var(--border);border-radius:8px;padding:12px 14px;margin:8px 0;overflow-x:auto}
table{border-collapse:collapse;width:100%%;font-variant-numeric:tabular-nums} th,td{text-align:left;padding:4px 8px;border-bottom:1px solid var(--grid);white-space:nowrap}
th{color:var(--text-secondary);font-weight:600} td.num,th.num{text-align:right}
a{color:inherit} .sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.flag{font-weight:700} nav a{margin-right:12px}
svg text{fill:var(--text-secondary);font-size:11px} svg .lab{fill:var(--text-primary)}
"""


def esc(x):
    return html.escape('' if x is None else str(x))


def fmt(x, k=2, sign=True):
    if x is None:
        return '—'
    return f'{x:+.{k}f}' if sign else f'{x:.{k}f}'


def page(title, body, colors):
    light = ''.join(f'--series-{i + 1}:{c};' for i, c in enumerate(SERIES_LIGHT[:len(colors)]))
    dark = ''.join(f'--series-{i + 1}:{c};' for i, c in enumerate(SERIES_DARK[:len(colors)]))
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}</title><style>{CSS % dict(light=light, dark=dark)}</style></head>'
            f'<body class="viz-root"><main>{body}</main></body></html>\n')


def mix(c1, c2, t):
    return '#' + ''.join(f'{round(a + (b - a) * t):02x}' for a, b in zip(c1, c2))


def diverging(v, cap=2.5):
    if v is None:
        return '#' + ''.join(f'{x:02x}' for x in NEUTRAL)
    t = min(abs(v) / cap, 1.)
    return mix(NEUTRAL, POS if v > 0 else NEG, t)


def ink_on(hexcolor):
    r, g, b = (int(hexcolor[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return '#0b0b0b' if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.55 else '#ffffff'


# ---- charts ----------------------------------------------------------------------------------------
def interval_chart(rows, color_of, link=True):
    """Horizontal dot-and-interval chart of ratings, best first."""
    if not rows:
        return ''
    lo = min(r['ci95'][0] for r in rows)
    hi = max(r['ci95'][1] for r in rows)
    lo, hi = math.floor(min(lo, 0) * 2) / 2, math.ceil(hi * 2) / 2
    W, left, right, rowh, top = 640, 110, 24, 26, 18
    H = top + rowh * len(rows) + 24
    x = lambda v: left + (v - lo) / (hi - lo) * (W - left - right)
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Ratings with 95% intervals">']
    t = lo
    while t <= hi + 1e-9:
        out.append(f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{top - 6}" y2="{H - 20}" stroke="var(--grid)" stroke-width="1"/>'
                   f'<text x="{x(t):.1f}" y="{H - 6}" text-anchor="middle">{t:+g}</text>')
        t += 0.5
    for k, r in enumerate(rows):
        y = top + rowh * k + rowh / 2
        c = color_of(r['player'])
        name = esc(r['player'])
        label = f'<a href="players/{name}.html"><text class="lab" x="{left - 8}" y="{y + 4:.1f}" text-anchor="end">{name}</text></a>' if link else \
            f'<text class="lab" x="{left - 8}" y="{y + 4:.1f}" text-anchor="end">{name}</text>'
        out.append(label)
        out.append(f'<g><title>{name}: {fmt(r["strength"])} IMPs a board (95% {fmt(r["ci95"][0])} to {fmt(r["ci95"][1])}), {r["boards"]} boards</title>'
                   f'<line x1="{x(r["ci95"][0]):.1f}" x2="{x(r["ci95"][1]):.1f}" y1="{y:.1f}" y2="{y:.1f}" stroke="{c}" stroke-width="2" stroke-linecap="round"/>'
                   f'<circle cx="{x(r["strength"]):.1f}" cy="{y:.1f}" r="5" fill="{c}" stroke="var(--surface-1)" stroke-width="2"/></g>')
    out.append('</svg>')
    return ''.join(out)


def lines_chart(series, color_of, epochs, ylabel='IMPs a board', band=False):
    """One line per player over epochs, labelled at its right end. series: {player: {epoch: (value, se)}}."""
    vals = [v for s in series.values() for v, se in s.values() if v is not None]
    if not vals:
        return ''
    los = [v - 1.96 * (se or 0) for s in series.values() for v, se in s.values() if v is not None] if band else vals
    his = [v + 1.96 * (se or 0) for s in series.values() for v, se in s.values() if v is not None] if band else vals
    lo, hi = math.floor(min(min(los), 0) * 2) / 2, math.ceil(max(his) * 2) / 2
    if hi - lo < 1:
        hi = lo + 1
    W, H, left, right, top, bottom = 640, 260, 44, 90, 12, 28
    x = lambda e: left + (e - epochs[0]) / max(epochs[-1] - epochs[0], 1) * (W - left - right)
    y = lambda v: top + (hi - v) / (hi - lo) * (H - top - bottom)
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="{esc(ylabel)} by epoch">']
    t = lo
    while t <= hi + 1e-9:
        out.append(f'<line x1="{left}" x2="{W - right}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="var(--grid)"/>'
                   f'<text x="{left - 6}" y="{y(t) + 4:.1f}" text-anchor="end">{t:+g}</text>')
        t += 0.5
    for e in epochs:
        out.append(f'<text x="{x(e):.1f}" y="{H - 8}" text-anchor="middle">epoch {e}</text>')
    ends = []
    for p, s in series.items():
        pts = [(e, s[e][0], s[e][1]) for e in epochs if e in s and s[e][0] is not None]
        if not pts:
            continue
        c = color_of(p)
        if band and len(pts) > 1:
            poly = [(x(e), y(v + 1.96 * (se or 0))) for e, v, se in pts] + [(x(e), y(v - 1.96 * (se or 0))) for e, v, se in reversed(pts)]
            out.append(f'<polygon points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in poly)}" fill="{c}" opacity="0.15"/>')
        if len(pts) > 1:
            out.append(f'<polyline points="{" ".join(f"{x(e):.1f},{y(v):.1f}" for e, v, _ in pts)}" fill="none" stroke="{c}" stroke-width="2" '
                       f'stroke-linejoin="round" stroke-linecap="round"/>')
        for e, v, se in pts:
            out.append(f'<g><title>{esc(p)}, epoch {e}: {fmt(v)}' + (f' ± {1.96 * se:.2f}' if se else '') +
                       f'</title><circle cx="{x(e):.1f}" cy="{y(v):.1f}" r="4" fill="{c}" stroke="var(--surface-1)" stroke-width="2"/></g>')
        ends.append([y(pts[-1][1]), p, x(pts[-1][0])])
    ends.sort()
    for k in range(1, len(ends)):                       # keep end labels at least 12px apart
        ends[k][0] = max(ends[k][0], ends[k - 1][0] + 12)
    for yy, p, xx in ends:
        out.append(f'<text class="lab" x="{xx + 8:.1f}" y="{yy + 4:.1f}">{esc(p)}</text>')
    out.append('</svg>')
    return ''.join(out)


def matrix_chart(players, cells, flagged, direct):
    """Row player minus column player, the cell estimate (IMPs a board); a ring marks a pair that has played,
    a flag marks an out-of-line pair."""
    n = len(players)
    if n < 2:
        return ''
    cw, left, top = 62, 96, 70
    W, H = left + cw * n + 8, top + cw * n * 0.6 + 8
    rh = cw * 0.6
    out = [f'<svg viewBox="0 0 {W} {H:.0f}" width="100%" role="img" aria-label="Pair matrix">']
    for j, q in enumerate(players):
        out.append(f'<text class="lab" x="{left + cw * j + cw / 2:.1f}" y="{top - 8}" text-anchor="middle" '
                   f'transform="rotate(-30 {left + cw * j + cw / 2:.1f} {top - 8})">{esc(q)}</text>')
    for i, p in enumerate(players):
        y0 = top + rh * i
        out.append(f'<text class="lab" x="{left - 8}" y="{y0 + rh / 2 + 4:.1f}" text-anchor="end">{esc(p)}</text>')
        for j, q in enumerate(players):
            x0 = left + cw * j
            if p == q:
                out.append(f'<rect x="{x0 + 1}" y="{y0 + 1:.1f}" width="{cw - 2}" height="{rh - 2:.1f}" rx="3" fill="var(--grid)" opacity="0.5"/>')
                continue
            c = cells.get((p, q))
            v = None if c is None else c[0]
            fill = diverging(v)
            key = tuple(sorted((p, q)))
            ring = f' stroke="var(--text-primary)" stroke-width="1.2"' if key in direct else ''
            tip = f'{esc(p)} against {esc(q)}: {fmt(v)} (± {1.96 * c[1]:.2f})' if c else ''
            tip += '; played' if key in direct else '; not played (the model alone)'
            tip += '; out of line' if key in flagged else ''
            out.append(f'<g><title>{tip}</title><rect x="{x0 + 1}" y="{y0 + 1:.1f}" width="{cw - 2}" height="{rh - 2:.1f}" rx="3" fill="{fill}"{ring}/>'
                       f'<text x="{x0 + cw / 2:.1f}" y="{y0 + rh / 2 + 4:.1f}" text-anchor="middle" style="fill:{ink_on(fill)}">'
                       f'{fmt(v, 1)}{" ⚑" if key in flagged else ""}</text></g>')
    out.append('</svg>')
    return ''.join(out)


# ---- pages -----------------------------------------------------------------------------------------
def load(data):
    index = json.loads((data / 'index.json').read_text())
    docs = {json.loads((data / f).read_text())['epoch']: json.loads((data / f).read_text()) for f in index['files']}
    return index, docs


def render(data, out, title):
    index, docs = load(data)
    epochs = sorted(docs)
    last = docs[epochs[-1]]
    order = [r['player'] for r in last['roster']]
    color = {p: f'var(--series-{k + 1})' for k, p in enumerate(order[:8])}
    color_of = lambda p: color.get(p, 'var(--muted)')
    strength = {r['player']: r for r in last['ratings']['players']}
    out.mkdir(parents=True, exist_ok=True)
    (out / 'players').mkdir(exist_ok=True)
    shutil.copytree(data, out / 'data', dirs_exist_ok=True)
    B = [f'<h1>{esc(title)}</h1><p class="sub">The arena at the close of epoch {last["epoch"]} ({esc(last["closed_utc"] or "")}), condition '
         f'{esc(last["condition"])}. Ratings are IMPs a board against <b>{esc(last["ratings"]["reference"])}</b>. Data: <a href="data/index.json">'
         f'data/</a> ({esc(last["schema"])}). Rules {esc(last["source"]["rules_version"])}; source {esc((last["source"]["source_commit"] or "")[:12])}.</p>',
         '<nav><a href="#roster">Roster</a><a href="#ratings">Ratings</a><a href="#history">Over epochs</a><a href="#pairs">Pairs</a>'
         '<a href="#decisions">Decisions</a><a href="#schedule">Schedule</a><a href="#panel">Panel tracker</a></nav>']
    # roster
    B.append('<h2 id="roster">Who is in the arena</h2><div class="card"><table><tr><th>Player</th><th>Kind</th><th>Status</th><th>Version</th>'
             '<th>Declared card</th><th class="num">Rating</th><th class="num">Boards</th><th>Joined</th><th>Admitted</th><th>Retired</th></tr>')
    for r in last['roster']:
        s = strength.get(r['player'])
        card = ', '.join(f'{k} {v}' for k, v in r['declared'].items()) or '—'
        status = r['status'] + (f' (testing against {r["test"]["champion"]} since epoch {r["test"]["opened_epoch"]})' if r.get('test') else '')
        B.append(f'<tr><td><span class="sw" style="background:{color_of(r["player"])}"></span><a href="players/{esc(r["player"])}.html">{esc(r["player"])}</a></td>'
                 f'<td>{esc(r["kind"])}</td><td>{esc(status)}</td><td class="muted">{esc(r["version"])}</td><td>{esc(card)}</td>'
                 f'<td class="num">{fmt(s["strength"]) if s else "—"}{(" ± " + format(1.96 * s["se"], ".2f")) if s and s["se"] else ""}</td>'
                 f'<td class="num">{s["boards"] if s else 0}</td><td>{"epoch " + str(r["joined_epoch"]) if (r.get("joined_epoch") or 0) > 1 else "start"}</td>'
                 f'<td>{"epoch " + str(r["admitted_epoch"]) if r.get("admitted_epoch") else "—"}</td>'
                 f'<td>{"epoch " + str(r["retired_epoch"]) if r.get("retired_epoch") else "—"}</td></tr>')
    B.append('</table></div>')
    # ratings
    rows = last['ratings']['players']
    B.append('<h2 id="ratings">Ratings</h2><p class="sub">Dot: the rating; bar: its 95% interval. Field score: the mean cell against the '
             'rest of the epoch\'s population, equally weighted (provisional); worst cell: the opponent with the lowest upper bound. '
             'Screen: opponents beaten or lost to with the 95% interval clear of zero.</p>')
    B.append('<div class="card">' + interval_chart(rows, color_of) + '</div>')
    B.append('<div class="card"><table><tr><th>Player</th><th class="num">Rating</th><th class="num">95% interval</th><th class="num">Boards</th>'
             '<th class="num">Field score</th><th>Worst cell</th><th>Screen (won / lost / even)</th></tr>')
    for r in rows:
        f = r.get('field') or {}
        w = f.get('worst') or {}
        B.append(f'<tr><td><a href="players/{esc(r["player"])}.html">{esc(r["player"])}</a></td><td class="num">{fmt(r["strength"])}</td>'
                 f'<td class="num">{fmt(r["ci95"][0])} to {fmt(r["ci95"][1])}</td><td class="num">{r["boards"]}</td>'
                 f'<td class="num">{fmt(f.get("score"))}{(" ± " + format(1.96 * f["se"], ".2f")) if f.get("se") else ""}</td>'
                 f'<td>{esc(w.get("opponent", "—"))} {fmt(w.get("estimate")) if w else ""}</td>'
                 f'<td>{len(r["screen"]["won"])} / {len(r["screen"]["lost"])} / {r["screen"]["even"]}</td></tr>')
    B.append('</table></div>')
    # history
    series = {}
    for e in epochs:
        for r in docs[e]['ratings']['players']:
            series.setdefault(r['player'], {})[e] = (r['strength'], r['se'])
    B.append('<h2 id="history">Ratings over epochs</h2><p class="sub">Each player\'s rating at the close of each epoch, from every board so far.</p>')
    B.append('<div class="card">' + lines_chart({p: series[p] for p in order if p in series}, color_of, epochs) + '</div>')
    B.append('<div class="card"><table><tr><th>Player</th>' + ''.join(f'<th class="num">epoch {e}</th>' for e in epochs) + '</tr>' +
             ''.join(f'<tr><td>{esc(p)}</td>' + ''.join(f'<td class="num">{fmt(series[p][e][0]) if e in series[p] else "—"}</td>' for e in epochs) + '</tr>'
                     for p in order if p in series) + '</table></div>')
    # pairs
    cells = {(c['player'], c['opponent']): (c['cell'], c['se']) for c in last['ratings']['cells']}
    pairs = last['ratings']['pairs']
    direct = {tuple(sorted(p['pair'].split('~'))) for p in pairs}
    flagged = {tuple(sorted(p['pair'].split('~'))) for p in pairs if p['out_of_line']}
    present = [p for p in order if p in strength]
    B.append('<h2 id="pairs">Pairs</h2><p class="sub">Row player against column player: the cell estimate, IMPs a board (blue: the row player is '
             'better; red: worse; gray: even). A ring: the pair has played; ⚑: its result is out of line with the other pairs '
             '(leave-one-out z, Holm-adjusted p &lt; 0.05).</p>')
    B.append('<div class="card">' + matrix_chart(present, cells, flagged, direct) + '</div>')
    B.append('<div class="card"><table><tr><th>Pair</th><th class="num">Boards</th><th class="num">Observed (SE)</th><th class="num">'
             'Predicted by the other pairs</th><th class="num">z</th><th>Out of line</th></tr>' +
             ''.join(f'<tr><td>{esc(p["pair"])}</td><td class="num">{p["boards"]}</td><td class="num">{fmt(p["mean"])} ({fmt(p["se"], 2, False)})</td>'
                     f'<td class="num">{fmt(p["predicted"])}</td><td class="num">{fmt(p["z"])}</td>'
                     f'<td>{"<span class=flag>yes</span>" if p["out_of_line"] else ("not testable" if not p["testable"] else "no")}</td></tr>' for p in pairs) +
             '</table></div>')
    # decisions
    B.append('<h2 id="decisions">Decisions by epoch</h2><div class="card"><table><tr><th>Boundary</th><th>Event</th><th>Player</th><th>Detail</th></tr>')
    for e in epochs:
        for d in docs[e]['decisions']:
            det = d.get('authority') or ''
            if d.get('evidence'):
                det += ' ' + json.dumps(d['evidence'])
            when = 'before epoch 1' if (d.get('epoch') or 0) <= 1 else f'before epoch {d["epoch"]}'
            B.append(f'<tr><td>{esc(when)}</td><td>{esc(d["event"])}</td><td>{esc(d["player"])}</td><td style="white-space:normal">{esc(det)}</td></tr>')
        for t in docs[e]['tests']:
            B.append(f'<tr><td>close of epoch {e}</td><td>test state</td><td>{esc(t["pair"])}</td><td>{t["boards"]} direct boards; K {t["K"]:.2f} '
                     f'(promote at {t["promote_at"]:g}), L {t["L"]:.2f} (stop at {t["futility_at"]:g}); decision {esc(t["decision"] or "none yet")}</td></tr>')
    B.append('</table></div>')
    # schedule
    purposes = sorted({k for e in epochs for k in docs[e]['schedule']['played']})
    B.append('<h2 id="schedule">Schedule</h2><p class="sub">Boards played in each epoch by purpose.</p><div class="card"><table><tr><th>Epoch</th>'
             '<th class="num">Boards</th>' + ''.join(f'<th class="num">{esc(k)}</th>' for k in purposes) + '</tr>' +
             ''.join(f'<tr><td>{e}</td><td class="num">{docs[e]["schedule"]["boards"]}</td>' +
                     ''.join(f'<td class="num">{docs[e]["schedule"]["played"].get(k, {}).get("boards", 0)}</td>' for k in purposes) + '</tr>' for e in epochs) +
             '</table></div>')
    # panel
    anchors = last['panel']['anchors']
    B.append('<h2 id="panel">Panel tracker</h2><p class="sub">Each player against the fixed outside panel (the anchors '
             f'{esc(", ".join(anchors))}), cell estimates by epoch.</p><div class="card"><table><tr><th>Player</th><th>Anchor</th>' +
             ''.join(f'<th class="num">epoch {e}</th>' for e in epochs) + '</tr>')
    for p in order:
        if p in anchors:
            continue
        for a in anchors:
            vals = [docs[e]['panel']['players'].get(p, {}).get(a) for e in epochs]
            if not any(vals):
                continue
            B.append(f'<tr><td>{esc(p)}</td><td>{esc(a)}</td>' + ''.join(f'<td class="num">{fmt(v["cell"]) if v else "—"}</td>' for v in vals) + '</tr>')
    B.append('</table></div><p class="muted">Experiments are not on this page; they have their own files.</p>')
    (out / 'index.html').write_text(page(title, ''.join(B), order[:8]))
    for p in order:
        player_page(out, p, docs, epochs, color_of, title, order)


def player_page(out, p, docs, epochs, color_of, title, order):
    last = docs[epochs[-1]]
    r = next(x for x in last['roster'] if x['player'] == p)
    s = next((x for x in last['ratings']['players'] if x['player'] == p), None)
    B = [f'<p><a href="../index.html">← {esc(title)}</a></p><h1><span class="sw" style="background:{color_of(p)}"></span>{esc(p)}</h1>',
         f'<p class="sub">{esc(r["kind"])}, {esc(r["status"])}; version {esc(r["version"])}; declared: '
         f'{esc(", ".join(f"{k} {v}" for k, v in r["declared"].items()) or "nothing")}. '
         + (f'Rating {fmt(s["strength"])} ± {1.96 * s["se"]:.2f} IMPs a board over {s["boards"]} boards.' if s else 'Not rated yet.') + '</p>']
    series = {p: {e: (x['strength'], x['se']) for e in epochs for x in docs[e]['ratings']['players'] if x['player'] == p}}
    B.append('<h2>Rating over epochs</h2><div class="card">' + lines_chart(series, color_of, epochs, band=True) + '</div>')
    cells = sorted(((c['opponent'], c['cell'], c['se']) for c in last['ratings']['cells'] if c['player'] == p), key=lambda t: -(t[1] or 0))
    B.append('<h2>Against each opponent (close of the last epoch)</h2><div class="card"><table><tr><th>Opponent</th><th class="num">Cell</th>'
             '<th class="num">95%</th><th class="num">Boards played</th><th class="num">Observed</th></tr>')
    played = {}
    for q in last['ratings']['pairs']:
        a, b = q['pair'].split('~')
        if p in (a, b):
            sign = 1 if a == p else -1
            played[b if a == p else a] = (q['boards'], None if q['mean'] is None else sign * q['mean'])
    for opp, c, se in cells:
        n, obs = played.get(opp, (0, None))
        B.append(f'<tr><td>{esc(opp)}</td><td class="num">{fmt(c)}</td><td class="num">± {1.96 * se:.2f}</td><td class="num">{n}</td>'
                 f'<td class="num">{fmt(obs)}</td></tr>')
    B.append('</table></div>')
    learned = [(e, docs[e]['learned'].get(p)) for e in epochs if docs[e]['learned'].get(p)]
    if learned:
        B.append('<h2>What the Gen 9 bot has learned about it</h2><p class="sub">What a Gen 9 bot is handed for the next epoch: profile '
                 'probabilities as read, signal honesty (pooled over situations), play factor. Boards: distinct boards in the snapshot; '
                 'deltas: one per board-side and kind of statistic.</p><div class="card"><table><tr><th>After epoch</th><th class="num">Boards</th><th class="num">Deltas</th>'
                 '<th>Profiles as read</th><th class="num">Honesty</th><th class="num">Play factor</th></tr>')
        for e, l in learned:
            prof = ', '.join(f'{k} {v:.2f}' for k, v in sorted(l['profiles_read'] or [], key=lambda kv: -kv[1]) if v >= 0.02)
            h = l.get('honesty_read')
            hv = (h.get('*') if isinstance(h, dict) else h)
            B.append(f'<tr><td>{e}</td><td class="num">{l.get("deals") or 0}</td><td class="num">{l["boards"]}</td><td style="white-space:normal">{esc(prof)}</td>'
                     f'<td class="num">{fmt(hv, 3, False) if hv is not None else "prior"}</td><td class="num">{fmt(l.get("play_factor"), 2, False)}</td></tr>')
        B.append('</table></div>')
    decided = [(e, d) for e in epochs for d in docs[e]['decisions'] if d['player'] == p]
    if decided:
        B.append('<h2>Decisions</h2><div class="card"><table><tr><th>Boundary</th><th>Event</th><th>Detail</th></tr>' +
                 ''.join(f'<tr><td>before epoch {max(d.get("epoch") or 1, 1)}</td><td>{esc(d["event"])}</td><td style="white-space:normal">{esc(d.get("authority") or "")}'
                         f'{(" " + esc(json.dumps(d["evidence"]))) if d.get("evidence") else ""}</td></tr>' for e, d in decided) + '</table></div>')
    anchors = last['panel']['anchors']
    if p not in anchors:
        panel = {a: {e: ((docs[e]['panel']['players'].get(p) or {}).get(a) or {}) for e in epochs} for a in anchors}
        ser = {a: {e: (v.get('cell'), v.get('se')) for e, v in panel[a].items() if v} for a in anchors}
        B.append('<h2>Against the fixed outside panel</h2><div class="card">' + lines_chart(ser, lambda a: 'var(--series-%d)' % (order.index(a) + 1) if a in order[:8]
                                                                                             else 'var(--muted)', epochs, band=True) + '</div>')
    (out / 'players' / f'{p}.html').write_text(page(f'{p} — {title}', ''.join(B), order[:8]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('results')
    p.add_argument('--control', type=Path, required=True); p.add_argument('--players', type=Path, required=True)
    p.add_argument('--reader', default='9a-32', help='the package whose Gen 9 settings read what was learned'); p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('render')
    p.add_argument('--data', type=Path, required=True); p.add_argument('--out', type=Path, required=True); p.add_argument('--title', default='The arena')
    a = ap.parse_args()
    if a.cmd == 'results':
        from bridge_harness import arena9 as a9
        from bridge_harness.arena9_results import write_results
        pk = a9.load_packages(a.players)
        print(json.dumps(write_results(a.control, pk, a.out, reader_spec=(pk.get(a.reader) or {}).get('bundle', {}).get('overrides'))))
    else:
        render(a.data, a.out, a.title)
        print(f'wrote {a.out / "index.html"} and {len(list((a.out / "players").glob("*.html")))} player pages')


if __name__ == '__main__':
    main()
