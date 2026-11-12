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


S = sections('cpp_results_678.txt', 'cpp_results_911.txt', 'cpp_ablation.txt', 'cpp_memcost.txt')
ct4 = only(S['contract-target, 4-card table (warm, real 2.5 GB array behind probes)'])
all4 = only(S['all card values, 4-card table'])
all0 = only(S['all card values, no table'])
ct0 = only(S['contract-target, no table'])
ct5 = only(S['contract-target, 5-card table (simulated)'])
ct4b = only(S['contract-target, 4-card table, 9-11 cards'])
ct0b = only(S['contract-target, no table, 9-10 cards'])
abl = S['ablations, contract-target, 4-card table (nodes are deterministic)']
mem = S['cost of a real memory read behind each probe (best of 5)']
sizes = {r['cards']: r for r in (json.loads(l) for l in open(rp('table_sizes.txt')))}
valid = [l.strip() for fn in ('cpp_validation.txt', 'cpp_validation2.txt') for l in open(rp(fn)) if l.strip()]
split = [json.loads(l) for l in open(rp('cpp_split.jsonl'))]
szs = [json.loads(l) for l in open(rp('cpp_split_sizes.jsonl'))]
build = [json.loads(l) for l in open(rp('cpp_build_cost.txt'))]
exact = {int(m.group(1)): int(m.group(2)) for m in (re.search(r'k=(\d+):.*entries (\d+)', l) for l in open(rp('endtable_counts.txt'))) if m}
poschk = [l.strip() for l in open(rp('cpp_positions_check.txt')) if l.strip()]

ms = lambda v: ('%.1f' if v < 10 else '%.0f') % v
out = []
w = out.append

w('# Sure-trick search in C++ above a resident ending table')
w('')
w('`sure.cpp` is the pooled-defender game of README section 5 (what North-South can guarantee against every split of the '
  'unseen cards, given hand sizes and show-outs), written for speed and checked against `sure.py`. One thread. '
  'All timings are from a shared 2-core VM, best of 3 runs unless stated; node and probe counts are deterministic.')
w('')
w('## Search')
w('')
w('- Yes/no question per search: can North-South guarantee `need` more tricks. `--need N` asks it once per legal card '
  '("does this card guarantee the contract"); without it every card gets its exact value.')
w('- Transposition table at trick boundaries. Key: who holds each remaining card of each suit in rank order (North, South, '
  'unseen), show-outs, leader, trump. Stores lower and upper bounds and the best card. The value depends only on the key, '
  'so entries stay valid across decisions and deals and the table never needs clearing.')
w('- At a trick boundary with K cards left (`--front K`) the search reads the ending table instead of searching. The '
  'table key is the same information made canonical under suit permutation and the half-turn of the table.')
w('- Sure-winner bounds for both sides, tried before a table read and before a search.')
w('- Touching cards: declarer plays one card per run. A defender plays one per run when partner has already played, when '
  'partner is known void in the suit, or when the card is a plain discard; otherwise both ends of the run (lowest only is '
  'unsound, see README section 5).')
w('- Move order: stored best card first, then winners and long suits on lead, cheapest winner or lowest when following.')
w('')
w('## The table is simulated')
w('')
w('No table has been built. The stand-in is a hash map filled on first use by the same search run to the end of the hand. '
  'With `--warm` the map is filled in an untimed first pass and the timed pass starts from an empty transposition table. '
  'With `--mem 2.5` every table read also reads one byte of a real 2.5 GB array at a hashed address, with the CPU caches '
  'flushed before the timed pass, so the cost of reaching into a table of that size is in the figures. Not in the '
  'figures: the index function a real table needs (position to slot). The hash-map lookup stands in for it; its real cost is unknown. '
  'For the time split further down the values themselves are read from an array (`--cells`), with no hash map in the timed pass.')
w('')
w('## Checks')
w('')
w('Against `sure.py` on random endings dense in touching cards with random show-outs (`check_cpp.py`):')
w('')
for l in valid:
    w('- ' + re.sub(r' \(C\+\+.*\)$', '', l).replace("args []", 'default flags').replace("args ['", 'flags `').replace("', '", ' ').replace("']", '`'))
w('')
w('Against the Python results already reported for the test-set positions (`check_cpp_positions.py`):')
w('')
for l in poschk:
    w('- ' + l)
w('')
w('## Timings: 6, 7 and 8 cards left')
w('')
w('Positions are the test-set deals after the first tricks of the sound line. Milliseconds of search.')
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
w('## What moved the node count')
w('')
base = abl['--front 4 --warm contract']
names = [('--front 4 --warm --noorder contract', 'no move ordering'), ('--front 4 --warm --nobounds contract', 'no sure-winner bounds'),
         ('--front 4 --warm --hist contract', 'history heuristic added')]
w('Contract question, 4-card table. Nodes above the table.')
w('')
w('| Position | Final | ' + ' | '.join(n for _, n in names) + ' |')
w('| --- | --- | ' + ' | '.join('---' for _ in names) + ' |')
for k in sorted(base, key=lambda k: (k[1], k[0])):
    w('| %s, %d cards | %s | %s |' % (k[0], k[1], format(base[k][1], ','), ' | '.join(format(abl[a][k][1], ',') for a, _ in names)))
w('')
w('Move ordering is the main factor. The history heuristic made things worse and is off (`--hist` turns it on). One card '
  'per run on plain discards cut nodes by 9 to 19 percent on these four positions (44,258 to 35,816 on A6 at 8 cards). '
  'Trying the bounds before the table read cut reads by 10 to 30 percent on the four positions measured. '
  'Transposition-table size from 2^16 to 2^22 entries made no measurable difference at 8 and 9 cards (three positions); the default is 2^20.')
w('')
kk = sorted(k for k in mem['--front 4 --warm contract'])
w('Reaching into real memory: ' + '; '.join('%s %d cards %s ms without the array read, %s ms with it' % (k[0], k[1], ms(mem['--front 4 --warm contract'][k][0]),
  ms(mem['--front 4 --warm --mem 2.5 contract'][k][0])) for k in kk) + '. Standard 4 KB pages; huge pages not tried. Hashed addresses are the worst case for locality.')
w('')
w('Where the nodes are: 73 to 80 percent of the nodes above the table are in the last trick before it (5 cards left) on the '
  'three positions counted (A6 at 8 and 9 cards, S6 at 9); `--stats` prints the count by depth. Keeping the transposition table from one decision to the next in '
  'the same deal cut the next decision\'s nodes by 20 to 30 percent on the three deals tried (all-card values, 8 then 7 cards).')
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
    nm = r['pos'].split('_')
    sh['tree'].append(f / b); sh['key'].append((c - f) / b); sh['mem'].append((b - c) / b); sh['ceil'].append(b / f); sh['huge'].append((b - h) / b)
    sh['keyns'].append(1e6 * (c - f) / r['probes'])
    w('| %s, %s cards | %s | %s | %s | %s | %s | %.0f%% | %.0f%% | %.0f%% |' % (nm[0], nm[1], format(r['probes'], ','), ms(f), ms(c), ms(b), ms(h), 100 * f / b, 100 * (c - f) / b, 100 * (b - c) / b))
w('')
pct = lambda v: '%.0f to %.0f percent' % (100 * min(v), 100 * max(v))
w('Tree, Key and Memory are shares of the Cold column. The tree above the table is %s of the time, the key computation %s '
  '(%.0f to %.0f ns a lookup) and the wait on memory %s. With free lookups the search would be %.1f to %.1f times faster; that is the most '
  'any work on the index or the read can gain. 2 MB pages for the table save %s of the total.'
  % (pct(sh['tree']), pct(sh['key']), min(sh['keyns']), max(sh['keyns']), pct(sh['mem']), min(sh['ceil']), max(sh['ceil']), pct(sh['huge'])))
w('')
names = [k for k in szs[0] if k.startswith('t')]
w('Table size (cold, 4 KB pages, 6 rounds, minimum, milliseconds):')
w('')
w('| Position | ' + ' | '.join(n[1:] + ' GB' for n in names) + ' |')
w('| --- | ' + ' | '.join('---' for _ in names) + ' |')
for r in szs:
    nm = r['pos'].split('_')
    w('| %s, %s cards | %s |' % (nm[0], nm[1], ' | '.join(ms(r[n]['min']) for n in names)))
w('')
small = [1 - r[names[0]]['min'] / r['t2.5']['min'] for r in szs]
w('1.07 GB (whole shapes), 1.75 GB (show-outs) and 3.09 GB (mixed) are within the run-to-run spread of each other. A %s GB table is %s faster than a 2.5 GB one. '
  '2 MB pages for the transposition table made no measurable difference to the tree part (%s).'
  % (names[0][1:], pct(small), '; '.join('%s %s cards %s against %s ms' % (*r['pos'].split('_'), ms(r['freehugett']['min']), ms(r['free']['min'])) for r in szs)))
w('')
w('Limits of this split. The key is the stand-in key (canonical suit order, then a hash); a real index swaps the hash for a ranking step and has not been '
  'written or timed. Hashed slots are the worst case for memory; a real index would put related endings near each other. The machine is an x86 VM with '
  '4 KB pages and a large shared L3; Apple silicon has 16 KB pages and different caches.')
w('')
w('## Building the 4-card table')
w('')
e4 = sizes[4]
w('Not built. `TABLE_BUILD.md` is the build specification, for the table that holds unknown-or-exact knowledge per suit (the mixed column below; %s entries exactly). In outline:' % format(exact[4], ','))
w('')
w('- An index function, position plus knowledge state to slot. With suits sorted so that permutations share a slot the table is the size given below; without the suit symmetry it is about 9 times larger.')
w('- A builder that walks the entries in index order, solves each and packs 3 bits. Bottom-up: the 3-card table first (%s entries), then each 4-card entry is one trick of search reading the 3-card table.' % format(exact[3], ','))
w('- Compute. Per entry, measured on %s random entries (`build_cost.py`): ' % format(build[0]['entries'], ',') +
  '; '.join('%s %.1f µs (%.0f nodes, %.0f lookups)' % (b['how'], b['us_per_entry'], b['nodes_per_entry'], b['lookups_per_entry']) for b in build) +
  '. For the specified table (%s entries) that is %.0f core-hours from the 3-card table or %.0f from scratch, if an entry with shape knowledge costs the same, which is unmeasured. '
  'An earlier run of the same measurement gave 10.3 and 29.3 µs. The 3-card table here is the stand-in hash map.'
  % (format(exact[4], ','), exact[4] * build[1]['us_per_entry'] / 3.6e9, exact[4] * build[0]['us_per_entry'] / 3.6e9))
w('- Checks: a sample of entries against `sure.py` and against from-scratch solves.')
w('- At play time: map the file into memory and replace the stand-in lookup with index plus read.')
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
w('- The table itself and its index function. The batch build has not been written or timed.')
w('- Shape constraints and pinned cards in the C++ solver (it has hand sizes and show-outs only). `sure.py` has pinned cards but no shape constraint.')
w('- Matching transposition entries on the cards that mattered rather than all cards (what DDS does), and splitting the legal cards across threads. Neither is implemented; their gain here is unknown.')
w('- The rule "a card that guarantees the contract comes first" (`surebot.py`) still calls the Python search. It has not been rerun on the C++ search.')
w('- Timings cover four deals, all spade contracts, positions on the sound line only.')
w('')
w('## Run')
w('')
w('```')
w('g++ -O2 -march=native -std=c++17 -o sure_cpp sure.cpp')
w('python check_cpp.py 5 250 --front 4            # against sure.py')
w('python runpos.py A6_8,S6_8 --contract --front 4 --warm --mem 2.5')
w('python split.py A6_8,S6_8 8 "free=--replay" "cache=--cells 0.002 --noflush" "cold4k=--cells 2.5" "coldhuge=--cells 2.5 --huge"')
w('python build_cost.py 4 200000')
w('python bench_cpp.py 6,7,8 --front 4 --contract  # needs the repo (SDB_ROOT) for Board')
w('```')
w('')
w('Input to `sure_cpp`, one position per line: `trump leader hN hS pool cE cW vE vW [cards already played to the trick]`. '
  'Trump 0-3 = S, H, D, C, 4 = notrump; leader 0-3 = N, E, S, W; hands and pool as hex masks with card = 13 × suit + rank '
  '(2 = 0 ... A = 12); cE, cW the defenders\' hand sizes; vE, vW bit masks of suits shown out of. `csure.py` builds the line from a `sure.Sure` object.')
open('SEARCH.md', 'w').write('\n'.join(out) + '\n')
print('SEARCH.md', len(out), 'lines')
