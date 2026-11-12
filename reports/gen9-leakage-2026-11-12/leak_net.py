"""The defenders' plays: what the two defenders gain from reading each other's, against what declarer gains from reading them.
p41's pools (530 house tables, v4). Tricks a board (the four seats of one table), deal as the unit."""
import glob, sys
import numpy as np
sys.path.insert(0, '/home/claude/single-dummy-bridge'); sys.path.insert(0, '/home/claude/bench')
from gen8_reading_bench import load, score, mean_se
out = dict(fam=[], decl=[], none=[], lead=[], partner=[], lead_partner=[], opp=[], lead_opp=[], all=[])
tables = 0
for part in sorted(glob.glob('/home/claude/pools/pools-*-*.npz')):
    rows, tabs, nets = load(part)
    tables += len(tabs)
    for r in rows:
        fit = np.asarray(r['fit']['v4'], np.float64)
        s = lambda parts: score(r, fit, 1., parts=parts)[1]
        out['fam'].append(str(r['family'])); out['decl'].append(bool(r['declaring']))
        out['none'].append(score(r, np.zeros_like(fit), 0.)[1])
        out['lead'].append(s((1., 0., 0.))); out['partner'].append(s((0., 1., 0.))); out['lead_partner'].append(s((1., 1., 0.)))
        out['opp'].append(s((0., 0., 1.))); out['lead_opp'].append(s((1., 0., 1.))); out['all'].append(s((1., 1., 1.)))
R = {k: np.array(v) for k, v in out.items()}
n = len(R['none']); per = n / tables; fam = R['fam']; D = R['decl']
def b(v):
    m, se = mean_se(v, fam); return m * per, se * per
def show(name, v):
    m, se = b(v); print(f'| {name} | {m:+.3f} ± {se:.3f} |')
z = np.zeros(n)
defs_each_other = np.where(~D, R['none'] - R['lead_partner'], 0.)        # each defender reading its partner's plays, the lead included
defs_other_only = np.where(~D, R['none'] - R['partner'], 0.)
decl_reads_defs = np.where(D, R['none'] - R['all'], 0.)                  # for declarer every hidden play is a defender's
decl_other_only = np.where(D, R['none'] - R['opp'], 0.)
decl_lead_only = np.where(D, R['none'] - R['lead'], 0.)
defs_read_decl = np.where(~D, R['none'] - R['opp'], 0.)
defs_all = np.where(~D, R['none'] - R['all'], 0.)
print('| What is read, by whom | Tricks a board gained by the reader |'); print('| --- | ---: |')
show('The defenders reading each other (opening lead included)', defs_each_other)
show('  of which partner\'s plays after the lead', defs_other_only)
show('Declarer reading the defenders (opening lead included)', decl_reads_defs)
show('  of which the plays after the lead', decl_other_only)
show('  of which the opening lead alone', decl_lead_only)
show('Net to the defending side of the defenders\' plays being readable (first minus third)', defs_each_other - decl_reads_defs)
show('The defenders reading declarer\'s plays', defs_read_decl)
show('The defenders reading everything', defs_all)
dd = np.flatnonzero(~D); print(f'defender decisions a board {len(dd) / tables:.1f}; declarer decisions a board {D.sum() / tables:.1f}')
