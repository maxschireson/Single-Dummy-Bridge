"""Summarise result files by bot and set. Usage: report.py fusion_deals.json res*.jsonl"""
import sys, json, collections
data = json.load(open(sys.argv[1]))
rows = [json.loads(l) for f in sys.argv[2:] for l in open(f)]
bots = []
for r in rows:
    if r['bot'] not in bots: bots.append(r['bot'])
made = collections.defaultdict(dict)
for r in rows:
    made[(r['bot'], r['deal'])][r['seed']] = r['made']
for st in data['sets']:
    print('%-4s %-9s %s' % (st['id'], st['kind'], st['title']))
    for bot in bots:
        if not all((bot, d) in made for d in st['deals']):
            continue
        seeds = set.intersection(*[set(made[(bot, d)]) for d in st['deals']])
        passed = sum(all(made[(bot, d)][s] for d in st['deals']) for s in seeds)
        cells = '  '.join('%s %d/%d' % (d.split('-')[-1], sum(made[(bot, d)].values()), len(made[(bot, d)])) for d in st['deals'])
        print('      %-12s set %2d/%-2d   %s' % (bot, passed, len(seeds), cells))
