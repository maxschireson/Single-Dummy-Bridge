/* Strength ladder for the arena page (Gen 9 task G9-D9).
 *
 * Reads ladder.json (schema arena-ladder-v1, written by scripts/arena_ladder.py) and draws, in <section id="ladder">:
 * every registered bot's strength (IMPs a board against the anchor, with its 95% interval) against the date of its
 * first board on a registered feed, each point labelled with its seconds per card decision, coloured by generation,
 * hollow where the prior carries more than half the information; candidates not yet on a registered feed are dashed
 * diamonds at the right. Hover a point for its numbers; click a point, its label or its table row for the drill-down:
 * features against the parent with their measured impacts, variants merged into the point, prior, timing.
 * Self-contained: no libraries, nothing else on the page is touched. Refetches ladder.json every 10 minutes.
 */
(function () {
  'use strict';
  const root = document.getElementById('ladder');
  if (!root) return;
  // at the top of the page: straight after the title lines, above what the other scripts insert (they insert before or
  // after #cards and after the h1), whichever runs first; their files are not touched
  const toTop = () => { const f = document.getElementById('feed-schedule'); if (f && root.previousElementSibling !== f) f.after(root); };
  toTop();
  const SVGNS = 'http://www.w3.org/2000/svg';
  // categorical slots in fixed order (dark steps of the reference palette, validated against this page's #192333:
  // adjacent CVD dE >= 8.4, normal-vision >= 19.3, all >= 3:1); every point is also direct-labelled and tabled
  const SLOTS = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'];
  const ORDER = ['Gen 1-4', 'Gen 5', 'Gen 6', 'Gen 7', 'Gen 7.1', 'Gen 8', 'BEN', 'Gen 9 candidate'];
  const SURFACE = '#192333', GRID = '#2a394f', AXIS = '#3a4d68', MUTED = '#acbbcf', TEXT = '#e9eff8';
  let data = null, selected = null;

  // ---- small helpers -------------------------------------------------------------------------------
  const el = (tag, attrs, ...kids) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === 'class') e.className = v; else if (k === 'text') e.textContent = v; else if (v !== null && v !== undefined) e.setAttribute(k, v);
    }
    for (const k of kids) if (k !== null && k !== undefined) e.append(k.nodeType ? k : document.createTextNode(String(k)));
    return e;
  };
  const sv = (tag, attrs) => {
    const e = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs || {})) if (v !== null && v !== undefined) e.setAttribute(k, v);
    return e;
  };
  const num = (x, d = 2) => (x === null || x === undefined || !Number.isFinite(+x)) ? '—' : (+x).toFixed(d);
  const signed = (x, d = 2) => (x === null || x === undefined || !Number.isFinite(+x)) ? '—' : ((+x >= 0 ? '+' : '−') + Math.abs(+x).toFixed(d));
  const pm = (m, s, d = 2) => m === null || m === undefined ? '—' : signed(m, d) + (s !== null && s !== undefined ? ' ± ' + num(s, d) : '');
  const int = x => (x === null || x === undefined) ? '—' : Math.round(+x).toLocaleString('en-US');
  const when = s => { if (!s) return '—'; const d = new Date(s.replace(/Z?$/, 'Z')); return isNaN(d) ? String(s) : d.toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'UTC' }).replace(',', ''); };
  const safeUrl = u => (typeof u === 'string' && /^https?:\/\//.test(u)) ? u : null;
  const link = (text, url) => { const u = safeUrl(url); const s = el('span', {}, text + ' '); if (u) s.append(el('a', { href: u, target: '_blank', rel: 'noopener' }, 'source')); return s; };
  const colour = g => SLOTS[Math.max(0, ORDER.indexOf(g)) % SLOTS.length];
  const timeOf = p => p.introduced_utc ? Date.parse(p.introduced_utc.replace(/Z?$/, 'Z')) : null;
  const seconds = p => p.timing && Number.isFinite(p.timing.seconds_per_choice) ? p.timing.seconds_per_choice : null;
  const variantWords = p => {
    if (!String(p.id).includes('#')) return null;
    const v = (p.variants || []).find(q => q.id === p.id) || {};
    const w = (v.differs_in && v.differs_in.length ? v.differs_in : (p.features || []).map(f => f.feature)).join(' and ');
    return w ? 'other ' + w : null;
  };
  const words = (text, p) => { const w = variantWords(p); return w ? String(text).replace(/\(variant [0-9a-f]+\)/, '(' + w + ')') : text; };
  const nm = p => words(p.label || p.id, p);
  const labelOf = p => words(p.point_label || p.label || p.id, p);

  // ---- layout ---------------------------------------------------------------------------------------
  function build() {
    root.replaceChildren();
    toTop();
    root.hidden = false;
    const s = data.sources || {};
    const anchor = (data.points || []).find(p => p.anchor || p.id === data.anchor);
    let chart;
    root.append(
      el('h2', { text: 'Strength ladder' }),
      el('p', { class: 'muted' },
        `${data.unit || 'IMPs a board'} against ${anchor ? anchor.label : data.anchor} (fixed at 0), ${data.condition === 'native' ? 'each side with its own bidder' : data.condition}; ` +
        `fitted ${when(data.computed_utc)} UTC from ${int(s.boards_fitted)} boards on ${int(s.feeds)} registered feeds. ` +
        'x: introduction, the first board on a registered feed unless the bot is known to have played earlier. Labels: seconds per card decision with a choice. Hollow: the prior carries more than half the information. ' +
        'Dashed diamonds: candidates not yet on a registered feed. Click a point, label or row for its features.'),
      legend(), chart = chartBox(), el('div', { id: 'ladder-drill', class: 'ladder-drill' }), table(), notes());
    chart.placeLabels();
    drill(selected);
  }

  function legend() {
    const used = new Set([...(data.points || []), ...(data.candidates || [])].map(p => p.group));
    const box = el('div', { class: 'legend', role: 'list', 'aria-label': 'Generations' });
    for (const g of ORDER.concat([...used].filter(g => !ORDER.includes(g)))) {
      if (!used.has(g)) continue;
      const sw = sv('svg', { width: 12, height: 12, 'aria-hidden': 'true' });
      sw.append(sv('circle', { cx: 6, cy: 6, r: 5, fill: colour(g) }));
      box.append(el('span', { role: 'listitem' }, sw, ' ' + g));
    }
    return box;
  }

  function chartBox() {
    const wrap = el('div', { style: 'position:relative' });
    const W = 1200, H = 470, M = { l: 58, r: 150, t: 14, b: 40 };
    const svg = sv('svg', { viewBox: `0 0 ${W} ${H}`, width: '100%', role: 'img', 'aria-label': 'Strength of each bot against its introduction date', style: 'display:block;min-width:880px' });
    const pts = (data.points || []).filter(p => Number.isFinite(p.strength));
    const cands = (data.candidates || []).filter(p => Number.isFinite(p.strength));
    const times = pts.map(timeOf).filter(Number.isFinite);
    const computed = Date.parse((data.computed_utc || '').replace(/Z?$/, 'Z')) || Math.max(...times);
    const t0 = Math.min(...times) - 6 * 3600e3, t1 = Math.max(computed, Math.max(...times)) + 4 * 3600e3;
    const all = pts.concat(cands);
    let lo = Math.min(...all.map(p => (p.ci95 || [p.strength])[0])), hi = Math.max(...all.map(p => (p.ci95 || [, p.strength])[1] ?? p.strength));
    lo = Math.floor((lo - 0.15) * 2) / 2; hi = Math.ceil((hi + 0.15) * 2) / 2;
    const X = t => M.l + (t - t0) / (t1 - t0) * (W - M.l - M.r);
    const Y = v => M.t + (hi - v) / (hi - lo) * (H - M.t - M.b);
    // grid and axes: recessive
    for (let v = lo; v <= hi + 1e-9; v += 0.5) {
      svg.append(sv('line', { x1: M.l, x2: W - M.r, y1: Y(v), y2: Y(v), stroke: Math.abs(v) < 1e-9 ? AXIS : GRID, 'stroke-width': Math.abs(v) < 1e-9 ? 1.5 : 1 }));
      const t = sv('text', { x: M.l - 8, y: Y(v) + 4, 'text-anchor': 'end' }); t.textContent = signed(v, 1).replace('+0.0', '0').replace('−0.0', '0'); svg.append(t);
    }
    const yl = sv('text', { x: 14, y: M.t + (H - M.t - M.b) / 2, transform: `rotate(-90 14 ${M.t + (H - M.t - M.b) / 2})`, 'text-anchor': 'middle' });
    yl.textContent = (data.unit || 'IMPs a board') + ' against ' + (anchor() || data.anchor); svg.append(yl);
    const day = 86400e3;
    for (let d = Math.ceil(t0 / day) * day; d <= t1; d += day) {
      svg.append(sv('line', { x1: X(d), x2: X(d), y1: M.t, y2: H - M.b, stroke: GRID, 'stroke-dasharray': '2 4' }));
      const t = sv('text', { x: X(d), y: H - M.b + 18, 'text-anchor': 'middle' });
      t.textContent = new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' }); svg.append(t);
    }
    const xl = sv('text', { x: (M.l + W - M.r) / 2, y: H - 6, 'text-anchor': 'middle' }); xl.textContent = 'introduced (UTC)'; svg.append(xl);
    // positions: candidates at the computed time; marks at nearly the same x are dodged sideways
    const marks = pts.map(p => ({ p, x: X(timeOf(p) ?? computed), y: Y(p.strength), cand: false }))
      .concat(cands.map(p => ({ p, x: X(computed), y: Y(p.strength), cand: true })));
    marks.sort((a, b) => a.x - b.x || a.y - b.y);
    for (let i = 0; i < marks.length;) {
      let j = i; while (j + 1 < marks.length && marks[j + 1].x - marks[i].x < 4) j++;
      const n = j - i + 1;
      for (let k = 0; k < n; k++) marks[i + k].x += (k - (n - 1) / 2) * 11;
      i = j + 1;
    }
    // intervals, then marks, then labels (greedy vertical placement without overlaps)
    const gI = sv('g'), gM = sv('g'), gL = sv('g');
    for (const m of marks) {
      const c = colour(m.p.group), ci = m.p.ci95;
      if (ci && Number.isFinite(ci[0]) && Number.isFinite(ci[1]) && ci[1] > ci[0]) { m.lo = Y(ci[0]); m.hi = Y(ci[1]); }
      if (m.lo !== undefined)
        gI.append(sv('line', { x1: m.x, x2: m.x, y1: Y(ci[0]), y2: Y(ci[1]), stroke: c, 'stroke-width': 2, 'stroke-linecap': 'round', opacity: 0.75, 'stroke-dasharray': m.cand ? '4 3' : null }));
      const hollow = !!m.p.hollow, shape = m.cand
        ? sv('path', { d: `M${m.x} ${m.y - 7}L${m.x + 7} ${m.y}L${m.x} ${m.y + 7}L${m.x - 7} ${m.y}Z`, fill: SURFACE, stroke: c, 'stroke-width': 2, 'stroke-dasharray': '3 2' })
        : sv('circle', { cx: m.x, cy: m.y, r: 5.5, fill: hollow ? SURFACE : c, stroke: hollow ? c : SURFACE, 'stroke-width': 2 });
      gM.append(shape);
      const hit = sv('circle', { cx: m.x, cy: m.y, r: 13, fill: 'transparent', tabindex: 0, role: 'button', 'aria-label': describe(m.p), style: 'cursor:pointer;outline:none' });
      hit.addEventListener('mouseenter', ev => tip(ev, m.p, wrap, svg)); hit.addEventListener('mouseleave', () => tip(null));
      hit.addEventListener('focus', ev => { hit.setAttribute('stroke', TEXT); hit.setAttribute('stroke-width', 1.5); tip(ev, m.p, wrap, svg); });
      hit.addEventListener('blur', () => { hit.removeAttribute('stroke'); tip(null); });
      hit.addEventListener('click', () => choose(m.p));
      hit.addEventListener('keydown', ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); choose(m.p); } });
      gM.append(hit);
      m.ring = shape;
    }
    svg.append(gI, gM, gL);
    wrap.append(svg, el('div', { id: 'ladder-tip', role: 'tooltip', hidden: '', style: 'position:absolute;pointer-events:none;background:#0f1622;border:1px solid #405875;border-radius:8px;padding:8px 10px;font-size:12px;line-height:1.45;color:' + TEXT + ';max-width:300px;z-index:5' }));
    // labels need measured widths, so they are placed once the chart is in the page (build calls this);
    // greedy: top to bottom, each label at its point's height or the nearest free row above or below, with a leader line
    wrap.placeLabels = () => {
      const placed = [], LH = 14, top = M.t + 9, bottom = H - M.b - 3;
      const crossesInterval = (x0, w, yy, m) => marks.some(o => o !== m && o.lo !== undefined && o.x > x0 - 3 && o.x < x0 + w + 3 && o.hi < yy + 2 && o.lo > yy - 13);
      const free = (x0, w, yy, m, strict) => yy >= top && yy <= bottom
        && !placed.some(b => !(x0 + w + 3 < b.x || x0 > b.x + b.w + 3 || yy - 12 > b.y || yy < b.y - 12))
        && !marks.some(o => o !== m && o.x > x0 - 7 && o.x < x0 + w + 7 && o.y > yy - 15 && o.y < yy + 4)
        && !(strict && crossesInterval(x0, w, yy, m));
      for (const m of marks.slice().sort((a, b) => a.y - b.y)) {
        const t = sv('text', { x: 0, y: 0, style: 'cursor:pointer;paint-order:stroke;stroke:' + SURFACE + ';stroke-width:3px;stroke-linejoin:round' }); t.textContent = labelOf(m.p); gL.append(t);
        const w = t.getComputedTextLength ? t.getComputedTextLength() : t.textContent.length * 6.8;
        let best = null;
        for (const [strict, rows] of [[true, 4], [false, 16]]) {
          for (const side of (m.x + 10 + w > W - 4 ? [-1] : [1, -1])) {
            const x0 = side > 0 ? m.x + 10 : m.x - 10 - w;
            if (x0 < M.l + 2) continue;
            for (let k = 0; k < rows && !best; k++) for (const s of k ? [1, -1] : [1]) {
              const yy = m.y + 4 + s * k * LH;
              if (!best && free(x0, w, yy, m, strict)) best = { x0, yy, side };
            }
            if (best) break;
          }
          if (best) break;
        }
        if (!best) best = { x0: m.x + 10 + w > W - 4 ? m.x - 10 - w : m.x + 10, yy: m.y + 4, side: m.x + 10 + w > W - 4 ? -1 : 1 };
        placed.push({ x: best.x0, y: best.yy, w });
        t.setAttribute('x', best.x0); t.setAttribute('y', best.yy);
        t.addEventListener('click', () => choose(m.p));
        if (Math.abs(best.yy - 4 - m.y) > 6)
          gL.insertBefore(sv('line', { x1: m.x + best.side * 6, y1: m.y, x2: best.side > 0 ? best.x0 - 2 : best.x0 + w + 2, y2: best.yy - 4, stroke: '#4f6482', 'stroke-width': 1 }), gL.firstChild);
      }
    };
    return wrap;
    function anchor() { const a = (data.points || []).find(p => p.anchor || p.id === data.anchor); return a ? a.label : null; }
  }

  function describe(p) {
    return `${nm(p)}: ${pm(p.strength)} ${data.unit || ''}, 95% ${num(p.ci95 && p.ci95[0])} to ${num(p.ci95 && p.ci95[1])}, ${int(p.boards)} boards` +
      (seconds(p) !== null ? `, ${num(seconds(p))} s per decision` : '') + (p.candidate ? ', candidate' : '');
  }

  function tip(ev, p, wrap, svg) {
    const box = document.getElementById('ladder-tip');
    if (!box) return;
    if (!ev || !p) { box.hidden = true; return; }
    box.replaceChildren(
      el('div', { style: 'font-weight:600' }, nm(p)),
      el('div', {}, `${pm(p.strength)} ${data.unit || ''}`),
      el('div', { style: 'color:' + MUTED }, `95%: ${num(p.ci95 && p.ci95[0])} to ${num(p.ci95 && p.ci95[1])} · ${int(p.boards)} boards`),
      el('div', { style: 'color:' + MUTED }, (p.candidate ? 'candidate, not on a registered feed' : `introduced ${when(p.introduced_utc)} UTC`) +
        (p.prior_share !== null && p.prior_share !== undefined ? ` · prior ${Math.round(100 * p.prior_share)}%` : '')),
      seconds(p) !== null ? el('div', { style: 'color:' + MUTED }, `${num(seconds(p), 3)} s per card decision with a choice`) : null,
      p.candidate ? el('div', { style: 'color:' + MUTED }, (p.estimate && p.estimate.edge) ? 'Click for where its edge comes from.' : 'Click for how it is placed.') : null);
    box.hidden = false;
    const r = wrap.getBoundingClientRect(), t = ev.target.getBoundingClientRect();
    let left = t.left - r.left + 18, top = t.top - r.top - 10;
    if (left + 300 > r.width) left = t.left - r.left - 310;
    box.style.left = Math.max(0, left) + 'px'; box.style.top = Math.max(0, top) + 'px';
  }

  function choose(p) { selected = p.id; drill(p.id); const d = document.getElementById('ladder-drill'); if (d && d.scrollIntoView) d.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }

  // ---- drill-down ---------------------------------------------------------------------------------
  function drill(id) {
    const box = document.getElementById('ladder-drill');
    if (!box) return;
    const p = [...(data.points || []), ...(data.candidates || [])].find(q => q.id === id);
    if (!p) { box.replaceChildren(); box.hidden = true; return; }
    box.hidden = false;
    const c = colour(p.group);
    const sw = sv('svg', { width: 12, height: 12, 'aria-hidden': 'true' }); sw.append(sv('circle', { cx: 6, cy: 6, r: 5, fill: c }));
    const head = el('h3', { style: 'margin:4px 0 6px;font-size:17px' }, sw, ' ' + nm(p));
    const close = el('button', { type: 'button', style: 'float:right;background:#25354b;color:' + TEXT + ';border:1px solid #405875;border-radius:6px;padding:4px 10px;cursor:pointer' }, 'Close');
    close.addEventListener('click', () => { selected = null; drill(null); });
    const facts = [
      ['Strength', `${pm(p.strength)} ${data.unit || ''} (95% ${num(p.ci95 && p.ci95[0])} to ${num(p.ci95 && p.ci95[1])})`],
      ['Group', p.group + (p.parent ? ` · parent ${nameOf(p.parent)}` : '')],
      p.vs_parent ? ['Against its parent', `${pm(p.vs_parent.mean, p.vs_parent.se)} (${nameOf(p.vs_parent.parent)})`] : null,
      ['Boards', int(p.boards)],
      ['Introduced', p.candidate ? 'candidate: not on a registered feed' + (p.introduced_utc ? ` (in the arrival run from ${when(p.introduced_utc)} UTC)` : '')
        : when(p.introduced_utc) + ' UTC' + (p.first_registered_board_utc && p.first_registered_board_utc !== p.introduced_utc ? ` · first board on a registered feed ${when(p.first_registered_board_utc)} UTC` : '')],
      p.introduced_source && typeof p.introduced_source === 'object' ? ['Introduction evidence', link(p.introduced_source.source + (p.introduced_source.note ? ' ' + p.introduced_source.note : ''), p.introduced_source.url)] : null,
      p.prior ? ['Prior', `${p.prior.kind}${p.prior.mean !== null && p.prior.mean !== undefined ? ', mean ' + signed(p.prior.mean) : ''}${p.prior.sd ? ', SD ' + num(p.prior.sd) : ''}${p.prior.source ? ' · ' + p.prior.source : ''}` +
        (p.prior_share !== null && p.prior_share !== undefined ? ` · ${Math.round(100 * p.prior_share)}% of the information` : '')] : null,
      p.timing ? ['Time per decision', `${num(p.timing.seconds_per_choice, 3)} s with a choice (${int(p.timing.decisions_with_choice)} decisions, ${int(p.timing.forced_decisions)} forced)` +
        (p.timing.by_environment ? ' · ' + Object.entries(p.timing.by_environment).map(([k, v]) => `${k} ${num(v, 3)}`).join(', ') : '')] : null,
    ].filter(Boolean);
    const dl = el('table', { style: 'width:auto;margin:6px 0 10px' });
    for (const [k, v] of facts) dl.append(el('tr', {}, el('th', { style: 'text-align:left;padding:4px 14px 4px 0' }, k), el('td', { style: 'text-align:left;white-space:normal;padding:4px 0' }, v)));
    const parts = [close, head];
    const edge = p.estimate && (p.estimate.edge || p.edge);
    if (p.candidate) parts.push(el('p', { class: 'notice', style: 'margin:6px 0 10px;color:' + TEXT },
      el('strong', {}, edge ? 'Where its edge comes from: ' : 'How it is placed: '), edge || (p.estimate && p.estimate.note) || 'not stated in ladder.json.'));
    parts.push(dl);
    if (p.estimate) {
      const e = p.estimate, u = safeUrl(e.url);
      parts.push(el('p', { class: 'muted' }, `Estimate: ${pm(e.mean, e.se)} against ${nameOf(e.vs)} over ${int(e.boards)} boards, placed on ${nameOf(e.placed_on)}. ${e.edge ? (e.note || '') : ''} `,
        u ? el('a', { href: u, target: '_blank', rel: 'noopener' }, e.source || 'source') : (e.source || '')));
    }
    // features
    const feats = p.features || [];
    parts.push(el('h4', { style: 'margin:12px 0 4px' }, 'Features' + (p.parent ? ` against ${nameOf(p.parent)}` : '')));
    if (!feats.length) parts.push(el('p', { class: 'muted' }, p.parent ? 'No configuration difference from its parent is published.' : 'No parent to compare with.'));
    else {
      const t = el('table'), hd = el('tr');
      for (const h of ['Feature', 'Parent', 'This bot', 'Estimated impact', 'Source']) hd.append(el('th', { style: 'text-align:left' }, h));
      t.append(el('thead', {}, hd));
      const tb = el('tbody');
      for (const f of feats) {
        const imps = f.impacts || [];
        const rows = imps.length ? imps : [null];
        rows.forEach((im, k) => {
          const tr = el('tr');
          if (k === 0) {
            tr.append(el('td', { rowspan: rows.length, style: 'text-align:left;white-space:normal' }, f.feature),
              el('td', { rowspan: rows.length, style: 'text-align:left;white-space:normal' }, String(f.parent_value ?? '—')),
              el('td', { rowspan: rows.length, style: 'text-align:left;white-space:normal' }, String(f.value ?? '—')));
          }
          if (!im) tr.append(el('td', { style: 'text-align:left;color:' + MUTED }, 'not measured'), el('td'));
          else {
            const u = safeUrl(im.url);
            const val = im.mean !== null && im.mean !== undefined ? `${pm(im.mean, im.se)} ${data.unit || ''}` : (im.text || 'no signed figure');
            tr.append(el('td', { style: 'text-align:left;white-space:normal' }, val,
              im.compares ? el('span', { class: 'ci' }, im.compares) : null,
              im.also_differs ? el('span', { class: 'ci' }, 'also differs: ' + (Array.isArray(im.also_differs) ? im.also_differs.join(', ') : im.also_differs)) : null),
            el('td', { style: 'text-align:left;white-space:normal' }, u ? el('a', { href: u, target: '_blank', rel: 'noopener' }, im.source || 'source') : (im.source || '')));
          }
          tb.append(tr);
        });
      }
      t.append(tb); parts.push(t);
    }
    // variants merged into the point
    const vars = (p.variants || []).filter(v => v.id !== p.id || (p.variants || []).length > 1);
    if (vars.length > 1 || vars.some(v => v.merged)) {
      parts.push(el('h4', { style: 'margin:12px 0 4px' }, 'Variants in this point'));
      const t = el('table'), hd = el('tr');
      for (const h of ['Variant', 'Boards', 'Share', 'Difference', 'Differs in', 'Rule']) hd.append(el('th', { style: 'text-align:left' }, h));
      t.append(el('thead', {}, hd));
      const tb = el('tbody');
      for (const v of p.variants) {
        tb.append(el('tr', {},
          el('td', { style: 'text-align:left' }, v.id + (v.fingerprint ? ` (${v.fingerprint})` : '')),
          el('td', {}, int(v.boards)), el('td', {}, v.share !== undefined ? Math.round(100 * v.share) + '%' : '—'),
          el('td', {}, v.difference !== undefined ? pm(v.difference, v.se) : 'reference'),
          el('td', { style: 'text-align:left;white-space:normal' }, (v.differs_in || []).join(', ') || '—'),
          el('td', { style: 'text-align:left;white-space:normal' }, v.rule || (v.note || '—'))));
      }
      t.append(tb); parts.push(t);
    }
    if (p.timing && p.timing.source) parts.push(el('p', { class: 'muted' }, 'Time per decision: ' + p.timing.source));
    box.replaceChildren(...parts);
    box.style.cssText = 'margin-top:14px;padding:14px;border:1px solid #2a394f;border-left:3px solid ' + c + ';border-radius:10px;background:#152030';
  }

  function nameOf(id) {
    const p = [...(data.points || []), ...(data.candidates || [])].find(q => q.id === id);
    return p ? nm(p) : (id || '—');
  }

  // ---- table under the chart ----------------------------------------------------------------------
  function table() {
    const rows = (data.points || []).slice().sort((a, b) => b.strength - a.strength).concat(data.candidates || []);
    const t = el('table'), hd = el('tr');
    for (const h of ['Bot', 'Group', 'Introduced (UTC)', 'Boards', 'Strength', '95% interval', 'Prior share', 's per decision']) hd.append(el('th', {}, h));
    t.append(el('thead', {}, hd));
    const tb = el('tbody');
    for (const p of rows) {
      const tr = el('tr', { tabindex: 0, style: 'cursor:pointer' },
        el('td', {}, nm(p) + (p.candidate ? ' (candidate)' : '') + (p.hollow ? ' (mostly prior)' : '')),
        el('td', {}, p.group), el('td', {}, p.candidate ? '—' : when(p.introduced_utc)), el('td', {}, int(p.boards)),
        el('td', { class: p.strength > 0 ? 'pos' : p.strength < 0 ? 'neg' : '' }, signed(p.strength)),
        el('td', {}, p.ci95 ? `${num(p.ci95[0])} to ${num(p.ci95[1])}` : '—'),
        el('td', {}, p.prior_share !== null && p.prior_share !== undefined ? Math.round(100 * p.prior_share) + '%' : '—'),
        el('td', {}, seconds(p) !== null ? num(seconds(p), 2) : '—'));
      tr.addEventListener('click', () => choose(p));
      tr.addEventListener('keydown', ev => { if (ev.key === 'Enter') choose(p); });
      tb.append(tr);
    }
    t.append(tb);
    return el('details', { style: 'margin-top:12px' }, el('summary', { style: 'cursor:pointer;color:' + MUTED }, `Table: ${rows.length} bots, strongest first`), t);
  }

  function notes() {
    const list = el('ul', { class: 'muted', style: 'margin:6px 0 0 18px;padding:0' });
    const a = (data.points || []).find(p => p.anchor || p.id === data.anchor);
    list.append(el('li', { style: 'margin:3px 0' }, `Every strength and interval is relative to ${a ? nm(a) : data.anchor}, fixed at 0, which is why its point has no interval. ` +
      `Its own uncertainty is part of every other bot's interval and shared by all of them, so the difference between two bots is less uncertain ` +
      `than their two intervals together suggest.`));
    for (const n of data.notes || []) list.append(el('li', { style: 'margin:3px 0' }, n));
    const s = data.sources || {};
    list.append(el('li', { style: 'margin:3px 0' }, `Sources: ${int(s.feeds)} feeds (${int(s.failed)} failed), ${int(s.boards_fetched)} boards fetched, ${int(s.boards_fitted)} fitted; collected ${when(s.collected_utc)} UTC; registry ${String(s.registry_sha256 || '').slice(0, 12)}.`));
    return el('details', { style: 'margin-top:8px' }, el('summary', { style: 'cursor:pointer;color:' + MUTED }, 'How this is computed'), list);
  }

  // ---- load and refresh ---------------------------------------------------------------------------
  async function load() {
    try {
      const r = await fetch('ladder.json?v=' + Math.floor(Date.now() / 600000), { cache: 'no-store' });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const d = await r.json();
      if (d.schema !== 'arena-ladder-v1' || !Array.isArray(d.points)) throw new Error('unexpected ladder.json');
      if (!data || d.computed_utc !== data.computed_utc) { data = d; build(); }
    } catch (e) {
      if (!data) root.hidden = true;           // nothing to show: the rest of the page is unaffected
    }
  }
  load();
  setInterval(load, 600000);
})();
