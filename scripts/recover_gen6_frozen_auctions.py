import importlib.util,json,hashlib,sys
from pathlib import Path
p=Path('/workspace/scratch/d59c0a9fe14a/gen6-full-data/scripts/match_gen6_5rz.py')
s=importlib.util.spec_from_file_location('match',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
from bridge_harness.bidding_ppo import Policy
reserved=json.loads(Path(__file__).with_name('frozen-match-families.json').read_text())
manifest=json.loads(Path(__file__).with_name('frozen-match-manifest.json').read_text())
bidder=Policy.load(m.REPO/'models/bidding/gen5-2026-11-10/bidder.keras')
rows=[]
for i in range(10000):
    b=m.make_board(manifest['seed'],i,'test');family=m.deal_key(b.hands,True)
    if family not in reserved: continue
    assert family==reserved[len(rows)],(i,family)
    bid,decisions=m.auction(b,[bidder]*4)
    rows.append(dict(index=len(rows),family=family,board=bid.to_dict(),raw_board=b.to_dict(),bidding=decisions))
    if len(rows)%10==0:print('reconstructed auctions',len(rows),flush=True)
    if len(rows)==100:break
assert len(rows)==100
m.RUN.mkdir(parents=True,exist_ok=True)
m.atomic_json(m.RUN/'auctions.json',rows)
assert m.sha(m.RUN/'auctions.json')==manifest['auctions_sha256'], 'Reconstructed auctions do not match frozen hash; do not run'
m.atomic_json(m.RUN/'manifest.json',manifest)
m.atomic_json(m.RUN/'reserved-families.json',reserved)
m.verify(manifest)
print('PASS: all 100 original auction bytes and every model/runtime SHA256 match the original frozen manifest.',flush=True)
