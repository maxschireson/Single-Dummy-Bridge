import sys, math, collections, re
import numpy as np
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from analyze import load, units
ADULT=('Open','Senior','Mixed',"Women's"); ROLES=('declarer','defense','lead'); W={'declarer':.25,'defense':.5,'lead':.25}
T=load(sys.argv[1:] or ['lt']); U=units(T)
loss=np.array([u[5] for u in U]); dng=np.array([u[9] for u in U]); role_of=np.array([u[1] for u in U])
cat=np.array([T[u[0]]['category'] for u in U]); isad=np.isin(cat,ADULT)
ec=np.zeros(len(U)); ref={}
for role in ROLES:
    m=(role_of==role)&isad; ref[role]=loss[m].mean()
    pos=m&(dng>0); qs=np.quantile(dng[pos],np.linspace(0,1,26)); xs=[];ys=[]
    for lo,hi in zip(qs[:-1],qs[1:]):
        b=pos&(dng>=lo)&(dng<=hi); xs.append(dng[b].mean()); ys.append(loss[b].mean())
    r=role_of==role; ec[r]=np.where(dng[r]>0,np.interp(dng[r],xs,ys),loss[m&(dng<=0)].mean())
print('adult average: ' + ', '.join(f'{r} {ref[r]:.3f}' for r in ROLES) + f', pooled {sum(W[r]*ref[r] for r in ROLES):.3f}')
def phase(t):
    c=t['category']; e=t.get('event') or ''
    if c.startswith('Junior'): return 'KO' if '(KO)' in c else 'RR'
    if 'Stage 1' in e: return 'Early'
    if 'Stage 2' in e: return 'KO'
    if t['stage'] in ('Round robin','Round of 16'): return 'Early'
    if t['stage'] in ('Quarterfinal','Semifinal','Final'): return 'KO'
def pooled(sel):
    s=0; v=0; parts={}
    for role in ROLES:
        by=collections.defaultdict(list)
        for k in sel[role]: by[U[k][0]].append(k)
        x=np.array([np.mean(loss[ks]-ec[ks]) for ks in by.values()])
        parts[role]=x.mean()+ref[role]; s+=W[role]*parts[role]; v+=W[role]**2*x.var(ddof=1)/len(x)
    return s, math.sqrt(v), parts
g=collections.defaultdict(lambda: collections.defaultdict(list)); yrs=collections.defaultdict(set)
for k,u in enumerate(U):
    t=T[u[0]]; p=phase(t)
    if p is None: continue
    for key in ((t['category'].replace(' (KO)',''),p),(t['category'].replace(' (KO)',''),'All')):
        g[key][u[1]].append(k); yrs[key].add(t['year'][2:])
for c in ['Open','Mixed','Senior',"Women's",'Junior U26','Junior U21','Junior RONA']:
    for p in ('Early','RR','KO','All'):
        if (c,p) in g:
            s,se,pt=pooled(g[(c,p)])
            print(f'{c} | {p} | {",".join(sorted(yrs[(c,p)]))} | {s:.3f} +- {se:.3f} | D {pt["declarer"]:.3f} F {pt["defense"]:.3f} L {pt["lead"]:.3f}')
