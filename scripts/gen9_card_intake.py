"""Card intake, step 1 (G9-B8): a reading bundle for a convention card.

Turns a card as a PDF or as photos of its pages into what a reader (an intake agent or a person) needs
to fill the card IR by docs/gen9/card-intake.md: the page images, the text with positions (the PDF's text
layer, or OCR for photos), suit symbols decoded where the text layer keeps them, the tick boxes of a
flattened ACBL-style PDF with their state and label, the card's layout guessed and its text grouped under
the layout's section headings, a checklist of IR fields per section, candidate style statements, and an
IR template. The tool does not fill the IR: reading the card is the reader's job, against the images.

    python scripts/gen9_card_intake.py card.pdf --out intake/card-a [--notes notes.md] [--id card-a]
    python scripts/gen9_card_intake.py p1.png p2.png --out intake/card-a-photo [--reference card.pdf]

Needs PyMuPDF for PDFs and the tesseract command for photos.
"""
import argparse
from collections import Counter
import datetime as dt
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bridge_harness.cards.card import DEFAULTS, SCHEMA     # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TOOL = 'scripts/gen9_card_intake.py v0 (G9-B8)'
# Symbol-font suit glyphs: the private-use codes Word's Symbol font leaves in a text layer, and the font's
# own single-byte codes when a PDF keeps those
SUIT_CODES = {'': '♣', '': '♦', '': '♥', '': '♠', '\xa7': '♣', '\xa8': '♦', '\xa9': '♥', '\xaa': '♠'}
STYLE_WORDS = re.compile(r'\b(vul\w*|NV|non-?vul|fav\w*|unfav\w*|1st|2nd|3rd|4th|seats?|light|sound|aggressive|joke|'
                         r'playing tricks|wide range|rule of (?:20|15)|balancing|re-?opening|max\w*|min\w*|good|bad|flaws?)\b', re.I)

# Section headings of the two layouts the samples use, each with the IR fields it feeds. Field names are
# _fields.json keys (bidding) or carding.<field> (configs/systems/_carding_fields.json).
LAYOUTS = {
    'acbl': {
        'signature': ('GENERAL APPROACH', 'NOTRUMP OPENING BIDS', 'SPECIAL DOUBLES', 'DEFENSIVE CARDING'),
        'sections': {
            'GENERAL APPROACH': ['resp.two_over_one', 'open.min_hcp', 'open.third_seat_min', 'open.strong_2c', 'style'],
            'NOTRUMP OPENING BIDS': ['open.nt (by seat and vulnerability)', 'open.nt_five_major', 'open.nt_six_minor', 'resp.nt',
                                     'resp.nt.puppet_stayman', 'resp.nt.smolen', 'resp.nt.three_level', 'resp.nt.system_on_over_x',
                                     'comp.lebensohl', 'open.two_nt', 'open.three_nt'],
            'MAJOR OPENING': ['open.major_len (1st/2nd and 3rd/4th)', 'resp.one_nt_to_major', 'resp.single_raise', 'resp.limit_raise',
                              'resp.major_jump_raise', 'resp.major_2nt', 'resp.jacoby_min', 'resp.splinters', 'resp.major.drury',
                              'resp.major.bergen', 'resp.major.3nt_raise'],
            'MINOR OPENING': ['open.minor', 'resp.inverted_minors', 'resp.minor_2nt', 'resp.minor_3nt', 'resp.minor.criss_cross',
                              'resp.minor.walsh'],
            'DESCRIBE': ['open.strong_2c', 'resp.strong_2c', 'open.two', 'resp.weak_two_2nt', 'open.weak_quality'],
            'OTHER CONV. CALLS': ['rebid.new_minor_forcing', 'rebid.fourth_suit_forcing', 'resp.minor.weak_jump_shifts'],
            'SPECIAL DOUBLES': ['comp.negative_double_thru', 'comp.responsive_double_thru', 'comp.maximal_double',
                                'comp.support_double_thru', 'comp.snapback'],
            'SIMPLE OVERCALL': ['comp.overcall_1', 'comp.overcall_2', 'comp.overcall_len'],
            'JUMP OVERCALL': ['comp.jump_overcall'],
            'OPENING PREEMPTS': ['open.three_level', 'open.four_level', 'open.weak_quality', 'open.weak_top3', 'variants'],
            'DIRECT CUEBID': ['comp.michaels', 'comp.michaels_major_min'],
            'NOTRUMP OVERCALLS': ['comp.nt_overcall', 'comp.balancing_nt', 'comp.balancing_nt_major', 'comp.unusual_2nt'],
            'DEFENSE VS NOTRUMP': ['comp.vs_nt', 'comp.vs_nt_double'],
            "OVER OPP'S T/O DOUBLE": [],
            'VS Opening Preempts': ['comp.vs_preempts'],
            'SLAM CONVENTIONS': ['slam', 'slam.vs_interference', 'slam.exclusion', 'slam.kickback', 'slam.cuebid_style'],
            'LEADS': ['carding.length_lead_vs_suit', 'carding.length_lead_vs_nt', 'carding.lead_from_ak',
                      'carding.honor_sequence_lead', 'carding.three_small_lead_vs_suit', 'carding.three_small_lead_vs_nt',
                      'carding.four_small_lead'],
            'DEFENSIVE CARDING': ['carding.attitude', 'carding.count', 'carding.signal_on_partner_lead', 'carding.signal_on_declarer_lead'],
            'FIRST DISCARD': ['carding.first_discard'],
            'OTHER CARDING': ['carding.smith_echo', 'carding.trump_signal'],
        },
    },
    'wbf': {
        'signature': ('W B F CONVENTION CARD', 'DEFENSIVE AND COMPETITIVE BIDDING', 'SYSTEM SUMMARY'),
        'sections': {
            'OVERCALLS': ['comp.overcall_1', 'comp.overcall_2', 'comp.overcall_len', 'style'],
            '1NT OVERCALL': ['comp.nt_overcall', 'comp.balancing_nt', 'comp.balancing_nt_major'],
            'JUMP OVERCALLS': ['comp.jump_overcall', 'comp.unusual_2nt'],
            'DIRECT & JUMP CUE BIDS': ['comp.michaels', 'comp.michaels_major_min'],
            'VS. NT': ['comp.vs_nt', 'comp.vs_nt_double'],
            'VS.PREEMPTS': ['comp.vs_preempts'],
            'VS. ARTIFICIAL STRONG OPENINGS': ['comp.vs_strong_club'],
            "OVER OPPONENTS' TAKEOUT DOUBLE": [],
            'OPENING LEADS STYLE': ['carding.length_lead_vs_suit', 'carding.length_lead_vs_nt'],
            'LEADS': ['carding.lead_from_ak', 'carding.honor_sequence_lead', 'carding.three_small_lead_vs_suit',
                      'carding.three_small_lead_vs_nt', 'carding.four_small_lead'],
            'SIGNALS IN ORDER OF PRIORITY': ['carding.attitude', 'carding.count', 'carding.signal_on_partner_lead',
                                             'carding.signal_on_declarer_lead', 'carding.first_discard', 'carding.trump_signal'],
            'TAKEOUT DOUBLES': ['comp.takeout_double_min', 'comp.takeout_shape'],
            'SPECIAL, ARTIFICIAL & COMPETITIVE DBLS/RDLS': ['comp.responsive_double_thru', 'comp.support_double_thru'],
            'SYSTEM SUMMARY': ['open.major_len', 'resp.two_over_one', 'open.nt', 'style'],
            'SPECIAL BIDS THAT MAY REQUIRE DEFENSE': ['resp.minor.weak_jump_shifts', 'comp.vs_two_suiters'],
            'SPECIAL FORCING PASS SEQUENCES': ['general.forcing_pass'],
            'IMPORTANT NOTES': ['general.psychs'],
            'OPENING': ['open.* by opening (rows 1C to 5S: min. cards, description)', 'resp.* (responses column)',
                        'comp.negative_double_thru (NEG.DBL THRU column)', 'variants (seat and vulnerability in the descriptions)'],
            'HIGH LEVEL BIDDING': ['slam', 'slam.exclusion', 'slam.vs_interference', 'slam.cuebid_style'],
        },
    },
}


def decode(text):
    return ''.join(SUIT_CODES.get(ch, ch) for ch in text)


def norm(s):
    """Upper case without spaces: some text layers drop the spaces in headings."""
    return re.sub(r'\s+', '', s).upper()


# ---------------------------------------------------------------------------------------------- sources
def pdf_pages(path, out, dpi):
    import pymupdf
    doc = pymupdf.open(str(path))
    pages = []
    for i, page in enumerate(doc):
        img = out / 'pages' / f'{path.stem}-p{i + 1}.png'
        page.get_pixmap(dpi=dpi).save(str(img))
        lines, symbols = [], 0
        spans = [(s['bbox'], s['font']) for b in page.get_text('dict')['blocks'] for ln in b.get('lines', [])
                 for s in ln['spans'] if s['text'].strip()]

        def font_at(w):
            x, y = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
            return next((f for bb, f in spans if bb[0] - .5 <= x <= bb[2] + .5 and bb[1] - .5 <= y <= bb[3] + .5), '?')

        groups = {}
        for w in page.get_text('words'):                   # words keep the gaps that a span's text drops
            groups.setdefault((w[5], w[6]), []).append(w)
        for ws in groups.values():
            ws.sort(key=lambda w: w[7])
            raw = ' '.join(w[4] for w in ws)
            symbols += sum(ch in SUIT_CODES or ch in '♣♦♥♠' for ch in raw)
            fonts = {font_at(w) for w in ws}
            bbox = [min(w[0] for w in ws), min(w[1] for w in ws), max(w[2] for w in ws), max(w[3] for w in ws)]
            lines.append({'text': decode(raw).strip(), 'bbox': [round(v, 1) for v in bbox],
                          'bold': all('Bold' in f for f in fonts), 'fonts': sorted(fonts)})
        pages.append({'source': str(path), 'page': i + 1, 'image': str(img.relative_to(out)), 'size': [page.rect.width, page.rect.height],
                      'text_from': 'pdf text layer', 'lines': merge_lines(lines), 'boxes': boxes_of(page),
                      'suit_symbols': symbols})
    return pages


def merge_lines(lines):
    """Join text-layer lines that sit on one baseline and touch (a heading split over spans)."""
    out = []
    for ln in sorted(lines, key=lambda r: (round(r['bbox'][1]), r['bbox'][0])):
        if out and abs(out[-1]['bbox'][1] - ln['bbox'][1]) < 1.5 and 0 <= ln['bbox'][0] - out[-1]['bbox'][2] < 4 and out[-1]['bold'] == ln['bold']:
            prev = out[-1]
            prev['text'] = (prev['text'] + ' ' + ln['text']).strip()
            prev['bbox'] = [prev['bbox'][0], min(prev['bbox'][1], ln['bbox'][1]), ln['bbox'][2], max(prev['bbox'][3], ln['bbox'][3])]
            continue
        out.append(dict(ln))
    return out


def boxes_of(page):
    """Tick boxes drawn as small squares: stroked outline, filled when ticked. Label: the words just left of the
    box on its line, and the nearest words above it (a column header) when the box sits in a grid."""
    words = page.get_text('words')
    strokes, fills = [], []
    for d in page.get_drawings():
        r = d['rect']
        if 3.5 <= r.width <= 9.5 and 3.5 <= r.height <= 9.5 and abs(r.width - r.height) < 1.5:
            (fills if d.get('fill') is not None and d.get('type') in ('f', 'fs') else strokes).append((r, d))
    out = []
    for r, d in strokes:
        ticked = any(abs(f.x0 - r.x0) < 2 and abs(f.y0 - r.y0) < 2 for f, _ in fills)
        col = d.get('color') or (0, 0, 0)
        colour = 'red (alert)' if col[0] > .8 and col[1] < .3 else 'blue (announce)' if col[2] > .8 and col[0] < .2 else 'black'
        cy = (r.y0 + r.y1) / 2
        left = sorted((w for w in words if abs((w[1] + w[3]) / 2 - cy) < 4.5 and -1 <= r.x0 - w[2] < 60), key=lambda w: w[2])
        label = decode(left[-1][4]) if left else ''
        context = ' '.join(decode(w[4]) for w in left[-3:-1])
        above = [w for w in words if w[3] <= r.y0 + 1 and r.y0 - w[3] < 40 and w[0] - 6 <= (r.x0 + r.x1) / 2 <= w[2] + 6]
        header = decode(max(above, key=lambda w: w[3])[4]) if above else ''
        out.append({'bbox': [round(v, 1) for v in (r.x0, r.y0, r.x1, r.y1)], 'ticked': ticked, 'colour': colour,
                    'label': label, 'context': context, 'header': header})
    out.sort(key=lambda b: (b['bbox'][0] // 150, b['bbox'][1], b['bbox'][0]))
    return out


def ocr_page(path, out):
    img = out / 'pages' / path.name
    if img.resolve() != path.resolve():
        shutil.copyfile(path, img)
    tsv = subprocess.run(['tesseract', str(path), 'stdout', '--psm', '11', 'tsv'], capture_output=True, text=True, check=True).stdout
    rows = [r.split('\t') for r in tsv.splitlines()[1:]]
    words = [(int(r[6]), int(r[7]), int(r[6]) + int(r[8]), int(r[7]) + int(r[9]), r[11], float(r[10]))
             for r in rows if len(r) >= 12 and r[11].strip() and float(r[10]) >= 0]
    # words into lines: same block/paragraph/line numbers in tesseract's own grouping
    groups = {}
    for r in rows:
        if len(r) >= 12 and r[11].strip() and float(r[10]) >= 0:
            groups.setdefault((r[2], r[3], r[4]), []).append(r)
    lines = []
    for g in groups.values():
        x0 = min(int(r[6]) for r in g)
        y0 = min(int(r[7]) for r in g)
        x1 = max(int(r[6]) + int(r[8]) for r in g)
        y1 = max(int(r[7]) + int(r[9]) for r in g)
        lines.append({'text': ' '.join(r[11] for r in g), 'bbox': [x0, y0, x1, y1], 'bold': False, 'fonts': ['ocr'],
                      'conf': round(sum(float(r[10]) for r in g) / len(g), 1)})
    lines.sort(key=lambda r: (r['bbox'][1] // 8, r['bbox'][0]))
    from PIL import Image
    w, h = Image.open(path).size
    conf = [x[5] for x in words]
    return {'source': str(path), 'page': None, 'image': str(img.relative_to(out)), 'size': [w, h], 'text_from': 'ocr (tesseract, psm 11)',
            'lines': lines, 'boxes': None, 'words': len(words), 'mean_conf': round(sum(conf) / max(len(conf), 1), 1),
            'suit_symbols': 0}


# ---------------------------------------------------------------------------------------------- layout
def guess_layout(pages):
    text = norm(' '.join(ln['text'] for p in pages for ln in p['lines']))
    scores = {k: sum(norm(sig) in text for sig in v['signature']) for k, v in LAYOUTS.items()}
    best = max(scores, key=scores.get)
    return (best if scores[best] else None), scores


def sections(page, layout):
    """Each line under the nearest section heading above it that overlaps it horizontally (a guess: the reader
    checks against the image)."""
    if layout is None:
        return {'(no layout)': [ln['text'] for ln in page['lines']]}
    names = list(LAYOUTS[layout]['sections'])
    heads = []
    for ln in page['lines']:
        t = norm(ln['text'])
        for n in names:
            if t.startswith(norm(n)) and (ln['bold'] or page['text_from'].startswith('ocr') or t == norm(n)):
                heads.append((n, ln['bbox']))
                break
    grouped = {}
    margin = page['size'][0] * 0.07
    for ln in page['lines']:
        x0, y0, x1, _ = ln['bbox']
        cx, best = (x0 + x1) / 2, None
        for n, hb in heads:
            gap = max(hb[0] - cx, cx - hb[2], 0)          # horizontal distance from the heading's extent
            if hb[1] <= y0 + 0.5 and gap <= margin:
                score = (y0 - hb[3]) + 4 * gap              # nearest above, preferring the heading's own column
                if best is None or score < best[0]:
                    best = (score, n)
        grouped.setdefault(best[1] if best else '(before any heading)', []).append(ln['text'])
    return grouped


def style_candidates(texts, source):
    out = []
    for t in texts:
        for s in re.split(r'(?<=[.!])(?<![Vv]s\.)\s+(?=[A-Z0-9“"])', t):     # not after 'vs.'
            s = s.strip(' -•\t')
            if len(s) > 6 and STYLE_WORDS.search(s):
                out.append({'text': s, 'source': source, 'placed': None})
    return out


def template(card_id, name, sources, fmt, styles):
    return {
        'schema': SCHEMA, 'id': card_id, 'name': name, 'family': 'natural',
        'descriptor': {}, 'cover': list(DEFAULTS['cover']), 'carding': {},
        'variants': [], 'recorded': {}, 'style': styles,
        'provenance': {'source': sources, 'format': fmt, 'reader': None, 'date': None, 'tool': TOOL,
                       'confidence': {'high': [], 'medium': [], 'low': []}, 'defaulted': [], 'not_placed': []},
    }


def recall(pages, reference):
    """Share of the reference PDF's words (3+ letters) that the OCR text holds: the photo path against the text layer."""
    import pymupdf
    ref = Counter(w[4].lower() for p in pymupdf.open(str(reference)) for w in p.get_text('words') if len(re.sub(r'\W', '', w[4])) >= 3)
    got = Counter(w.lower() for p in pages for ln in p['lines'] for w in ln['text'].split())
    hit = sum(min(n, got[w]) for w, n in ref.items())
    return round(hit / max(sum(ref.values()), 1), 3), sum(ref.values())


# ---------------------------------------------------------------------------------------------- bundle
def fields_info():
    f = json.loads((ROOT / 'configs/cards/_fields.json').read_text())['fields']
    c = json.loads((ROOT / 'configs/systems/_carding_fields.json').read_text())['fields']
    return f, c


def checklist_line(field, f, c):
    key = field.split(' ')[0]
    if key.startswith('carding.'):
        vals = c.get(key[8:])
        return f'- [ ] `{field}`' + (f': one of {", ".join(vals)}' if vals else '')
    if key in ('style', 'variants'):
        return f'- [ ] {field}: statements of seat, vulnerability or strength (style list; variants where a field holds them)'
    spec = f.get(key) or {}
    how = {'meanings': 'compiled', 'no': 'recorded only'}.get(spec.get('executable'), 'not in _fields.json: check card.py DEFAULTS')
    default = json.dumps(spec['default']) if 'default' in spec else None
    return f'- [ ] `{field}` ({how}' + (f'; default {default}' if default not in (None, 'null') else '') + ')'


def write_bundle(out, pages, layout, scores, styles, tmpl, rec):
    f, c = fields_info()
    md = [f'# Card intake bundle: {tmpl["name"] or tmpl["id"]}', '',
          f'Made by `{TOOL}` on {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC. Procedure: docs/gen9/card-intake.md.',
          f'Layout guessed: **{layout or "unknown"}** (signature headings found: {scores}).', '',
          'Read every field against the page images; the text below is an aid. Suit symbols: '
          + ('taken from the text layer (symbol-font codes decoded) where it kept them; check each against the image.'
             if any(p['suit_symbols'] for p in pages) else 'none decoded; read every symbol-bearing field from the image.'), '']
    if rec:
        md += [f'OCR against the PDF text layer: {rec[0]:.1%} of the reference\'s {rec[1]} words of 3+ letters are in the OCR text.', '']
    md += ['## Pages', ''] + [f'- `{p["image"]}` from `{p["source"]}`' + (f' page {p["page"]}' if p['page'] else '')
                              + f': {len(p["lines"])} lines, {p["text_from"]}'
                              + (f', mean word confidence {p["mean_conf"]}' if p.get('mean_conf') is not None else '') for p in pages]
    for p in pages:
        title = f'{Path(p["source"]).name}' + (f' p{p["page"]}' if p['page'] else '')
        md += ['', f'## {title}', '']
        for name, lines in sections(p, layout).items():
            md += [f'### {name}', '']
            fields = LAYOUTS[layout]['sections'].get(name, []) if layout else []
            if fields:
                md += ['Fields this section feeds:', ''] + [checklist_line(x, f, c) for x in fields] + ['']
            md += ['```'] + lines + ['```', '']
        if p['boxes']:
            md += ['### Tick boxes', '', 'A box follows its label on ACBL-style cards: the label is the word just left of the box.', '',
                   '| Ticked | Colour | Label | Words before it | Header above | Box |', '| --- | --- | --- | --- | --- | --- |']
            md += [f'| {"■" if b["ticked"] else "☐"} | {b["colour"]} | {b["label"]} | {b["context"]} | {b["header"]} | {b["bbox"]} |'
                   for b in p['boxes']]
            md.append('')
    md += ['## Style statements found', '', 'Each becomes a field, a variant (by seat and vulnerability), "the defaults hold", or a `not_placed` line with the reason.', '']
    md += [f'- ({s["source"]}) {s["text"]}' for s in styles] or ['- none found']
    (out / 'bundle.md').write_text('\n'.join(md) + '\n')
    (out / 'template.json').write_text(json.dumps(tmpl, indent=1, ensure_ascii=False) + '\n')
    (out / 'text.json').write_text(json.dumps(pages, indent=1, ensure_ascii=False) + '\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('sources', nargs='+', help='a PDF, or image files of the pages in order')
    ap.add_argument('--out', required=True)
    ap.add_argument('--notes', default=None, help="the partnership's notes (text or markdown) to scan for style statements")
    ap.add_argument('--id', default=None)
    ap.add_argument('--name', default=None)
    ap.add_argument('--dpi', type=int, default=150)
    ap.add_argument('--reference', default=None, help='a PDF of the same card, to measure OCR recall on photos')
    a = ap.parse_args()
    out = Path(a.out)
    (out / 'pages').mkdir(parents=True, exist_ok=True)
    pages = []
    for s in map(Path, a.sources):
        pages += pdf_pages(s, out, a.dpi) if s.suffix.lower() == '.pdf' else [ocr_page(s, out)]
    layout, scores = guess_layout(pages)
    texts = [ln['text'] for p in pages for ln in p['lines']]
    styles = style_candidates(texts, 'card')
    if a.notes:
        styles += style_candidates([ln for ln in Path(a.notes).read_text().splitlines() if ln.strip().startswith('-')], 'notes')
    fmt = ('pdf' if all(Path(s).suffix.lower() == '.pdf' for s in a.sources) else 'photos') + f', {layout or "unknown"} layout'
    card_id = a.id or Path(a.sources[0]).stem
    tmpl = template(card_id, a.name, [str(s) for s in a.sources], fmt, styles)
    rec = recall(pages, a.reference) if a.reference else None
    write_bundle(out, pages, layout, scores, styles, tmpl, rec)
    print(f'{out}/bundle.md: {len(pages)} pages, layout {layout}, {sum(len(p["lines"]) for p in pages)} lines, '
          f'{sum(len(p["boxes"] or []) for p in pages)} tick boxes, {len(styles)} style candidates'
          + (f', OCR recall {rec[0]:.1%} of {rec[1]} words' if rec else ''))


if __name__ == '__main__':
    main()
