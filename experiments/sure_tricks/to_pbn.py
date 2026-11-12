"""fusion_deals.json -> fusion_deals.pbn (one game per deal)."""
import json, sys
data = json.load(open(sys.argv[1]))
sets = {s['id']: s for s in data['sets']}
out = []
for i, d in enumerate(data['deals'], 1):
    st = sets[d['set']]
    n, e, s, w = d['hands']
    calls = [{'PASS': 'Pass', 'X': 'X', 'XX': 'XX'}.get(c, c.replace('N', 'NT') if c[-1] == 'N' else c) for c in d['auction']]
    rows = [' '.join(calls[j:j + 4]) for j in range(0, len(calls), 4)]
    out += ['[Event "Strategy fusion test set: %s"]' % d['id'], '[Board "%d"]' % i, '[Dealer "%s"]' % d['dealer'],
            '[Vulnerable "None"]', '[Deal "N:%s %s %s %s"]' % (n, e, s, w), '[Declarer "%s"]' % d['declarer'],
            '[Contract "%s"]' % d['contract'].replace('N', 'NT') if d['contract'][-1] == 'N' else '[Contract "%s"]' % d['contract'],
            '[Auction "%s"]' % d['dealer'], *rows, '[Play "W"]', d['opening_lead'] + ' - - -', '*',
            '{%s | set %s (%s): %s | layout: %s}' % (d['id'], st['id'], st['kind'], st['title'], d['layout']), '']
open(sys.argv[2], 'w').write('\n'.join(out))
print(len(data['deals']), 'games')
