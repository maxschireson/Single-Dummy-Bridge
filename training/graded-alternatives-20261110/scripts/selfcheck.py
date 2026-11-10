"""Check the fast simulator against the user's harness on real auctions."""
import os
import sys
import time

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
import numpy as np

sys.path.insert(0, '/home/claude/gen5r')
sys.path.insert(0, '/home/claude/bid')
import abid  # noqa: E402
from bridge_harness import core  # noqa: E402
from bridge_harness.bidding_env import (BidObservation, CALLS, encode, legal_mask, paired_auctions,  # noqa: E402
                                        terminal_score)
from bridge_harness.bidding_ppo import Policy  # noqa: E402

n_deals = int(sys.argv[1]) if len(sys.argv) > 1 else 200
deals = abid.Deals.from_export('/home/claude/bid/data/train.jsonl.gz', limit=n_deals)
base = Policy.load('/home/claude/bid/base.keras')
ppo = Policy.load('/home/claude/bid/ppo40k.keras')
print('models loaded; outputs:', len(base.model.outputs), len(ppo.model.outputs))

t = time.time()
result, auc = abid.duplicate(deals, ppo, base)
dt = time.time() - t
print('fast duplicate: %d deals, %d calls, %.1fs' % (n_deals, int(auc.n.sum()), dt), abid.summary(result))

# (1) features and legal masks at every decision of the first 60 auctions
rng = np.random.default_rng(0)
bad_x = bad_m = checked = 0
for a in range(min(60, len(auc))):
    d = auc.deal[a]
    calls = auc.call_text(a)
    for n in range(len(calls)):
        seat = (auc.dealer[a] + n) % 4
        obs = BidObservation(tuple(deals.hands[d][seat]), int(seat), int(auc.dealer[a]), deals.vul[d], tuple(calls[:n]))
        ref = encode(obs)
        x, length = abid.decision_inputs(auc, np.array([a]), np.array([n]))
        checked += 1
        if length[0] != len(ref) or not np.array_equal(x[0, :length[0]], ref):
            bad_x += 1
        snap = auc.clone(np.array([a]))
        # rebuild state by replaying the prefix
        fresh = abid.Auctions(deals, np.array([d]), np.array([0]))
        for c in calls[:n]:
            fresh.apply(np.array([0]), np.array([CALLS.index(c)]))
        if not np.array_equal(fresh.legal(np.array([0]))[0], legal_mask(int(auc.dealer[a]), calls[:n])):
            bad_m += 1
print('decisions checked:', checked, '| feature mismatches:', bad_x, '| legal-mask mismatches:', bad_m)

# (2) terminal scores against the harness
bad_s = 0
ns = auc.ns_score()
for a in range(len(auc)):
    d = auc.deal[a]
    board = core.Board('x', tuple(tuple(h) for h in deals.hands[d]), None, int(auc.dealer[a]), deals.vul[d])
    if terminal_score(board, auc.call_text(a), deals.table[d].tolist()) != ns[a]:
        bad_s += 1
print('auctions:', len(auc), '| score mismatches:', bad_s)

# (3) whole pipeline against the harness's own paired_auctions on the first 64 deals
m = min(64, n_deals)
boards = [core.Board('x', tuple(tuple(h) for h in deals.hands[i]), None, int(deals.dealer[i]), deals.vul[i]) for i in range(m)]
from bridge_harness.bidding_env import deal_key  # noqa: E402
tables = [deals.table[i].tolist() for i in range(m)]
t = time.time()
rows, _ = paired_auctions(boards, tables, ppo, [base] * m, np.random.default_rng(0), explore=False)
dt_h = time.time() - t
ref_imps = np.array([r['imps'] for r in rows])
same_calls = sum(rows[i]['tables'][room]['calls'] == auc.call_text(i + room * n_deals) for i in range(m) for room in (0, 1))
print('harness paired_auctions on %d deals: %.1fs | IMPs identical: %s | identical auctions: %d of %d' % (
    m, dt_h, np.array_equal(ref_imps, result[:m]), same_calls, 2 * m))
