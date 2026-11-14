"""E9-25 slices (registered: 8 against 7 cards; games, slams and doubled against partscores), with e925_report.py's definitions.
usage: python3 e925_slices.py DIR   (DIR holds the four result files, unzipped)"""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'experiments' / 'e9_25'))
from pathlib import Path
import e925_report as R
d = Path(sys.argv[1])
pops = {'BEN defending': R.rows(d / 'ben_defends-8.jsonl') + R.rows(d / 'ben_defends-7.jsonl'),
        'house defending': R.rows(d / 'house_defends-8.jsonl') + R.rows(d / 'house_defends-7.jsonl')}
def kind(r):
    c = r['contract']
    lvl = int(c[0])
    if 'X' in c[1:]:
        return 'doubled'
    if lvl >= 6:
        return 'slam'
    return 'game' if r.get('game') else 'partscore'
for name, rs in pops.items():
    print(name, 'positions', len(rs), 'by kind', {k: sum(kind(r) == k for r in rs) for k in ('partscore', 'game', 'slam', 'doubled')})
    for k in ('partscore', 'game', 'slam', 'doubled'):
        sub = [r for r in rs if kind(r) == k]
        kb, nb, pb, sb = R.rate(sub, 'b'); kg, ng, pg, sg = R.rate(sub, 'g')
        print(f'  {k:9s} scorer {kb}/{nb}  Gen 9 {kg}/{ng}')
    gs = [r for r in rs if kind(r) != 'partscore']
    kb, nb, pb, sb = R.rate(gs, 'b'); kg, ng, pg, sg = R.rate(gs, 'g')
    print(f'  games, slams and doubled: scorer {kb}/{nb}  Gen 9 {kg}/{ng}')
    # effective sample sizes and how often the two weightings pick a different best card
    import statistics
    eb = [r['eff_b'] for r in rs]; eg = [r['eff_g'] for r in rs]
    diff = sum(r['shape']['b']['best'] != r['shape']['g']['best'] for r in rs)
    print(f'  median effective layouts: scorer {statistics.median(eb):.0f}, Gen 9 {statistics.median(eg):.0f}; best card differs on {diff} of {len(rs)}')
ben = pops['BEN defending']
print('BEN pooled, committed by either:', sum(R.committed(r, 'b') or R.committed(r, 'g') for r in ben))
print('contracts made at the table among BEN failures:', [ (r['contract'], r['made'], r['cards']) for r in ben if (R.committed(r,'b') and R.fails(r,'b')) or (R.committed(r,'g') and R.fails(r,'g'))])
