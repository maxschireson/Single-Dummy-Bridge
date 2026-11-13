#!/usr/bin/env python3
"""Checks of the Gen 7 prototype against recorded Gen 6 tables, on deals the net never trained on.

  python scripts/gen7_check.py fidelity  --episodes DIR
  python scripts/gen7_check.py inference --episodes DIR --policy policy.npz [--split 1] [--tables 60]
  python scripts/gen7_check.py match     --episodes DIR --policy policy.npz [--boards 40]
  python scripts/gen7_check.py speed     --episodes DIR --policy policy.npz [--boards 10]
  python scripts/gen7_check.py auction   --episodes DIR [--per-trick 40]

fidelity   The Gen 6 engine built here from the repository's model files reproduces what the live
           bot recorded: its estimates at deal-list decisions where the whole list was solved (these
           have no sampling in them), and its tie-break card.
inference  At recorded deal-list decisions of Gen 6 seats: the log-probability each weighting gives
           the true layout (uniform over the list, Gen 6's scorer weights, scorer times the net's
           play likelihood), and the true-deal double-dummy cost of the card each weighting picks.
           Recorded positions are replayed, so every weighting sees the same position.
match      Gen 7 against the local Gen 6 on recorded boards: same contract and opening lead in both
           rooms, sides swapped, same random stream for the same position, so a board is flat unless
           Gen 7 chooses differently.

speed      CPU per table: Gen 6 at all four seats (recorded lead, search from trick 1) against the
           fast data table (the net plays the lead and tricks before --search-from-trick, Gen 6's
           search after that).

auction    How much of Gen 6's card depends on the auction, and how much on which layouts it happened
           to draw. Recorded positions are decided again four ways: as live (twice, with different
           draws), with another deal's auction, and with no auction knowledge at all (every card-fit
           layout equally likely). Each choice is costed by a 256-layout Gen 6 with the real auction.
           This is the size of the auction signal a clone of Gen 6's card could learn, and the part
           of the clone's disagreement that is Gen 6's own sampling noise.

The local Gen 6 uses the hand-fit scorer for layouts at every trick and never loads the lead net
(which needs TensorFlow), so the opening lead is always taken from the record.
Deals are split as in gen7_build_dataset.py: 0 train, 1 validation, 2 test.
"""
import argparse
from dataclasses import replace
import gzip
import json
import math
from pathlib import Path
import random
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.core import Board, Game, card, imps, symbol
from bridge_harness.gen6 import View, systematic
from bridge_harness.gen7 import Gen7Player, floored, hidden_plays, player, resolved
from bridge_harness.runner import play_table

SCORER = 'models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz'
GEN5_POLICY = 'models/cardplay/gen5-2026-11-10/policy.npz'
FAST = dict(lead_source='scorer', mid_from_trick=14, mid_samples=32, list_from_trick=7, list_solve=256)     # the live 6-32 after the lead


def spec(engine, policy=None, **gen7):
    s = dict(id='6-32' if engine == 'gen6' else '7-32', engine=engine, samples=32, near_tie=0., exploration=0.,
             policy=GEN5_POLICY, scorer=SCORER, gen6=dict(FAST))
    if engine == 'gen7':
        s.update(gen7_policy=str(Path(policy).resolve()), gen7=gen7)
    return s


def split_of(family):
    bucket = int(family[:8], 16) % 10
    return 2 if bucket == 0 else 1 if bucket == 5 else 0


def records(directory, split, seed=0):
    """(family, bot of each seat's controller, record) for every played record of the split's deals, in a fixed shuffled order."""
    files = sorted(Path(directory).glob('*.json.gz'))
    random.Random(seed).shuffle(files)
    for path in files:
        with gzip.open(path, 'rt') as f:
            d = json.load(f)
        if split >= 0 and split_of(d['family']) != split:
            continue
        who = {'candidate': d['candidate'], 'opponent': d['opponent']}
        for e in d['unique_tables'].values():
            if e.get('schema_version') != 'v4-passed-out-v1' and e['tables'][0].get('actions'):
                yield d['family'], [who[x] for x in e['assignments']], e


def solve(p, o, worlds):
    return p.dds.solve_batch(worlds, o.contract.trump, o.leader, o.trick, fixed_seats=[s for s, h in enumerate(o.known_hands) if h is not None])


def utilities(o, values):
    """Per legal card, the deciding side's final tricks (negated for the defence), as the engine counts them."""
    declaring = o.actor % 2 == o.contract.declarer % 2
    remaining = 13 - len(o.history) // 4
    out = {}
    for c, t in values.items():
        total = o.declarer_tricks + (t if declaring else remaining - t)
        out[c] = total if declaring else -total
    return out


def best_cards(p, o, view, assign, logw, rng, most=256):
    """The cards with the top weighted-mean tricks, the engine's way: the list (cut to `most` by weight) solved once per layout."""
    w = np.exp(logw - logw.max())
    index, weights = systematic(w, most, rng) if len(assign) > most else (np.arange(len(assign)), w / w.sum())
    means = {c: 0. for c in o.legal}
    for (values, _), share in zip(solve(p, o, [view.world(assign[i]) for i in index]), weights):
        for c, u in utilities(o, values).items():
            means[c] += float(share) * u
    top = max(means.values())
    return sorted(c for c, v in means.items() if top - v <= 1e-9)


def fidelity(a):
    six = player(spec('gen6'), ROOT)
    checked = ties = same_card = 0
    worst = 0.
    for family, bots, e in records(a.episodes, a.split):
        game = Game(Board.from_dict(e['board']))
        for act in e['tables'][0]['actions']:
            c = card(act['card'])
            o = game.observation()
            g = act.get('gen6') or {}
            if bots[o.controller] == '6-32' and g.get('source') == 'deal_list' and g.get('listed', 1 << 30) <= 256 and act.get('estimates'):
                view = View(o)
                worlds, weights, _ = six.layouts(o, view, 'list', np.random.default_rng(0))
                stats = six.dds.cache_stats()
                d = six.search_decision(o, random.Random(0), solve(six, o, worlds), weights, stats, stats, {})
                worst = max(worst, max(abs(d.details['estimates'][k]['utility'] - v['utility']) for k, v in act['estimates'].items()))
                checked += 1
                if act.get('selector'):
                    ties += 1
                    same_card += six.break_ties(o, random.Random(0), d).card == c
            game.play(c)
        if checked >= a.decisions:
            break
    six.close()
    print(json.dumps(dict(check='fidelity', decisions=checked, largest_estimate_difference=worst, tie_breaks=ties, same_tie_break_card=same_card)))


def logsumexp(x):
    m = x.max()
    return m + math.log(np.exp(x - m).sum())


def inference(a):
    p = Gen7Player(spec('gen7', a.policy, tie_break='gen5'), ROOT)
    taus, floors = (.25, .5, .75, 1.), (.02, .05, .15)
    rows, tables, skipped, started = [], 0, 0, time.time()
    for family, bots, e in records(a.episodes, a.split):
        if tables >= a.tables or time.time() - started > a.seconds:
            break
        tables += 1
        board = Board.from_dict(e['board'])
        game = Game(board)
        for act in e['tables'][0]['actions']:
            c = card(act['card'])
            o = game.observation()
            g = act.get('gen6') or {}
            if bots[o.controller] in ('6-32', '6-256') and g.get('source') == 'deal_list' and len(o.legal) > 1:
                view = View(o)
                if view.count() > a.max_list:
                    skipped += 1
                else:
                    assign = view.every()
                    truth = np.array([next(j for j, s in enumerate(view.hidden) if int(x) in game.hands[s]) for x in view.unseen])
                    t = int(np.flatnonzero((assign == truth).all(axis=1))[0])
                    logw = p.layout_log_weights(o, view, assign)
                    plays = hidden_plays(o)
                    logp, options = p.play_log_probabilities(o, view, assign, plays)
                    lead = np.array([i == 0 for i, _, _ in plays])
                    row = dict(family=family, trick=len(o.history) // 4 + 1, listed=len(assign), declaring=o.controller == o.contract.declarer,
                               hidden_gen6=all(bots[s if s != o.contract.dummy else o.contract.declarer] in ('6-32', '6-256') for s in view.hidden),
                               plays=len(plays), uniform=-math.log(len(assign)), scorer=float(logw[t] - logsumexp(logw)))
                    for f in floors:
                        ll = floored(logp, options, f).sum(axis=0)
                        for tau in taus:
                            x = logw + tau * ll
                            row[f'play f{f} t{tau}'] = float(x[t] - logsumexp(x))
                    f = a.floor
                    ll = floored(logp, options, f)
                    row['play alone'] = float(ll.sum(0)[t] - logsumexp(ll.sum(0)))
                    no_lead = logw + a.tau * ll[~lead].sum(axis=0)
                    row['play without the lead'] = float(no_lead[t] - logsumexp(no_lead))
                    # the card each weighting picks, costed on the real deal
                    true = utilities(o, solve(p, o, [tuple(tuple(sorted(h)) for h in game.hands)])[0][0])
                    top = max(true.values())
                    for name, lw in (('gen6', logw), ('gen7', logw + a.tau * ll.sum(axis=0))):
                        cards = best_cards(p, o, view, assign, lw, np.random.default_rng(len(rows)))
                        row[name + '_cost'] = float(np.mean([top - true[x] for x in cards]))
                        row[name + '_cards'] = [symbol(x) for x in cards]
                    row['recorded_cost'] = float(top - true[c])
                    rows.append(row)
            game.play(c)
    p.close()

    def mean_se(values, families):
        """Mean and its standard error with deals as the unit."""
        v = np.asarray(values, float)
        by = {}
        for x, f in zip(v, families):
            by.setdefault(f, []).append(x)
        totals = np.array([sum(x) for x in by.values()])
        counts = np.array([len(x) for x in by.values()])
        mean = totals.sum() / counts.sum()
        se = math.sqrt(((totals - mean * counts) ** 2).sum() * len(by) / max(1, len(by) - 1)) / counts.sum()
        return round(float(mean), 4), round(float(se), 4)

    def report(subset, label):
        if not subset:
            return None
        fam = [r['family'] for r in subset]
        out = dict(label=label, decisions=len(subset), deals=len(set(fam)), mean_listed=round(float(np.mean([r['listed'] for r in subset])), 1))
        out['log_probability_of_true_layout'] = {k: mean_se([r[k] for r in subset], fam)[0] for k in subset[0]
                                                 if k in ('uniform', 'scorer', 'play alone', 'play without the lead') or k.startswith('play f')}
        chosen = f'play f{a.floor} t{a.tau}'
        out['gain_over_scorer_nats'] = mean_se([r[chosen] - r['scorer'] for r in subset], fam)
        out['true_layout_more_likely_share'] = round(float(np.mean([r[chosen] > r['scorer'] for r in subset])), 3)
        out['dd_cost_gen6'], out['dd_cost_gen7'] = mean_se([r['gen6_cost'] for r in subset], fam), mean_se([r['gen7_cost'] for r in subset], fam)
        out['dd_cost_saved_by_gen7'] = mean_se([r['gen6_cost'] - r['gen7_cost'] for r in subset], fam)
        out['different_cards_share'] = round(float(np.mean([r['gen6_cards'] != r['gen7_cards'] for r in subset])), 4)
        return out

    result = dict(check='inference', split=a.split, tables=tables, decisions=len(rows), skipped_long_lists=skipped, max_list=a.max_list,
                  tau=a.tau, floor=a.floor, net_rows=p.net_rows, seconds=round(time.time() - started),
                  groups=[report(rows, 'all'), report([r for r in rows if r['declaring']], 'declarer deciding'),
                          report([r for r in rows if not r['declaring']], 'defender deciding'),
                          report([r for r in rows if r['hidden_gen6']], 'hidden seats played by Gen 6'),
                          report([r for r in rows if not r['hidden_gen6']], 'a hidden seat played by another bot'),
                          *[report([r for r in rows if r['trick'] == k], f'trick {k}') for k in range(6, 13)]])
    result['groups'] = [g for g in result['groups'] if g]
    if a.out:
        Path(a.out).write_text(json.dumps(dict(result, rows=rows), indent=1))
    print(json.dumps(result, indent=1))


def gen7_block(a):
    """The Gen 7 bot's settings: --gen7 (a JSON object, a file holding one, or a plan file with --bot) or the single switches."""
    if not a.gen7:
        return dict(play_weight=a.tau, play_floor=a.floor, tie_break=a.tie_break, search_from_trick=a.search_from_trick,
                    play_max_layouts=a.play_max_layouts)
    block = json.loads(Path(a.gen7).read_text() if Path(a.gen7).exists() else a.gen7)
    if 'gen7_bots' in block:
        block = block['gen7_bots'][a.bot or next(iter(block['gen7_bots']))].get('gen7', {})
    return resolved(block)


def tree_use(tables):
    """What the tree did at the Gen 7 seats' decisions of these tables."""
    notes = [x['gen7_tree'] for t in tables for x in t['actions'] if x['player'] == '7' and 'gen7_tree' in x]
    used = [n for n in notes if n['consulted']]
    switched = sum(1 for t in tables for x in t['actions'] if x['player'] == '7' and x.get('gen7_tree', {}).get('consulted')
                   and x['selected_pimc_gap'] > 1e-9)
    out = dict(decisions_in_a_stage=len(notes), consulted=len(used), switched=switched, over_budget=sum(bool(n.get('over_budget')) for n in notes))
    if used:
        solves = np.array([n['solves'] for n in used])
        seconds = np.array([n['seconds'] for n in used])
        out.update(seconds_per_consulted=round(float(seconds.mean()), 3), seconds_p95=round(float(np.quantile(seconds, .95)), 3),
                   seconds_max=round(float(seconds.max()), 2), solves_per_consulted=round(float(solves.mean()), 1),
                   solves_p95=int(np.quantile(solves, .95)), solves_p99=int(np.quantile(solves, .99)), solves_max=int(solves.max()),
                   lines_per_consulted=round(float(np.mean([n['lines'] for n in used])), 1),
                   net_rows_per_consulted=round(float(np.mean([n['net_rows'] for n in used])), 1))
    return out


def match(a):
    six = player(spec('gen6'), ROOT)
    block = gen7_block(a)
    seven = Gen7Player(spec('gen7', a.policy, **block), ROOT)
    players = {'6': six, '7': seven}
    results, seen, started, played = [], set(), time.time(), []
    for family, bots, e in records(a.episodes, a.split):
        if len(results) >= a.boards or time.time() - started > a.seconds:
            break
        if family in seen:
            continue
        seen.add(family)
        lead = None if a.search_from_trick > 1 else card(e['tables'][0]['actions'][0]['card'])
        board = replace(Board.from_dict(e['board']), opening_lead=lead)
        scores, cpu, changed = [], [], 0
        for room in (0, 1):
            before = time.process_time()
            t = play_table(board, ['7' if s % 2 == room else '6' for s in range(4)], players, seed=a.seed, rng_group='table')
            if t['status'] != 'ok':
                raise RuntimeError(t.get('traceback'))
            cpu.append(time.process_time() - before)
            scores.append(t['ns_score'])
            played.append(t)
        results.append(dict(family=family, contract=e['board']['contract'], declarer=e['board']['declarer'], ns_scores=scores,
                            imps=imps(scores[0] - scores[1]), cpu=cpu))
        if len(results) % 5 == 0:
            x = np.array([r['imps'] for r in results])
            print(json.dumps(dict(boards=len(results), imps_per_board=round(float(x.mean()), 3), nonflat=int((x != 0).sum()),
                                  seconds=round(time.time() - started))), flush=True)
    six.close()
    seven.close()
    x = np.array([r['imps'] for r in results], float)
    out = dict(check='match', boards=len(x), gen7_imps_per_board=round(float(x.mean()), 3),
               standard_error=round(float(x.std(ddof=1) / math.sqrt(len(x))), 3) if len(x) > 1 else None,
               nonflat_boards=int((x != 0).sum()), won=int((x > 0).sum()), lost=int((x < 0).sum()),
               cpu_seconds_per_table=round(float(np.mean([c for r in results for c in r['cpu']])), 2),
               tree=tree_use(played) if seven.stages else None, settings=block, seconds=round(time.time() - started))
    if a.out:
        Path(a.out).write_text(json.dumps(dict(out, boards_detail=results), indent=1))
    print(json.dumps(out, indent=1))


def speed(a):
    six = player(spec('gen6'), ROOT)
    fast = Gen7Player(spec('gen7', a.policy, play_weight=0., tie_break='gen5', search_from_trick=a.search_from_trick, net_sample=True), ROOT)
    rows, seen = [], set()
    for family, bots, e in records(a.episodes, a.split):
        if len(rows) >= a.boards:
            break
        if family in seen:
            continue
        seen.add(family)
        board = Board.from_dict(e['board'])
        row = {}
        for name, p_, b in (('gen6', six, replace(board, opening_lead=card(e['tables'][0]['actions'][0]['card']))), ('fast', fast, replace(board, opening_lead=None))):
            before = time.process_time()
            t = play_table(b, ['x'] * 4, {'x': p_}, seed=a.seed)
            if t['status'] != 'ok':
                raise RuntimeError(t.get('traceback'))
            row[name] = time.process_time() - before
            row[name + '_searched'] = sum(1 for x in t['actions'] if x.get('estimates'))
            row[name + '_by_trick'] = [round(sum(x['seconds'] for x in t['actions'] if x['ply'] // 4 == k), 3) for k in range(13)]
        rows.append(row)
    six.close()
    fast.close()
    mean = lambda k: round(float(np.mean([r[k] for r in rows])), 3)
    print(json.dumps(dict(check='speed', boards=len(rows), search_from_trick=a.search_from_trick, gen6_cpu_per_table_after_the_lead=mean('gen6'),
                          fast_cpu_per_table=mean('fast'), ratio=round(mean('gen6') / mean('fast'), 2),
                          gen6_searched_decisions=mean('gen6_searched'), fast_searched_decisions=mean('fast_searched'),
                          gen6_seconds_by_trick=[round(float(np.mean([r['gen6_by_trick'][k] for r in rows])), 3) for k in range(13)],
                          fast_seconds_by_trick=[round(float(np.mean([r['fast_by_trick'][k] for r in rows])), 3) for k in range(13)])))


def auction(a):
    six = player(spec('gen6'), ROOT)
    groups = {1: 'trick 1', 2: 'trick 2', 3: 'tricks 3-4', 4: 'tricks 3-4', 5: 'tricks 5-6', 6: 'tricks 5-6'}
    name = lambda trick: groups.get(trick, 'tricks 7-9' if trick <= 9 else 'tricks 10-12')
    want = {'trick 1': a.per_trick // 4, 'trick 2': a.per_trick // 2}
    rows, last_auction, started = [], None, time.time()
    score = six.scorer.type_log_score

    def means(o_weights, o, seed, samples=32, blind=False):
        view = View(o_weights)
        six.samples = samples
        six.scorer.type_log_score = (lambda length, hon, *rest: np.zeros(len(length))) if blind else score
        try:
            worlds, weights, _ = six.layouts(o_weights, view, six.source(o_weights, view), np.random.default_rng(seed))
        finally:
            six.samples, six.scorer.type_log_score = 32, score
        out = {c: 0. for c in o.legal}
        for (values, _), share in zip(solve(six, o, worlds), weights):
            for c, u in utilities(o, values).items():
                out[c] += float(share) * u
        return out

    def best(m):
        top = max(m.values())
        return sorted(c for c, v in m.items() if top - v <= 1e-9)

    for family, bots, e in records(a.episodes, a.split):
        if time.time() - started > a.seconds:
            break
        board = Board.from_dict(e['board'])
        game = Game(board)
        taken = set()
        for act in e['tables'][0]['actions']:
            c = card(act['card'])
            o = game.observation()
            group = name(len(o.history) // 4 + 1)
            have = sum(r['group'] == group for r in rows)
            if (bots[o.controller] == '6-32' and act.get('gen6') and o.history and len(o.legal) > 1 and last_auction is not None
                    and have < want.get(group, a.per_trick) and group not in taken):
                taken.add(group)                    # one position per phase per table
                reference = means(o, o, 99, samples=256)
                top = max(reference.values())
                cost = lambda cards: float(np.mean([top - reference[x] for x in cards]))
                live, again = best(means(o, o, 0)), best(means(o, o, 1))
                other = best(means(replace(o, auction=last_auction), o, 0))
                blind = best(means(o, o, 0, blind=True))
                rows.append(dict(group=group, family=family, live=cost(live), again=cost(again), other=cost(other), blind=cost(blind),
                                 same_again=live == again, same_other=live == other, same_blind=live == blind,
                                 first_again=live[0] == again[0], first_other=live[0] == other[0], first_blind=live[0] == blind[0]))
            game.play(c)
        last_auction = tuple(e['board']['auction'])
    six.close()
    out = []
    for group in ('trick 1', 'trick 2', 'tricks 3-4', 'tricks 5-6', 'tricks 7-9', 'tricks 10-12'):
        sub = [r for r in rows if r['group'] == group]
        if sub:
            m = lambda k: round(float(np.mean([r[k] for r in sub])), 4)
            out.append(dict(phase=group, decisions=len(sub),
                            tricks_given_up=dict(live_32_layouts=m('live'), live_other_draw=m('again'), another_deals_auction=m('other'), no_auction=m('blind')),
                            same_best_cards_as_live=dict(other_draw=m('same_again'), another_deals_auction=m('same_other'), no_auction=m('same_blind'))))
    print(json.dumps(dict(check='auction', decisions=len(rows), seconds=round(time.time() - started), phases=out), indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(dict(rows=rows, phases=out), indent=1))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('check', choices=('fidelity', 'inference', 'match', 'speed', 'auction'))
    p.add_argument('--episodes', type=Path, required=True)
    p.add_argument('--policy', type=Path)
    p.add_argument('--split', type=int, default=2, help='0 train, 1 validation, 2 test (default), -1 every deal')
    p.add_argument('--tables', type=int, default=60)
    p.add_argument('--decisions', type=int, default=300)
    p.add_argument('--boards', type=int, default=40)
    p.add_argument('--per-trick', type=int, default=40)
    p.add_argument('--seconds', type=float, default=1e9)
    p.add_argument('--max-list', type=int, default=3500)
    p.add_argument('--tau', type=float, default=.5)
    p.add_argument('--floor', type=float, default=.05)
    p.add_argument('--tie-break', default='net')
    p.add_argument('--search-from-trick', type=int, default=1)
    p.add_argument('--play-max-layouts', type=int, default=1024)
    p.add_argument('--gen7', help="match: the Gen 7 bot's whole `gen7` block as JSON, a file holding it, or a plan file "
                                  '(configs/round7-alpha.json); replaces the five switches above')
    p.add_argument('--bot', help='with a plan file in --gen7: which of its gen7_bots (default: the first)')
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--out')
    a = p.parse_args()
    {'fidelity': fidelity, 'inference': inference, 'match': match, 'speed': speed, 'auction': auction}[a.check](a)


if __name__ == '__main__':
    main()
