import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""How much the auction says about the hidden hands at the lead, and how much the belief net captures.

Per lead, in nats per layout:
  available = -log u(C): u(C) is the share of uniform layouts consistent with the auction
              (the exact posterior is uniform on C, so its log-density gain over uniform is -log u(C))
  captured  = log P_belief(true layout) - log P_uniform(true layout), with P_belief the sampler's
              exact probability of the true layout (product of v5 weights conditioned on hand sizes)
"""
import gzip, json, math, os, sys
os.environ['BRIDGE_DDS_CACHE'] = ''
import numpy as np
sys.path.insert(0, HERE)
from analyze_leads import load
from nbid import RUNTIME
from bridge_harness.core import Board, Game
from bridge_harness.belief_capacity import Weights
from bridge_harness.bidding_sampling import WeightedSampler
ROOT = FEED
belief = Weights(ROOT + '/artifacts/v5/belief.npz')
LOG_UNIFORM = -(math.lgamma(40) - 3 * math.lgamma(14))
rows = [r for r in load(sys.argv[1] if len(sys.argv) > 1 else HERE + '/out/main_*.jsonl*')
        if not r.get('passed_out') and r['exact_stats'].get('block_proposals')]
avail, capt, marg = [], [], []
per_lead = {}
for r in rows:
    st = r['exact_stats']
    if not st['completion_successes'] or not st['block_pool']:
        continue
    u = (st['block_pool'] / st['block_proposals']) * (st['completion_successes'] / st['completions'])
    ep = json.load(gzip.open(f"{ROOT}/episodes/{r['index']:06d}.json.gz")); board = Board.from_dict(ep['board'])
    o = Game(board).observation()
    s = WeightedSampler(o, belief.logits(o), 1.)
    owner = {c: seat for seat in range(4) for c in board.hands[seat]}
    logw = sum(s.weights[i][s.unknown.index(owner[c])] for i, c in enumerate(s.cards))
    logp = logw - s.partition(0, s.caps)
    avail.append(-math.log(u)); capt.append(logp - LOG_UNIFORM)
    per_lead[r['index']] = [avail[-1], capt[-1]]
avail, capt = np.array(avail), np.array(capt)
se = lambda x: x.std(ddof=1) / np.sqrt(len(x))
print('leads', len(avail))
print('available from the auction: %.2f +- %.2f nats per layout (median %.2f; 10th-90th pct %.1f to %.1f)' % (avail.mean(), se(avail), np.median(avail), *np.percentile(avail, [10, 90])))
print('captured by the belief sampler: %.2f +- %.2f nats (median %.2f)' % (capt.mean(), se(capt), np.median(capt)))
print('gap: %.2f +- %.2f nats; captured share of mean %.0f%%' % ((avail - capt).mean(), se(avail - capt), 100 * capt.mean() / avail.mean()))
print('per unknown card (39): available %.3f, captured %.3f, gap %.3f' % (avail.mean() / 39, capt.mean() / 39, (avail - capt).mean() / 39))
print('uniform acceptance: mean %.4f%%, median %.4f%%' % (100 * np.exp(-avail).mean(), 100 * np.exp(-np.median(avail))))
json.dump(per_lead, open(HERE + '/out/info.json', 'w'))
