import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Fit a logit choice model on double-dummy loss from recorded plays on the true deal.

P(card) = exp(-lambda * loss(card)) / sum over legal cards. One lambda per group:
opening lead; declarer side and defenders, in tricks 1-5 and in tricks 6-12.
"""
import glob, gzip, json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))

def group(ply, controller, declarer):
    if ply == 0: return 'lead'
    return ('dec' if controller == declarer else 'def') + ('_early' if ply < 20 else '_late')

def main(pattern, out):
    data = {}
    for f in sorted(glob.glob(pattern)):
        for line in (gzip.open(f, 'rt') if f.endswith('.gz') else open(f)):
            r = json.loads(line)
            for p in r['plies']:
                t = np.array(p['true_dd'], float); loss = t.max() - t
                data.setdefault(group(p['ply'], p['controller'], r['declarer']), []).append((loss, int(loss[p['legal'].index(p['played'])])))
    lam = {}
    grid = np.linspace(0, 8, 321)
    print(f'{"group":10s} {"plays":>6s} {"zero-loss":>9s} {"1 trick":>8s} {"2+":>6s} {"chance zero-loss":>16s} {"lambda":>7s} {"nats/play vs uniform":>20s}')
    for g, rows in sorted(data.items()):
        ll = np.zeros(len(grid))
        base = 0.0
        for loss, lp in rows:
            ll += -grid * lp - np.log(np.exp(-np.outer(grid, loss)).sum(axis=1))
            base += -np.log(len(loss))
        k = int(ll.argmax()); lam[g] = float(grid[k])
        lp = np.array([x[1] for x in rows]); chance = np.mean([(x[0] == 0).mean() for x in rows])
        print(f'{g:10s} {len(rows):6d} {100*np.mean(lp==0):8.1f}% {100*np.mean(lp==1):7.1f}% {100*np.mean(lp>=2):5.1f}% {100*chance:15.1f}% {lam[g]:7.2f} {(ll[k]-base)/len(rows):20.3f}')
    json.dump(lam, open(out, 'w'), indent=1)
    print('saved', out, lam)

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else HERE + '/out/late_[01].jsonl*', sys.argv[2] if len(sys.argv) > 2 else HERE + '/out/lambda.json')
