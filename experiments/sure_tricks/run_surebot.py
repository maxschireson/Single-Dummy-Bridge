import sys, json, time
from fusionlab import *
from surebot import SureFirst
from fusion_test import board
data = json.load(open('fusion_deals.json'))
deals = {d['id']: d for d in data['deals']}
base, ids, seeds = sys.argv[1], sys.argv[2].split(','), int(sys.argv[3])
bot = SureFirst(make_bot(base), max_left=int(sys.argv[4]) if len(sys.argv) > 4 else 8, max_nodes=15_000_000)
dds = DDS(cache_path='')
out = open(sys.argv[5], 'a') if len(sys.argv) > 5 else None
for did in ids:
    d = deals[did]
    b = board(d)
    for seed in range(1, seeds + 1):
        t0 = time.time()
        t = run(b, bot, avoid=d['avoid'], critical=d['critical'], seed=seed, dds=dds)
        ov = [(a['ply'] // 4 + 1, a['sure_override'], a['card']) for a in t['actions'] if a.get('sure_override')]
        big = sum(1 for a in t['actions'] if a.get('sure') == 'too big')
        print(base + '+sure', did, 'seed', seed, 'tricks', t['declarer_tricks'], 'overrides (trick, base card, played)', ov, 'too big', big, '%.0f s' % (time.time() - t0), flush=True)
        if out:
            out.write(json.dumps(dict(bot=base + '+sure', deal=did, set=d['set'], seed=seed, tricks=t['declarer_tricks'],
                                      made=t['declarer_tricks'] >= b.contract.level + 6, overrides=ov, too_big=big, play=tricks_text(t['actions']))) + '\n')
            out.flush()
