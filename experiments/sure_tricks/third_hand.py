"""Exact fused-vs-true values at the third-hand decision after a low diamond lead in set A6."""
import json
from exact import Exact
from fusionlab import Board, card
data = json.load(open('fusion_deals.json'))
deals = {d['id']: d for d in data['deals']}
KEYS = ('id', 'hands', 'contract', 'declarer', 'dealer', 'vulnerability', 'auction', 'opening_lead')
ids = ['A6-QW', 'A6-QE']
prefix = 'HQ H4 H2 HK SA S5 S2 S3 S4 S6 SK H5 D4 D2'
ex = Exact.from_boards([Board.from_dict({k: deals[i][k] for k in KEYS}) for i in ids], [card(c) for c in prefix.split()],
                       weights=[deals[i]['weight'] for i in ids])
r = ex.root()
out = dict(prefix=prefix.split(), cards={c: dict(fused=v['fused'], true=v['true'], wins=[n for i, n in enumerate(ids) if v['wins'] >> i & 1]) for c, v in r.items()})
json.dump(out, open('cert_A6_third.json', 'w'), indent=1)
for c, v in out['cards'].items():
    print(c, 'fused %.2f true %.2f' % (v['fused'], v['true']), v['wins'])
