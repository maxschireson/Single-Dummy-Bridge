"""Checks on the deal file: card counts, double-dummy result, the stated sound line against the oracle,
and the exact fused-vs-true table at a common position of each set.
Usage: verify.py fusion_deals.json [set ids] [--exact] [--out file]"""
import sys, json, time
from fusionlab import *
from scripted import Script
from exact import Exact

KEYS = ('id', 'hands', 'contract', 'declarer', 'dealer', 'vulnerability', 'auction', 'opening_lead')

def board(d):
    return Board.from_dict({k: d[k] for k in KEYS})

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    data = json.load(open(args[0]))
    only = set(args[1].split(',')) if len(args) > 1 else None
    exact = '--exact' in sys.argv
    out = {}
    dds = DDS(cache_path='')
    deals = {d['id']: d for d in data['deals']}
    for st in data['sets']:
        if only and st['id'] not in only:
            continue
        print('==', st['id'], '(%s)' % st['kind'], st['title'])
        boards, prefix = [], None
        rec = out[st['id']] = dict(deals={})
        for did in st['deals']:
            d = deals[did]
            b = board(d)
            boards.append(b)
            need = b.contract.level + 6
            dd = dd_tricks(b, dds)
            t = run(b, Script(b, st['script'], dds), avoid=d['avoid'], critical=d['critical'], dds=dds)
            plays = [c for trick in tricks_text(t['actions']) for c in trick.split()]
            print('   %-9s %-34s DD %2d  sound line vs oracle %2d  %s' % (did, d['layout'], dd, t['declarer_tricks'],
                  'ok' if dd >= need and t['declarer_tricks'] >= need else 'PROBLEM'))
            rec['deals'][did] = dict(dd=dd, sound=t['declarer_tricks'], play=tricks_text(t['actions']))
            if prefix is None:
                n = 4 * st['cert_tricks'] if st['cert_tricks'] else 1
                prefix = st['cert_prefix'].split() if st.get('cert_prefix') else [x.split(':')[1] for x in plays[:n]]
        if exact:
            t0 = time.time()
            ex = Exact.from_boards(boards, [card(c) for c in prefix], weights=[deals[i].get('weight', 1) for i in st['deals']], dds=dds)
            r = ex.root()
            names = st['deals']
            print('   exact, after', ' '.join(prefix))
            for c, v in r.items():
                print('      %s fused %.2f true %.2f  %s' % (c, v['fused'], v['true'], ' '.join(n for i, n in enumerate(names) if v['wins'] >> i & 1)))
            print('      (%d nodes, %d solves, %.0f s)' % (ex.nodes, ex.dd_calls, time.time() - t0), flush=True)
            rec['exact'] = dict(prefix=prefix, cards={c: dict(fused=v['fused'], true=v['true'],
                                wins=[n for i, n in enumerate(names) if v['wins'] >> i & 1]) for c, v in r.items()},
                                nodes=ex.nodes, solves=ex.dd_calls, seconds=round(time.time() - t0))
    for a in sys.argv:
        if a.startswith('--out='):
            json.dump(out, open(a[6:], 'w'), indent=1)

main()
