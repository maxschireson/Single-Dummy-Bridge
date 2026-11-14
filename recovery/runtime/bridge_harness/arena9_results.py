"""The arena's results data for a population (G9-D8): one file per closed epoch, schema `arena-results-v1`.

Written from a control directory (bridge_harness/arena9.py) at each epoch boundary, or afterwards for a finished run.
Everything on the results page comes from these files; nothing is edited by hand. The format is written down in
docs/gen9/arena-results.md. A file describes the arena as it stands at the close of its epoch:

  roster     every player registered so far: kind, version, declared card and carding, status for the next epoch
  ratings    the condition's ratings (IMPs a board against the reference) with intervals, board counts, a field
             score over the epoch's population with its worst cell, and a won/lost screen against every other player
  pairs      each pair's observed mean against the leave-one-out prediction of the other pairs, out-of-line pairs flagged
  decisions  the registry events that take effect at this boundary (admissions, retirements, tests opened, arrivals)
  tests      each open promotion test's betting state over every direct board so far
  schedule   boards played in the epoch by purpose and pair, and the next epoch's plan
  learned    per player, what a Gen 9 bot will be handed next: profile probabilities, honesty, play factor
  panel      each player's cell against each anchor (the fixed outside panel), for the version tracker

Experiments are not here: they have their own files.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from . import arena9 as a9
from . import arena_ratings as ar

SCHEMA = 'arena-results-v1'
UNTESTABLE_SE = 1.0          # a leave-one-out prediction this uncertain is the prior, not the other pairs: not tested


def _holm(pvals):
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    out, running = [0.] * len(pvals), 0.
    for rank, i in enumerate(order):
        running = max(running, min(1., (len(pvals) - rank) * pvals[i]))
        out[i] = running
    return out


def _round(x, k=4):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), k)


def ratings_section(results, players, reference, field):
    """Ratings, pairs and cells from [(i, j, x)] (a9.pooled). `field` is the list of players the field score averages
    over, equally weighted; `players` fixes the order of the fit."""
    pairs = ar.summarise(results)
    present = [p for p in players if any(p in (q.i, q.j) for q in pairs)]
    ref = reference if reference in present else present[0]
    R = ar.fit(pairs, present, ref)
    boards = {p: 0 for p in present}
    for q in pairs:
        boards[q.i] += q.n
        boards[q.j] += q.n
    prow = []
    for q in pairs:
        loo = ar.fit([x for x in pairs if x is not q], present, ref)
        a = loo._a(q.i, q.j)
        pred, var = float(a @ loo.s), float(a @ loo.C @ a)
        z = (q.mean - pred) / math.sqrt(q.se2() + var + loo.t2)
        cell, vcell = R.cell(q.i, q.j)
        se = math.sqrt(q.var / q.n) if q.n > 1 else None
        prow.append(dict(pair=f'{q.i}~{q.j}', boards=q.n, mean=_round(q.mean), se=_round(se), predicted=_round(pred), predicted_se=_round(math.sqrt(var)),
                         z=_round(z, 3), p=2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2)))), testable=math.sqrt(var) < UNTESTABLE_SE,
                         cell=_round(cell), cell_se=_round(math.sqrt(vcell))))
    tested = [r for r in prow if r['testable']]
    for r, padj in zip(tested, _holm([r['p'] for r in tested])):
        r['p_holm'], r['out_of_line'] = _round(padj, 5), padj < 0.05
    for r in prow:
        r['p'] = _round(r['p'], 5)
        r.setdefault('p_holm', None)
        r.setdefault('out_of_line', None)
    prow.sort(key=lambda r: -r['boards'])
    cells = {}
    for i in present:
        for j in present:
            if i != j:
                c, v = R.cell(i, j)
                cells[(i, j)] = (c, math.sqrt(v))
    field = [p for p in field if p in present]
    rows = []
    for p in present:
        s, v = R.strength(p)
        row = dict(player=p, strength=_round(s), se=_round(math.sqrt(v)), ci95=[_round(s - 1.96 * math.sqrt(v)), _round(s + 1.96 * math.sqrt(v))],
                   boards=boards[p])
        others = [j for j in field if j != p]
        if len(others) >= 2:
            F, vF, worst = R.field_score(p, {j: 1. / len(others) for j in others})
            row['field'] = dict(score=_round(F), se=_round(math.sqrt(vF)), worst=dict(opponent=worst['opponent'], estimate=_round(worst['estimate']),
                                                                                      se=_round(worst['se'])))
        won = [j for j in present if j != p and cells[(p, j)][0] - 1.96 * cells[(p, j)][1] > 0]
        lost = [j for j in present if j != p and cells[(p, j)][0] + 1.96 * cells[(p, j)][1] < 0]
        row['screen'] = dict(won=won, lost=lost, even=len(present) - 1 - len(won) - len(lost))
        rows.append(row)
    rows.sort(key=lambda r: -r['strength'])
    matrix = [dict(player=i, opponent=j, cell=_round(c), se=_round(se)) for (i, j), (c, se) in sorted(cells.items())]
    return dict(reference=ref, t2=_round(R.t2, 5), boards=sum(q.n for q in pairs), players=rows, pairs=prow, cells=matrix), cells


def _card_name(package):
    d = package.get('declaration') or {}
    out = {}
    for k in ('card', 'carding'):
        v = d.get(k)
        if isinstance(v, str):
            out[k] = Path(v).stem
        elif isinstance(v, dict):
            out[k] = v.get('id') or v.get('name') or 'declared'
    return out


def results_for_epoch(control, packages, n, reader_spec=None, rows=None, log=None):
    """The arena-results-v1 document at the close of epoch n."""
    from . import arena9_pipeline as pl
    control = Path(control)
    rules = json.loads((control / 'rules.json').read_text())
    rows = a9.read_results(control) if rows is None else rows
    log = a9.read_log(control) if log is None else log
    m = json.loads(a9.epoch_path(control, n).read_text())
    nxt_path = a9.epoch_path(control, n + 1)
    nxt = json.loads(nxt_path.read_text()) if nxt_path.exists() else None
    cond = rules['condition']
    upto = [r for r in rows if r['epoch'] <= n]
    st = a9.fold([e for e in log if (e.get('epoch') or 0) <= n + 1])
    order = sorted(st, key=lambda p: (st[p]['status'] != 'champion', st[p]['status'] == 'anchor', p))
    population = [p for p in (m.get('players') or {}) if st.get(p, {}).get('status') != 'retired'] or order
    events = {}
    for e in log:
        if e['event'] == 'submit':
            events.setdefault(e['player'], {}).setdefault('joined_epoch', e.get('epoch'))
        if e['event'] == 'retire':
            events.setdefault(e['player'], {})['retired_epoch'] = e.get('epoch')
        if e['event'] == 'activate':
            events.setdefault(e['player'], {})['admitted_epoch'] = e.get('epoch')
    roster = []
    for p in order:
        s = st[p]
        pkg = packages.get(p) or {}
        roster.append(dict(player=p, kind=s.get('kind'), status=s['status'], version=(s.get('package_sha256') or '')[:12],
                           identity=((nxt or m).get('players', {}).get(p) or {}).get('identity', '')[:12], since=s.get('since'),
                           joined_epoch=events.get(p, {}).get('joined_epoch'),
                           admitted_epoch=events.get(p, {}).get('admitted_epoch') if (events.get(p, {}).get('admitted_epoch') or 99) <= n + 1 else None,
                           retired_epoch=events.get(p, {}).get('retired_epoch') if (events.get(p, {}).get('retired_epoch') or 99) <= n + 1 else None,
                           test=s.get('test'), declared=_card_name(pkg)))
    ratings, cells = ratings_section(a9.pooled(upto, cond), order, rules['reference'], population)
    decisions = [dict(seq=e['seq'], epoch=e.get('epoch'), event=e['event'], player=e['player'], author=e.get('author'),
                      authority=e.get('authority'), champion=e.get('champion'), evidence=e.get('evidence'))
                 for e in log if (e.get('epoch') or 0) == n + 1 or (n == 1 and (e.get('epoch') or 0) <= 1)]
    tests = []
    for p, s in a9.fold([e for e in log if (e.get('epoch') or 0) <= n]).items():      # tests open during epoch n
        if s.get('test'):
            pair = f"{p}~{s['test']['champion']}"
            pr = rules['promotion']
            t = ar.BettingTest(alpha=pr['alpha'], beta=pr['beta'], d=pr['d'], cap=pr['cap'])
            since = s['test']['opened_epoch']           # the direct boards played since the test opened
            for r in sorted((r for r in upto if r['pair'] == pair and r['epoch'] >= since and r.get(cond) is not None),
                            key=lambda r: (r['epoch'], r['slot'], r['k'])):
                if t.update(float(r[cond])):
                    break
            tests.append(dict(pair=pair, opened_epoch=s['test']['opened_epoch'], boards=t.t, K=_round(t.K), L=_round(t.L),
                              promote_at=1 / pr['alpha'], futility_at=1 / pr['beta'], decision=t.decision))
    purpose_of = {}
    for purpose, ps in m['schedule']['purposes'].items():
        for p in ps:
            purpose_of.setdefault(p, purpose)
    floor_pairs = {p for f in m['schedule'].get('floors', []) for p in f['pairs']}
    played = {}
    for r in rows:
        if r['epoch'] != n:
            continue
        purpose = 'floor' if r.get('floor') is not None or r['pair'] in floor_pairs and r['pair'] not in purpose_of else purpose_of.get(r['pair'], 'other')
        d = played.setdefault(purpose, dict(boards=0, pairs={}))
        d['boards'] += 1
        d['pairs'][r['pair']] = d['pairs'].get(r['pair'], 0) + 1
    schedule = dict(epoch=n, boards=sum(d['boards'] for d in played.values()), played=played,
                    next=None if nxt is None else dict(epoch=n + 1, boards=a9.epoch_boards(rules, n + 1), purposes=nxt['schedule']['purposes'],
                                                       pair_weights=nxt['schedule']['pair_weights'], floors=nxt['schedule'].get('floors', [])))
    learned = {}
    if nxt is not None:
        xp = pl.epoch_experience(control, n + 1, reader_spec)
        for p, row in xp['players'].items():
            if row['boards'] or st.get(p, {}).get('kind') == 'guest':
                learned[p] = {k: row.get(k) for k in ('boards', 'deals', 'profiles_read', 'honesty_read', 'play_factor', 'off_card',
                                                      'snapshot_matches_envelopes')}
    anchors = sorted(p for p, s in st.items() if s['status'] == 'anchor')
    panel = dict(anchors=anchors, players={p: {a: dict(cell=_round(cells[(p, a)][0]), se=_round(cells[(p, a)][1]))
                                               for a in anchors if (p, a) in cells} for p in order if p not in anchors})
    return dict(schema=SCHEMA, epoch=n, condition=cond, closed_utc=(nxt or {}).get('opened_utc'),
                source=dict(epoch_manifest=m['id'], next_manifest=(nxt or {}).get('id'), rules_version=rules.get('version'),
                            source_commit=m.get('source_commit'), next_snapshot=(nxt or {}).get('experience_snapshot')),
                roster=roster, ratings=ratings, decisions=decisions, tests=tests, schedule=schedule, learned=learned, panel=panel)


def write_results(control, packages, out, reader_spec=None, epochs=None):
    """Write epoch-<nnnn>.json for every closed epoch (or those given) and index.json into `out`; returns the index."""
    control, out = Path(control), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows, log = a9.read_results(control), a9.read_log(control)
    closed = sorted(int(p.stem) for p in (control / 'epochs').glob('*.json') if a9.epoch_path(control, int(p.stem) + 1).exists())
    for n in epochs or closed:
        doc = results_for_epoch(control, packages, n, reader_spec, rows=rows, log=log)
        (out / f'epoch-{n:04d}.json').write_text(json.dumps(doc, indent=1) + '\n')
    files = sorted(p.name for p in out.glob('epoch-*.json'))
    index = dict(schema=SCHEMA, epochs=[int(f[6:10]) for f in files], files=files, latest=files[-1] if files else None)
    (out / 'index.json').write_text(json.dumps(index, indent=1) + '\n')
    return index
