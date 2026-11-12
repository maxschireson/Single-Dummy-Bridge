"""Assemble SEARCH.md (the C++ sure-trick search above an ending table) from the result files."""
import json, os, re

RES = 'results' if os.path.isdir('results') else '.'
rp = lambda n: os.path.join(RES, n)
ROW = re.compile(r'^(\w+?)_(\d+)\s+(.*?)\s+([\d.]+) ms\s+nodes\s+(\d+)\s+probes\s+(\d+)')


def sections(*files):
    out, cur = {}, None
    for fn in files:
        for l in open(rp(fn)):
            if l.startswith('## '):
                cur = out.setdefault(l[3:].strip(), {})
            else:
                m = ROW.match(l)
                if m and cur is not None:
                    cur.setdefault((m.group(3)), {})[(m.group(1), int(m.group(2)))] = (float(m.group(4)), int(m.group(5)), int(m.group(6)))
    return out


def only(sec):
    assert len(sec) == 1, sec.keys()
    return next(iter(sec.values()))


def stats(fn):
    """--stats output by position: first-move counts at lead nodes, and lead nodes with / without a table read below."""
    out, cur = {}, None
    for l in open(rp(fn)):
        if l.startswith('== '):
            cur = out.setdefault(l[3:].strip(), {'lead': {}, 'noread': {}})
            continue
        m = re.match(r'\s+(declarer|defender) on lead\s*: settled by move 1: (\d+), 2: (\d+), 3: (\d+), 4: (\d+), 5: (\d+), later: (\d+); every move tried: (\d+)', l)
        if m:
            v = [int(x) for x in m.groups()[1:]]
            cur['lead'][m.group(1)] = (v[0], sum(v[:6]))
        m = re.match(r'\s+lead nodes searched with (\d+) cards left: (\d+) with no table read below, (\d+) with some', l)
        if m:
            cur['noread'][int(m.group(1))] = (int(m.group(2)), int(m.group(3)))
    return out


S = sections('cpp_results_678.txt', 'cpp_results_911.txt')
ct4 = only(S['contract-target, 4-card table (warm, real 2.5 GB array behind probes)'])
all4 = only(S['all card values, 4-card table'])
all0 = only(S['all card values, no table'])
ct0 = only(S['contract-target, no table'])
ct5 = only(S['contract-target, 5-card table (simulated)'])
ct4b = only(S['contract-target, 4-card table, 9-11 cards'])
ct0b = only(S['contract-target, no table, 9-10 cards'])
sizes = {r['cards']: r for r in (json.loads(l) for l in open(rp('table_sizes.txt')))}
valid = [l.strip() for l in open(rp('cpp_validation3.txt')) if l.strip()]
builds = [l.strip() for l in open(rp('cpp_builds_check.txt')) if l.strip()]
split = [json.loads(l) for l in open(rp('cpp_split.jsonl'))]
szs = [json.loads(l) for l in open(rp('cpp_split_sizes.jsonl'))]
build = [json.loads(l) for l in open(rp('cpp_build_cost.txt'))]
exact = {int(m.group(1)): int(m.group(2)) for m in (re.search(r'k=(\d+):.*entries (\d+)', l) for l in open(rp('endtable_counts.txt'))) if m}
poschk = [l.strip() for l in open(rp('cpp_positions_check.txt')) if l.strip()]
st, st0 = stats('cpp_stats.txt'), stats('cpp_stats_nokiller.txt')
ABL = re.compile(r'^(.*?)\s+bench nodes\s+(\d+) lookups\s+(\d+) \| 7-card nodes\s+(\d+) lookups\s+(\d+) \| 8-card nodes\s+(\d+) lookups\s+(\d+) \| results (\w+)')
abl = {}
for l in open(rp('cpp_ablation2.txt')):
    m = ABL.match(l)
    if m:
        abl[m.group(1).strip()] = [int(x) for x in m.groups()[1:7]] + [m.group(8)]

ms = lambda v: ('%.1f' if v < 10 else '%.0f') % v
pos = lambda k: '%s, %s cards' % tuple(k.split('_'))
pct = lambda v: '%.0f to %.0f percent' % (100 * min(v), 100 * max(v))
more = lambda a, b: '%.0f to %.0f percent' % tuple(sorted((100 * (a[2] / b[2] - 1), 100 * (a[4] / b[4] - 1))))
out = []
w = out.append

w('# Sure-trick search in C++ above a resident ending table')
w('')
w('`sure.cpp` is the pooled-defender game of README section 5 (what North-South can guarantee against every split of the '
  'unseen cards, given hand sizes and show-outs), written for speed and checked against `sure.py`. One thread. '
  'All timings are from a shared 2-core x86 VM, best of 3 runs unless stated; node and lookup counts are deterministic.')
w('')
w('## Search')
w('')
w('- Yes/no question per search: can North-South guarantee `need` more tricks. `--need N` asks it once per legal card '
  '("does this card guarantee the contract"); without it every card gets its exact value.')
w('- Transposition table at trick boundaries. Key: who holds each remaining card of each suit in rank order (North, South, '
  'unseen), show-outs, leader, trump. Stores lower and upper bounds and the best card. The value depends only on the key, '
  'so entries stay valid across decisions and deals and the table never needs clearing.')
w('- At a trick boundary with K cards left (`--front K`) the search reads the ending table instead of searching. The '
  'stand-in table key is the same information made canonical under suit permutation and the half-turn of the table.')
w('- Bounds tried before a table read and before a search: sure winners of the hand on lead; quick tricks using both '
  'declaring hands; top trumps for either side whoever leads.')
w('- Touching cards: declarer plays one card per run. A defender plays one per run when partner has already played, when '
  'partner is known void in the suit, or when the card is a plain discard; otherwise both ends of the run (lowest only is '
  'unsound, see README section 5).')
w('- Move order: stored best card first, then the two leads that last settled a node for this seat at this depth, then '
  'winners and long suits on lead, cheapest winner or lowest when following.')
w('')
w('## The table is simulated')
w('')
w('No table has been built (`TABLE_BUILD.md` is the specification). The stand-in is a hash map filled on first use by the '
  'same search run to the end of the hand. With `--warm` the map is filled in untimed passes and the timed pass starts from '
  'an empty transposition table. With `--cells 2.5` the timed pass reads each value from a real 2.5 GB array at a hashed '
  'slot, its cache lines flushed first, and does not touch the hash map: one dependent memory read per lookup, as with a '
  'built table. Not in the figures: the index function a real table needs (position to slot). The stand-in key and hash '
  'take its place; the real cost is unknown.')
w('')
w('## Checks')
w('')
w('The current build against `sure.py` on random endings dense in touching cards with random show-outs (`check_cpp.py`):')
w('')
for l in valid:
    w('- ' + re.sub(r' \(C\+\+.*?\)', '', l).replace("args []", 'default flags').replace("args ['", 'flags `').replace("', '", ' ').replace("']", '`'))
w('')
w('Against the build before the second round of changes, on positions too large for the Python reference (`check_cpp_builds.py`):')
w('')
for l in builds:
    w('- ' + l)
w('')
w('Against the Python results already reported for the test-set positions (`check_cpp_positions.py`):')
w('')
for l in poschk:
    w('- ' + l)
w('')
w('## Timings: 6, 7 and 8 cards left')
w('')
w('Positions are the test-set deals after the first tricks of the sound line. Milliseconds of search. The table columns read a cold 2.5 GB array (`--cells 2.5`).')
w('')
w('| Position | Contract, 4-card table | All cards, 4-card table | Contract, no table | All cards, no table | Contract, 5-card table |')
w('| --- | --- | --- | --- | --- | --- |')
for k in sorted(ct4, key=lambda k: (k[1], k[0])):
    w('| %s, %d cards | %s | %s | %s | %s | %s |' % (k[0], k[1], ms(ct4[k][0]), ms(all4[k][0]), ms(ct0[k][0]), ms(all0[k][0]), ms(ct5[k][0]) if k in ct5 else ''))
w('')
w('Nodes above the table and table reads, contract question with the 4-card table: ' +
  '; '.join('%s %d cards %s nodes, %s reads' % (k[0], k[1], format(ct4[k][1], ','), format(ct4[k][2], ',')) for k in sorted(ct4, key=lambda k: (k[1], k[0]))) + '.')
w('')
w('## Timings: 9 to 11 cards left')
w('')
w('Contract question. Milliseconds of search. Best of 2 with the table, single run without.')
w('')
w('| Position | 4-card table | No table | Nodes above table | Table reads |')
w('| --- | --- | --- | --- | --- |')
for k in sorted(ct4b, key=lambda k: (k[1], k[0])):
    w('| %s, %d cards | %s | %s | %s | %s |' % (k[0], k[1], ms(ct4b[k][0]), ms(ct0b[k][0]) if k in ct0b else 'not run', format(ct4b[k][1], ','), format(ct4b[k][2], ',')))
w('')
r8 = [ct0[k][0] / ct4[k][0] for k in ct4 if k[1] == 8]
r5 = [ct4[k][0] / ct5[k][0] for k in ct5 if k[1] == 8]
r9 = [ct0b[k][0] / ct4b[k][0] for k in ct0b if k in ct4b]
w('What the table buys at 8 cards: the 4-card table makes the contract question %.1f to %.1f times faster than no table, '
  'and a 5-card table (simulated the same way) a further %.1f to %.1f times. At 9 and 10 cards the 4-card table gives %.1f to %.1f times.'
  % (min(r8), max(r8), min(r5), max(r5), min(r9), max(r9)))
w('')
w('## Second round: what was taken from DDS')
w('')
w('Before is the build of commit `0fe1283` (first push of this directory). Contract question, values read from a cold 2.5 GB array, 8 interleaved rounds, minimum, milliseconds.')
w('')
w('| Position | Before | Now | Speed-up | Nodes before | Nodes now | Table reads before | Table reads now |')
w('| --- | --- | --- | --- | --- | --- | --- | --- |')
sp = []
for r in split:
    b, n = r['before']['min'], r['cold4k']['min']
    sp.append(b / n)
    w('| %s | %s | %s | %.1f× | %s | %s | %s | %s |' % (pos(r['pos']), ms(b), ms(n), b / n, format(r['nodes']['before'], ','), format(r['nodes']['cold4k'], ','),
                                                    format(r['probes']['before'], ','), format(r['probes']['cold4k'], ',')))
w('')
d, k0, nr, nt, nb, no = abl['(default)'], abl['--nokiller'], abl['--norun --norunfront'], abl['--notrumpbounds'], abl['--nobounds'], abl['--noorder']
w('The search is %.1f to %.1f times faster on these positions. What was adopted, each with DDS\'s counterpart:' % (min(sp), max(sp)))
w('')
w('- **Lead memory** (DDS keeps a best move per depth). The two leads that last settled a node for the same seat with the same number of cards left are tried right after the transposition table\'s move. '
  'Without it the benchmark positions take %.2f times the nodes, random positions %s more.'
  % (k0[0] / d[0], more(k0, d)))
lead = lambda s, k, side: '%.0f' % (100 * s[k]['lead'][side][0] / s[k]['lead'][side][1])
w('  Among declarer\'s lead nodes that some lead settles, the first lead tried is that lead in %s percent of cases at A6 with 9 cards and %s percent at S6 with 9 cards (%s and %s without the memory); for a defender on lead %s and %s percent (%s and %s without).'
  % (lead(st, 'A6_9', 'declarer'), lead(st, 'S6_9', 'declarer'), lead(st0, 'A6_9', 'declarer'), lead(st0, 'S6_9', 'declarer'),
     lead(st, 'A6_9', 'defender'), lead(st, 'S6_9', 'defender'), lead(st0, 'A6_9', 'defender'), lead(st0, 'S6_9', 'defender')))
w('- **Quick tricks with both hands** (DDS\'s QuickTricks, simplified). With North or South on lead and no ruff possible: cash a card above every unseen card of its suit, or lead low to such a card in partner\'s hand, and count until the certainty runs out. '
  'Used as a lower bound at lead nodes and before table reads. Without it the benchmark positions take %.0f percent more nodes and %.1f times the table reads; random positions %s more nodes.'
  % (100 * (nr[0] / d[0] - 1), nr[1] / d[1], more(nr, d)))
w('- **Later tricks for trumps** (DDS\'s LaterTricks, trumps only). A trump above every trump of the other side wins the trick it is played on, whoever leads; North-South get at least the larger of their two holdings of such trumps, the defenders as many as one of them can be given. '
  'No effect on the benchmark positions, where trumps are drawn (%.1f percent); without it random positions take %s more nodes.'
  % (100 * (nt[0] / d[0] - 1), more(nt, d)))
w('- **Keys from relative ranks without a loop** (DDS uses lookup tables by suit holding). Each suit\'s part of the key comes from two bit-extract and two bit-deposit instructions; the loop version remains for processors without them. With picking the best remaining move instead of sorting all of them, this took 14 to 25 percent off the time when it went in.')
w('- **One transposition lookup on the way into a node and a pointer check on the way out**, instead of three lookups with three key computations; the trick\'s current winner computed once per node; pool counts per suit once per node in the defenders\' move generator. Together about 10 percent of the tree time when they went in.')
w('- **Transposition table of 2^18 entries** instead of 2^20: same nodes up to 10 cards on these positions and 3 to 9 percent less time at 10 cards (it stays in cache). Not compared at 11 cards or more.')
w('')
w('Tried and dropped:')
w('')
w('- The same memory for the second, third and fourth seats, and a table of replies to the previous card: each searched more nodes on every set (15 and 68 percent more on the benchmark positions, about 60 percent more on random 8-card positions).')
w('- Low cards first for a defender\'s non-winning leads: within 1 percent either way.')
w('- "The side on lead cannot win the coming trick" as a bound for both sides: correct, under half a percent fewer nodes.')
w('- A global history count (first round): more nodes.')
w('')
nr9 = st['A6_9']['noread']
up = [l for l in nr9 if l > 5]
w('Not carried over: DDS\'s winning ranks, where a transposition entry records only the cards whose rank mattered, so that one entry '
  'covers every position that differs in lower cards. A table read depends on every card of the ending and reports nothing about '
  'which ranks mattered, so a node with a table read below it cannot be generalized this way. Measured at A6 with 9 cards: of the lead nodes searched, '
  '%s of %s at 6 to 8 cards left and %s of %s at 5 cards left had no table read below them. Those are the nodes the technique could reach; it was not implemented. '
  'It would become available everywhere if the table stored, with each value, how many top cards of each suit the value depends on.'
  % tuple(format(x, ',') for x in (sum(nr9[l][0] for l in up), sum(sum(nr9[l]) for l in up), nr9[5][0], sum(nr9[5]))))
w('')
w('## What each part contributes')
w('')
w('Node and table-read totals with one part switched off (`ordtest.py`). Benchmark: the 15 test-set positions at 7 to 10 cards, contract question. Random: 300 7-card and 120 8-card positions drawn uniformly over card patterns, position value. Answers were the same in every row.')
w('')
w('| Build | Benchmark nodes | Benchmark reads | Random 7-card nodes | Random 8-card nodes |')
w('| --- | --- | --- | --- | --- |')
for name, label in (('(default)', 'Current'), ('--nokiller', 'No lead memory'), ('--norun --norunfront', 'No two-hand quick tricks'), ('--notrumpbounds', 'No trump later tricks'),
                    ('--nobounds', 'No bounds at all'), ('--noorder', 'No move ordering')):
    a = abl[name]
    assert a[6] == 'same'
    w('| %s | %s | %s | %s | %s |' % (label, format(a[0], ','), format(a[1], ','), format(a[2], ','), format(a[4], ',')))
w('')
w('## Where the time goes: lookups against the tree above the table')
w('')
w('The same search run four ways, interleaved over 8 rounds, minimum taken (`split.py`). Contract question, 4-card table, milliseconds.')
w('')
w('- Free lookups (`--replay`): the table\'s answers are returned in recorded order, with no key computed and nothing read. What is left is the tree above the table.')
w('- In cache (`--cells 0.002 --noflush`): values read from a 2 MB table that stays in cache. Adds the key computation.')
w('- Cold (`--cells 2.5`): values read from a 2.5 GB array at a hashed slot, 4 KB pages, the touched cache lines flushed before timing. Adds the wait on memory.')
w('- Cold on 2 MB pages (`--cells 2.5 --huge`).')
w('')
w('| Position | Lookups | Free | In cache | Cold | Cold, 2 MB pages | Tree | Key | Memory |')
w('| --- | --- | --- | --- | --- | --- | --- | --- | --- |')
sh = {'tree': [], 'key': [], 'mem': [], 'ceil': [], 'huge': [], 'keyns': []}
for r in split:
    f, c, b, h = (r[n]['min'] for n in ('free', 'cache', 'cold4k', 'coldhuge'))
    pr = r['probes']['cold4k']
    sh['tree'].append(f / b); sh['key'].append((c - f) / b); sh['mem'].append((b - c) / b); sh['ceil'].append(b / f); sh['huge'].append((b - h) / b)
    sh['keyns'].append(1e6 * (c - f) / pr)
    w('| %s | %s | %s | %s | %s | %s | %.0f%% | %.0f%% | %.0f%% |' % (pos(r['pos']), format(pr, ','), ms(f), ms(c), ms(b), ms(h), 100 * f / b, 100 * (c - f) / b, 100 * (b - c) / b))
w('')
w('Tree, Key and Memory are shares of the Cold column. The tree above the table is %s of the time, the key computation %s '
  '(%.0f to %.0f ns a lookup) and the wait on memory %s. With free lookups the search would be %.1f to %.1f times faster; that is the most '
  'any work on the index or the read can gain. Before the second round the tree was 55 to 68 percent and free lookups were worth 1.5 to 1.8 times: '
  'the bounds removed most of the table reads.'
  % (pct(sh['tree']), pct(sh['key']), min(sh['keyns']), max(sh['keyns']), pct(sh['mem']), min(sh['ceil']), max(sh['ceil'])))
w('')
names = [k for k in szs[0] if k.startswith('t')]
w('Table size (cold, 4 KB pages, 5 rounds, minimum, milliseconds):')
w('')
w('| Position | ' + ' | '.join(n[1:] + ' GB' for n in names) + ' |')
w('| --- | ' + ' | '.join('---' for _ in names) + ' |')
for r in szs:
    w('| %s | %s |' % (pos(r['pos']), ' | '.join(ms(r[n]['min']) for n in names)))
w('')
small = [1 - r[names[0]]['min'] / r['t2.5']['min'] for r in szs]
w('1.07 GB, 1.75 GB, 2.5 GB and 3.09 GB are within the run-to-run spread of each other (the specified table is 2.80 GB). A %s GB table is %.0f to %.0f percent faster than a 2.5 GB one. '
  '2 MB pages for the transposition table made no measurable difference to the tree part (%s).'
  % (names[0][1:], 100 * min(small), 100 * max(small), '; '.join('%s %s against %s ms' % (pos(r['pos']), ms(r['freehugett']['min']), ms(r['free']['min'])) for r in szs)))
w('')
w('Limits of this split. The key is the stand-in key (canonical suit order, then a hash); a real index swaps the hash for a ranking step and has not been '
  'written or timed. Hashed slots are the worst case for memory; a real index would put related endings near each other. The machine is an x86 VM with '
  '4 KB pages and a large shared L3; Apple silicon has 16 KB pages and different caches.')
w('')
w('## Building the 4-card table')
w('')
w('Not built. `TABLE_BUILD.md` is the build specification, for the table that holds unknown-or-exact knowledge per suit (the mixed column below; %s entries exactly). In outline:' % format(exact[4], ','))
w('')
w('- An index function, position plus knowledge state to slot. With suits sorted so that permutations share a slot the table is the size given below; without the suit symmetry it is about 9 times larger.')
w('- A builder that walks the entries in index order, solves each and packs 3 bits. Bottom-up: the 3-card table first (%s entries), then each 4-card entry is one trick of search reading the 3-card table.' % format(exact[3], ','))
w('- Compute. Per entry, measured on %s random entries with show-out knowledge (`build_cost.py`): ' % format(build[0]['entries'], ',') +
  '; '.join('%s %.1f µs (%.0f nodes, %.0f lookups)' % (b['how'], b['us_per_entry'], b['nodes_per_entry'], b['lookups_per_entry']) for b in build) +
  '. For the specified table (%s entries) that is %.0f core-hours from the 3-card table or %.0f from scratch, if an entry with shape knowledge costs the same, which is unmeasured. '
  'With the search as it was before the second round the same measurement gave 10.3 to 11.2 and 29.3 to 31.7 µs. The 3-card table here is the stand-in hash map.'
  % (format(exact[4], ','), exact[4] * build[1]['us_per_entry'] / 3.6e9, exact[4] * build[0]['us_per_entry'] / 3.6e9))
w('- Checks: entries against `pooled_ref.py`, `sure_cpp --value` and the test vectors.')
w('- At play time: map the file into memory; `sure.cpp` built with `-DENDTABLE` reads it through `endtable/endtable.h` (`--table FILE`).')
w('')
w('## Table sizes')
w('')
w('`table_size.py`, `table_size_shapes.py`. Positions: each remaining card is North\'s, South\'s or unseen, relative rank only, '
  'up to suit permutation, two leader classes, notrump and trump. Each position is then multiplied by its knowledge states.')
w('')
w('| Cards | Positions | Show-outs only | Whole shapes only | Mixed |')
w('| --- | --- | --- | --- | --- |')
for k in sorted(sizes):
    r = sizes[k]
    cell = lambda d: '×%.1f, %.1e entries, %s' % (d['mult'], d['entries'], ('%.2f GB' if d['gb'] < 10 else '%.0f GB') % d['gb'])
    w('| %d | %.2e | %s | %s | %s |' % (k, r['positions'], cell(r['voids']), cell(r['shapes']), cell(r['mixed'])))
w('')
w('- Show-outs only: each suit with unseen cards is free, or all East\'s, or all West\'s. States that imply one another are '
  'counted once (counted separately the 4-card figure is %.1e entries, %.1f GB, the number quoted earlier).' % (sizes[4]['voids_raw']['entries'], sizes[4]['voids_raw']['gb']))
w('- Whole shapes only: East\'s length in every suit is known. This answers "what is guaranteed if East is exactly this '
  'shape". It does not give the value when the shape is unknown: the minimum over shapes is only an upper bound on it, '
  'because different shapes can need different lines.')
w('- Mixed: each suit is either unknown or known exactly. Contains both of the others.')
w('- Sizes at 3 bits an entry (2 bits for 3 cards). Build time is unmeasured.')
w('- These are estimates: the knowledge multiplier was counted on ordered suits and applied to the symmetry-reduced position count, and a trump suit with no cards left is counted apart from notrump. '
  'The reference index (`endtable_ref.py`) counts the mixed table exactly: %s entries at 1 to 4 cards, %.2f GB at 4 cards, %.0f percent below the estimate above.'
  % (', '.join(format(exact[k], ',') for k in sorted(exact)), exact[4] * 3 / 8e9, 100 * (1 - exact[4] / sizes[4]['mixed']['entries'])))
w('')
w('## Not done')
w('')
w('- The table itself and its index function (specified in `TABLE_BUILD.md`).')
w('- Shape knowledge and pinned cards in the C++ search (it has hand sizes and show-outs only). `pooled_ref.py` defines the game with shape knowledge; `sure.py` has pinned cards.')
w('- Winning ranks in the transposition table (see above), read-ahead of table slots, and splitting the legal cards across threads. None is implemented. The memory wait that read-ahead would attack is now %s of the time.' % pct(sh['mem']))
w('- A richer quick-tricks bound for a defender on lead (the declaring side\'s version uses both hands; the defenders\' counts only what the leader can hold).')
w('- The rule "a card that guarantees the contract comes first" (`surebot.py`) still calls the Python search. It has not been rerun on the C++ search.')
w('- Timings cover four deals, all spade contracts, positions on the sound line only. The random positions are uniform over card patterns, not over positions that arise in play.')
w('')
w('## Run')
w('')
w('```')
w('g++ -O2 -march=native -std=c++17 -o sure_cpp sure.cpp')
w('python check_cpp.py 5 250 --front 4            # against sure.py')
w('python runpos.py A6_8,S6_8 --contract --front 4 --warm --cells 2.5')
w('python split.py A6_8,S6_8 8 "free=--replay" "cache=--cells 0.002 --noflush" "cold4k=--cells 2.5" "coldhuge=--cells 2.5 --huge"')
w('python ordtest.py "" "--nokiller" "--norun"       # node counts with parts switched off')
w('python build_cost.py 4 200000')
w('python bench_cpp.py 6,7,8 --front 4 --contract  # needs the repo (SDB_ROOT) for Board')
w('```')
w('')
w('Input to `sure_cpp`, one position per line: `trump leader hN hS pool cE cW vE vW [cards already played to the trick]`. '
  'Trump 0-3 = S, H, D, C, 4 = notrump; leader 0-3 = N, E, S, W; hands and pool as hex masks with card = 13 × suit + rank '
  '(2 = 0 ... A = 12); cE, cW the defenders\' hand sizes; vE, vW bit masks of suits shown out of. A line may start with `N<k>` to ask the contract question with target k. `csure.py` builds the line from a `sure.Sure` object.')
open('SEARCH.md', 'w').write('\n'.join(out) + '\n')
print('SEARCH.md', len(out), 'lines')
