"""Assemble README.md from the result files so that every number in it comes from a script."""
import collections
import json
import os

RES = 'results' if os.path.isdir('results') else '.'


def rp(name):
    return os.path.join(RES, name)

SYM = {'S': '♠', 'H': '♥', 'D': '♦', 'C': '♣'}


def cs(c):
    return SYM[c[0]] + c[1:].replace('T', '10')


def load(*files):
    rows = []
    for f in files:
        try:
            rows += [json.loads(l) for l in open(rp(f))]
        except FileNotFoundError:
            pass
    return rows


data = json.load(open('fusion_deals.json'))
sets = data['sets']
deals = {d['id']: d for d in data['deals']}
out = []
w = out.append

# ---------------------------------------------------------------- exploration batch (A6 hands, ids W3/E4/E3/W4)
ex = load('res2a.jsonl', 'res2b.jsonl')
qside = {'W3': 'W', 'W4': 'W', 'E3': 'E', 'E4': 'E'}
tab = collections.Counter()
decl_led = 0
for r in ex:
    first = next(t.split() for t in r['play'] if t.split()[0][2] == 'D')
    if first[0][0] in 'EW':
        kind = 'def'
    else:
        decl_led += 1
        lead, third = first[0], first[2]
        kind = 'A' if lead[3] in '45' and third[3] == 'A' else 'K' if lead[3] in '45' and third[3] == 'K' else 'fin'
    tab[(kind, qside[r['deal']], r['made'])] += 1
frac = lambda kind, q: '%d/%d' % (tab[(kind, q, True)], tab[(kind, q, True)] + tab[(kind, q, False)])
by = collections.Counter()
for r in ex:
    by[(r['bot'], r['deal'], r['made'])] += 1
lay = lambda bot, d: '%d/%d' % (by[(bot, d, True)], by[(bot, d, True)] + by[(bot, d, False)])

# ---------------------------------------------------------------- final results
fin = {'gen6': load('final_gen6.jsonl'), 'gen7': load('final_gen7.jsonl'),
       'pimc-make': [r for r in load('res3b.jsonl') if r['bot'] == 'pimc-make'] + load('final_pimc_make_s6.jsonl')}


def cell(bot, st, coupled=True):
    rows = [r for r in fin[bot] if r['deal'] in st['deals']]
    made = collections.defaultdict(dict)
    for r in rows:
        made[r['deal']][r['seed']] = r['made']
    if not all(d in made for d in st['deals']):
        return '–'
    per = ' '.join('%d/%d' % (sum(made[d].values()), len(made[d])) for d in st['deals'])
    if not coupled:
        return per
    seeds = set.intersection(*[set(made[d]) for d in st['deals']])
    passed = sum(all(made[d][s] for d in st['deals']) for s in seeds)
    return '**%d/%d** (%s)' % (passed, len(seeds), per)


trap = [s for s in sets if s['kind'] in ('tie', 'strict') and s['id'] != 'L6']


def total(bot):
    p = n = 0
    for st in trap:
        made = collections.defaultdict(dict)
        for r in fin[bot]:
            if r['deal'] in st['deals']:
                made[r['deal']][r['seed']] = r['made']
        seeds = set.intersection(*[set(made[d]) for d in st['deals']])
        p += sum(all(made[d][s] for d in st['deals']) for s in seeds)
        n += len(seeds)
    return p, n


g6, g7 = total('gen6'), total('gen7')

# ---------------------------------------------------------------- text
w('# Strategy-fusion test set and single-dummy sure tricks')
w('')
w('12 November 2026. Built against `maxschireson/Single-Dummy-Bridge` main (shallow clone of that day), using its '
  '`bridge_harness` engine, DDS build and model files. `mkreadme.py` assembled the tables and most counts from the '
  'result files; a few counts quoted in the text were read off script output by hand.')
w('')
w('## Contents')
w('')
w('| File | What it is |')
w('| --- | --- |')
w('| `fusion_deals.json`, `fusion_deals.pbn` | %d sets, %d deals. JSON fields load with `Board.from_dict`; extra fields: `set`, `layout`, `weight`, `avoid`, `critical`. |' % (len(sets), len(deals)))
w('| `fusion_test.py` | Runs a declarer over the sets against the oracle defender and scores by set. |')
w('| `fusionlab.py` | `OracleDefender`, `run()`, bot factories (repo PIMC, local Gen 6, Gen 7 standard). |')
w('| `exact.py` | Exact single-dummy value against best defence for a small set of layouts (Pareto fronts over layouts). Used to certify each set. |')
w('| `sure.py`, `surebot.py` | Single-dummy sure tricks (pooled-defender search) and the rule "a card that guarantees the contract comes first" as a wrapper on any declarer. |')
w('| `sure.cpp`, `SEARCH.md` | The same sure-trick search in C++ above a resident table of small endings, with its checks, timings and table sizes. Helpers: `csure.py`, `check_cpp.py`, `check_cpp_positions.py`, `bench_cpp.py`, `runpos.py`, `split.py`, `build_cost.py`, `gen_table_positions.py`, `table_size.py`, `table_size_shapes.py`, `mksearch.py`. |')
w('| `TABLE_BUILD.md`, `pooled_ref.py`, `endtable_ref.py`, `endtable_vectors.jsonl` | Build specification for the resident ending table, with the reference for the game under shape knowledge, the reference index and test vectors. Checks: `check_pooled_ref.py`, `check_endtable_ref.py`, `make_vectors.py`. |')
w('| `verify.py`, `scripted.py`, `trace.py`, `third_hand.py`, `families.py`, `report.py`, `to_pbn.py`, `check_sure.py`, `check_sure_reduction.py`, `run_surebot.py`, `sure_positions.py`, `lookup_gain.py`, `mkreadme.py` | Checks, generation and reporting. |')
w('| `results/` | Raw runs and certification output. |')
w('')
w('Run: `SDB_ROOT=/path/to/Single-Dummy-Bridge python fusion_test.py fusion_deals.json --bot gen6 --seeds 6` '
  '(DDS built with `scripts/build_dds.py`; hand-fit scorer v0, Gen 5 policy and Gen 7 policy v4 restored with their `restore` scripts).')
w('')
w('## 1. How the error arises, in numbers')
w('')
c = json.load(open(rp('cert_A6.json')))['A6']['exact']
w('Set A6: 6♠, ♦AJ5 opposite ♦K104, one club loser, a sure strip-and-club-exit. Position after the heart lead and two '
  'rounds of trumps (10 cards left, North to lead). Two layouts, ♦Q with West (3 diamonds) or East (4), weighted 15:20. '
  '"Fused" is the PIMC value (share of layouts where the card is double-dummy good enough). "True" is the best any '
  'single line starting with that card can do against best defence (`exact.py`).')
w('')
w('| Card | Fused | True |')
w('| --- | --- | --- |')
groups = collections.OrderedDict()
for card_, v in c['cards'].items():
    groups.setdefault((round(v['fused'], 2), round(v['true'], 2)), []).append(card_)
for (f, t), cards in groups.items():
    w('| %s | %.2f | %.2f |' % (' '.join(cs(x) for x in cards), f, t))
w('')
th = json.load(open(rp('cert_A6_third.json')))['cards']
g6est = None
for r in load('res2b.jsonl'):
    if r['bot'] == 'gen6' and r['deal'] == 'W3':
        g6est = next(e['est'] for e in r['est'] if e['card'] == 'DA' and e['seat'] == 'S')
        g6lead = next(e['est'] for e in r['est'] if e['card'] == 'D4' and e['seat'] == 'N')
        break
w('The low diamond is rated the same as the cards that keep the sure line. It is not rated higher: in this family the '
  'error is a tie, not a wrong preference. The clubs are 1.00 true as well as the hearts because there is more than '
  'one sound order of play.')
w('')
w('After ♦4 and a low card from East the two layouts give ♦J %.2f fused and %.2f true, ♦A %.2f and %.2f. Gen 6\'s own '
  'sample at that card (same hands) read ♦A %.2f, ♦J %.2f, ♦5 %.2f mean tricks: rising with the far honour scores '
  'higher than the finesse because in part of the sample double dummy can still endplay the other defender. '
  'When it led the diamond, ♦4 and ♣7 were both %.1f.'
  % (th['DJ']['fused'], th['DJ']['true'], th['DA']['fused'], th['DA']['true'], g6est['DA'], g6est['DJ'], g6est['D5'], g6lead['D4']))
w('')
w('Other ties the certification tables show (all 1.00 fused):')
w('')
c4 = json.load(open(rp('cert_A4.json')))['A4']['exact']['cards']
cb = json.load(open(rp('cert_B6.json')))['B6']['exact']['cards']
cm = json.load(open(rp('cert_B6m.json')))['B6m']['exact']['cards']
c6 = json.load(open(rp('cert_S6.json')))['S6']['exact']['cards']
cl = json.load(open(rp('cert_L6.json')))['L6']['exact']['cards']
w('- A4 (4♠): a club before the second top heart is cashed is %.2f true. The defenders take their clubs and get off lead in hearts.' % c4['C3']['true'])
w('- B6 (master trump with West): the trump exit before the strip is %.2f true. ♦5 to the king stays %.2f, because West will be the one on lead and must lead into the ace-jack; ♦A is %.2f.' % (cb['S3']['true'], cb['D5']['true'], cb['DA']['true']))
w('- B6m (master trump with East): the reverse. ♦5 to the king is %.2f true, ♦A stays %.2f. A heart to the queen at that point (dummy\'s entry, needed later for the club ruff) is %.2f.' % (cm['D5']['true'], cm['DA']['true'], cm['H3']['true']))
w('- S6: the club exit before the hearts are eliminated is %.2f true.' % c6['C7']['true'])
w('- L6 (the A6 hands on a low diamond lead, trick one): low or the ten from dummy is %.2f true, the king %.2f fused and %.2f true.' % (cl['D4']['true'], cl['DK']['fused'], cl['DK']['true']))
w('')
w('## 2. The queen in the three-card hand')
w('')
w('Hypothesis: the declarer misses the endplay, falls back on the guess, takes it with the odds and so fails when the '
  'queen is in the shorter holding. Tested on the A6 hands in four layouts (%d runs: repo `PIMCPlayer` with the make '
  'objective and random ties, local Gen 6, Gen 7 standard with and without the tree), before the sets were finalised.' % len(ex))
w('')
w('- Declarer broke diamonds itself in %d of %d runs.' % (decl_led, len(ex)))
w('- Low to the ace first (leaves only the finesse through West): made %s with the queen West, %s with the queen East.' % (frac('A', 'W'), frac('A', 'E')))
w('- Low to the king first (leaves only the finesse through East): made %s with the queen West, %s with the queen East.' % (frac('K', 'W'), frac('K', 'E')))
w('- Immediate finesse: made %d of %d.' % (tab[('fin', 'W', True)] + tab[('fin', 'E', True)], sum(tab[('fin', q, m)] for q in 'WE' for m in (True, False))))
w('')
w('| Layout | PIMC make | Gen 6 | Gen 7 std |')
w('| --- | --- | --- | --- |')
for d, name in (('W3', 'Q West, 3 diamonds'), ('E4', 'Q East, 4 diamonds'), ('E3', 'Q East, 3 diamonds'), ('W4', 'Q West, 4 diamonds')):
    w('| %s | %s | %s | %s |' % (name, lay('pimc-make', d), lay('gen6', d), lay('gen7', d)))
w('')
w('The length of the queen\'s suit did not decide the result. Which top honour was cashed first did, and that was set '
  'by which hand was on lead when the tie was broken (Gen 6: always dummy, so always the ace). The odds were not '
  'consulted at that point: the fused value of rising with the far honour was higher than that of either finesse.')
w('')
g = collections.Counter()
for bot in ('gen6', 'gen7'):
    for r in fin[bot]:
        if r['deal'].startswith('G7'):
            g[(bot, r['deal'], r['made'])] += 1
pm = collections.Counter()
for r in fin['pimc-make']:
    if r['deal'].startswith('G7'):
        pm[(r['deal'], r['made'])] += 1
gg = lambda bot, d: '%d/%d' % (g[(bot, d, True)], g[(bot, d, True)] + g[(bot, d, False)])
w('Reference pair G7 (7♠, the same diamond suit, nothing can be thrown in, and the count shows diamonds 3-4 once '
  'hearts and clubs have been played): Gen 6 made %s with the queen in the three-card hand and %s with it in the '
  'four-card hand; Gen 7 standard %s and %s; random-tie PIMC %d/%d and %d/%d. Gen 6 led low to the ace at trick 9 in all '
  'twelve runs and finessed West. The direction is habit, not count.'
  % (gg('gen6', 'G7-QW'), gg('gen6', 'G7-QE'), gg('gen7', 'G7-QW'), gg('gen7', 'G7-QE'),
     pm[('G7-QW', True)], pm[('G7-QW', True)] + pm[('G7-QW', False)], pm[('G7-QE', True)], pm[('G7-QE', True)] + pm[('G7-QE', False)]))
w('')
w('Consequence for test design: one layout with the queen in the short hand is decided by tie-breaks. A pair of '
  'layouts that differ only by exchanging the queen with a spot card fails any line that needs the guess in at least '
  'one of the two. Each set is such a pair; within a set the layouts share one random stream per seed.')
w('')
w('## 3. The defenders')
w('')
pl = collections.Counter((r['deal'], r['made']) for r in load('final_gen6_plain.jsonl'))
g6o = collections.Counter((r['deal'], r['made']) for r in fin['gen6'])
w('A plain double-dummy defender is not a usable opponent for these deals. Once the contract is "cold" because double '
  'dummy guesses the queen, every defensive card is double-dummy equal. Against a defender that plays its lowest '
  'double-dummy-optimal card, Gen 6 made A6-QE in %d of %d runs (after winning a club at trick 8 East led a diamond '
  'round to the tenace); against `OracleDefender`, %d of %d. An intermediate version that only refused to lead the suit '
  'threw club winners until declarer\'s third club stood up.'
  % (pl[('A6-QE', True)], pl[('A6-QE', True)] + pl[('A6-QE', False)], g6o[('A6-QE', True)], g6o[('A6-QE', True)] + g6o[('A6-QE', False)]))
w('')
w('`OracleDefender` plays double-dummy optimally on the true deal and breaks ties, in order: best in the deal where the '
  'queen is promoted above declarer\'s honours (so the guess cannot succeed), not leading the critical suit, keeping '
  'length with declarer and dummy when discarding, lowest card. On the A6 and S6 hands scripted guessing lines were '
  'checked to be down against it in the wrong layout. The same indifference applies to a PIMC defender at the table.')
w('')
w('## 4. The sets and what the bots did')
w('')
w('Bold = sets passed out of seeds (every layout made in the same seed); in brackets, makes per layout in the order '
  'listed. Gen 6 = local 6-32 built as in `scripts/gen7_check.py`. Gen 7 std = the `7s-32` block of '
  '`configs/round7-candidate-phase1.json`. PIMC = repo `PIMCPlayer`, make objective, 32 uniform layouts, random ties; '
  'its seeds were not coupled within a set except on S6, so only makes per layout are shown.')
w('')
w('| Set | Kind | Contract, layouts | Gen 6 | Gen 7 std | PIMC make |')
w('| --- | --- | --- | --- | --- | --- |')
for st in sets:
    ds = [deals[i] for i in st['deals']]
    lay_txt = '; '.join(d['layout'] for d in ds)
    scored = st['kind'] != 'guess'
    pc = cell('pimc-make', st, coupled=(st['id'] == 'S6'))
    w('| %s | %s | %s. %s | %s | %s | %s |' % (st['id'], st['kind'] if scored else 'reference', ds[0]['contract'].replace('S', '♠'), lay_txt, cell('gen6', st, scored), cell('gen7', st, scored), pc))
w('')
w('On the six trap sets (A6, A6m, A4, B6, B6m, S6) Gen 6 passed %d of %d set-seeds and Gen 7 standard %d of %d. Both '
  'passed the control C1 (frozen suit: double dummy itself needs the exit) and L6 every time.' % (g6[0], g6[1], g7[0], g7[1]))
w('')
w('- Gen 6 led diamonds itself in all 72 trap-set runs: low from dummy to the ace on A6, A6m and S6, low from hand to '
  'the king on B6 and B6m and mostly on A4. At those decisions the diamond and the sound cards were exact ties in mean '
  'tricks (A6: ♦4 12.0, ♣7 12.0), so the selector net chose.')
w('- Gen 7 standard also led diamonds itself in all 72. The first diamond lead came at tricks 5 to 11, at trick 7 or '
  'later in 64 of 72; the tree (tricks 3 to 6) was consulted at that decision in 8.')
w('- S6 is the strict case. Keeping the guess averages above 12 tricks over sampled layouts (a thirteenth trick when '
  'the queen is picked up and the fourth diamond takes the club), the exit exactly 12 (Gen 6 at trick 5: ♦2 and ♥A '
  '12.69, ♣6 12.00), so a mean-tricks ranking puts the exit below the rest and the tie-break never sees it.')
w('')
for st in sets:
    w('**%s. %s.** %s Sound line: %s' % (st['id'], st['title'], st['theme'], st['sound_line']))
    w('')
w('## 5. Single-dummy sure tricks (the pooled-defender search)')
w('')
w('The tricks declarer can guarantee against every split of the unseen cards are the value of a perfect-information '
  'game: the defenders\' cards form one pool, and who holds a card is settled only when it is played, subject to hand '
  'sizes, show-outs and any cards pinned to one defender. `sure.py` searches that game. Nothing is sampled. Pinning '
  'cards or voids gives the guarantee under that much knowledge ("1.x dummy"); pinning everything is double dummy.')
w('')
w('Guaranteed total tricks by card at positions from the sets (Python prototype, no layouts sampled):')
w('')
w('| Set | Cards left | Pinned | Guaranteed total | Time |')
w('| --- | --- | --- | --- | --- |')
pos = load('sure_pos_done.txt', 'sure_pos_b.txt')
for r in sorted(pos, key=lambda r: (r['set'], -r['left'], r['pinned'])):
    inv = collections.OrderedDict()
    for card_, n in r['guaranteed'].items():
        inv.setdefault(n, []).append(card_)
    txt = '; '.join('%s → %d' % (' '.join(cs(x) for x in v), k) for k, v in sorted(inv.items(), reverse=True))
    w('| %s, %s | %d | %s | %s | %.0f s |' % (r['set'], r['note'], r['left'], r['pinned'] or 'nothing', txt, r['seconds']))
w('')
w('- A6 and S6: the cards of the sound line guarantee the contract and every diamond card one trick fewer. Double '
  'dummy rates them equal (A6) or the diamond cards higher (S6, on mean tricks).')
if any(r['set'] == 'B6' for r in pos):
    w('- B6: with nothing pinned every card guarantees only 11, because the defender with the master trump might be '
      'short in a side suit and ruff in. The plain sure-trick number separates nothing there. With three of that '
      'defender\'s side cards pinned it gives the same answer as the certification table, including which top '
      'diamond is safe to cash. That is the conditional form ("12 tricks whenever West follows to the hearts and '
      'clubs"), and the conditions then need weights.')
w('')
sr = load('sure_runs.jsonl')
if sr:
    w('The rule "a card that guarantees the contract beats one that does not" (`surebot.py`, nothing pinned, applied '
      'from 8 cards left) on top of Gen 6, one seed per layout:')
    w('')
    w('| Layout | Gen 6 alone | Gen 6 + rule | Cards the rule changed |')
    w('| --- | --- | --- | --- |')
    g6made = collections.Counter()
    for r in fin['gen6']:
        g6made[(r['deal'], r['made'])] += 1
    for r in sorted(sr, key=lambda r: r['deal']):
        ov = ', '.join('trick %d %s→%s' % (t, cs(x), cs(y)) for t, x, y in r['overrides']) or 'none'
        if r.get('too_big'):
            ov += ' (%d decisions over the node cap)' % r['too_big']
        w('| %s | %d/%d | %s, %d tricks | %s |' % (r['deal'], g6made[(r['deal'], True)], g6made[(r['deal'], True)] + g6made[(r['deal'], False)],
                                                 'made' if r['made'] else 'down', r['tricks'], ov))
    w('')
    w('On A6-QW the rule kept Gen 6 from the fifth round of trumps and made it cash the clubs and exit; the first '
      'diamond was then led by East at trick 10. On S6 Gen 6 leads the diamond at trick 5 with 9 cards left, before the '
      'rule applies in this prototype (8 cards, for speed), so nothing changed. A6-QE and S6-QE were not run with the '
      'corrected search: the first attempt died (two searches in parallel, probably out of memory) and the rerun was '
      'stopped. The rule has therefore not yet been shown to pass a whole set.')
    w('')
w('Speed. The prototype searches 24 to 65 thousand nodes a second and keys its table on exact cards. The repo\'s DDS '
  'build on the same machine ran a full 13-card solve of A6 at 2.6 million nodes a second (556 thousand nodes, 0.21 s). '
  'A C++ version with a rank-relative table, bounds and move ordering is in `sure.cpp`; its timings are in `SEARCH.md`. Known inefficiencies of the prototype: no rank-relative transposition '
  'table, a yes/no search per trick target instead of stored bounds, no sure-winner bounds, no use of the symmetry '
  'between the two defenders when nothing distinguishes them, a fresh table for every decision, and it is asked about '
  'every legal card rather than only the cards tied under double dummy.')
w('')
lg = load('lg_a.txt', 'lg_b.txt')
if lg:
    parts = []
    for r in lg:
        a, b = r['lookup_4_card'], r['lookup_5_card']
        parts.append('from %d cards left (%s) %s nodes become %s with a 4-card table (%s above it plus %s distinct table positions, %.0f×) '
                     'and %s with a 5-card table (%.0f×)' % (r['cards_left'], r['name'].split('_')[0], format(r['nodes'], ','), format(a['work_with_table'], ','),
                     format(a['nodes_above'], ','), format(a['distinct_frontier_positions'], ','), a['ratio'], format(b['work_with_table'], ','), b['ratio']))
    w('A lookup of small endings (`lookup_gain.py`, counting nodes in the prototype, a perfect table assumed): ' + '; '.join(parts) +
      '. These are node counts in an unoptimized search. A search with a rank-relative table would already repeat less '
      'near the bottom, so the gain on top of that is unmeasured, and a probe is not free.')
    w('')
w('Checks on `sure.py`. It agrees with `exact.py` run over every layout on 300 random 3-card and 60 random 4-card '
  'endings drawn from short suits so that touching cards are common (0 mismatches), and its touching-card reduction '
  'agrees with the unreduced search on 1,500 4-card and 300 5-card endings. A first version pruned a defender\'s '
  'touching cards to the lowest one before his partner had played to the trick. That is unsound in a pooled game '
  '(the eight leaves partner only higher cards of the run, the queen only lower ones, which decides who is on lead) '
  'and it made the rule accept a diamond lead on S6-QE. On 9 endings where that pruning changed the answer, the '
  'corrected unreduced search matched `exact.py` on all 9; the two-ended reduction now used was then checked against '
  'the unreduced search as above. Random endings exercise this case rarely (1 in 1,500), so the '
  'checks are thinner there than the counts suggest.')
w('')
w('Sizes, by my count (arrangements of the remaining cards as North / South / unseen, cut into suits, divided by suit '
  'symmetry, per side on lead): 3-card endings about 3.5×10⁵ at notrump and 1.4×10⁶ with a trump suit; 4-card 3.6×10⁷ and '
  '1.5×10⁸; 5-card 3.4×10⁹ and 1.4×10¹⁰, before show-out and pinned-card variants. Three and four cards tabulate '
  'easily. Five is large as a full table; solving on demand and caching by rank-relative position avoids it, and the '
  'search is not limited to five cards. Python timings above are for 7 and 8 cards.')
w('')
w('## 6. Limits')
w('')
w('- The exact tables cover only the layouts in each set (two), from the stated position (after 0 to 3 tricks). '
  '"True 1.00" means one line makes in both layouts, not in every layout a sampler would draw.')
w('- Gen 6 and Gen 7 are local builds from the repo recipe (hand-fit scorer for layouts at every trick, lead net not '
  'loaded), not the frozen arena actors. Six seeds per layout; one seed, and two layouts only, for the rule runs.')
w('- The auctions are hand-written, not produced by the bidder, so the scorer may be off its training distribution.')
w('- The oracle defender is double-dummy optimal with tie-break rules. It is not proven to be the strongest defence '
  'against each declarer.')
w('- The sure-trick search at 7 and 8 cards has no independent check beyond agreeing with the exact tables\' ordering '
  '(see the checks in section 5) and with the C++ version on the same positions (`SEARCH.md`).')
w('- S6: the claim that the exit is also better on true expected tricks rests on a hand calculation for one guessing '
  'line (about 11.8 against 12), not on a solver.')
w('- Dropped after certification: a nine-card-fit set (no line wins all four layouts: after the ruff and discard the '
  'guess remains) and a count-the-hand set (the low diamond lead itself exposed a void). Information gained before a '
  'guess is therefore not covered by a scored set.')
w('')
w('## References')
w('')
w('- Frank and Basin, "Search in games with incomplete information: a case study using bridge card play", Artificial '
  'Intelligence 100 (1998): strategy fusion and non-locality.')
w('- Cazenave and Ventos, "The αμ search algorithm for the game of Bridge", arXiv 1911.07960: Pareto fronts over '
  'layouts, defenders with perfect information. `exact.py` is that idea run to the end of the hand on a few layouts.')
open('README.md', 'w').write('\n'.join(out) + '\n')
print('README.md', len(out), 'lines')
