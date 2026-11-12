"""Verify and combine frozen auction cohorts without DD or future-call inputs."""
import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.auction_belief import encode_auction
from bridge_harness.belief_capacity import SCHEMA, PLAY_SIZE, sha
from bridge_harness.bidding_env import deal_key
from bridge_harness.core import Board
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest


def prepare(base, play_roots, local, cohort, out):
    if out.exists():
        raise ValueError('Use a new frozen output directory')
    out.mkdir(parents=True)
    splits = {}
    def assign(g, split):
        if g in splits and splits[g] != split:
            raise ValueError(f'Family split conflict: {g}')
        splits[g] = split
    reserved = json.loads((base/'bidding-reserved-families.json').read_text())
    for split, groups in reserved.items():
        for g in groups: assign(g, split)
    for root in [base, *play_roots]:
        ds = json.loads((root/'dataset.json').read_text())
        for e in ds['shards']:
            p = root/e['file']
            if sha(p) != e['sha256']: raise ValueError('Input shard changed')
            with np.load(p, allow_pickle=False) as z:
                for g in np.unique(z['split_group']): assign(str(g), e['split'])
    buffers = defaultdict(list); entries = []; counts = Counter(); families = defaultdict(set)
    seen = set(); provenance = []; input_hashes = {}
    def flush(source, split):
        rows = buffers[source, split]
        if not rows: return
        p = out/f'{source}-{split}-{len(entries):05d}.npz'
        np.savez_compressed(p, **{k: np.stack([r[k] for r in rows]) for k in rows[0]})
        entries.append(dict(file=p.name, sha256=sha(p), rows=len(rows), source=source, split=split))
        counts[source+'_'+split+'_positions'] += len(rows)
        rows.clear()
    def add(raw, source, provenance_name, supplied=None):
        b = Board.from_dict(raw); g = deal_key(b.hands, True)
        if supplied:
            if supplied['family'] != g: raise ValueError('Incorrect canonical family')
            assign(g, supplied['split'])
        split = splits.setdefault(g, 'validation' if int(g[:8], 16)%5 == 0 else 'train')
        identity = digest([b.hands, b.dealer, b.vulnerability, b.auction])
        if identity in seen:
            counts['duplicate_auctions_skipped'] += 1; return
        seen.add(identity)
        if split == 'test':
            counts['reserved_test_auctions_skipped'] += 1; return
        families[split].add(g); counts['unique_auctions'] += 1
        counts['passed_out'] += b.contract is None
        provenance.append(dict(family=g, split=split, auction_identity=identity,
                               source=source, input=provenance_name))
        rng = np.random.default_rng(int(identity[:16],16))
        for observer in range(4):
            turns = [i for i in range(len(b.auction)) if (b.dealer+i)%4 == observer]
            if not turns: raise ValueError('No observed bidder turn')
            for kind, prefix in [(1, b.auction), (0, b.auction[:int(rng.choice(turns))])]:
                x, support = encode_auction(b.hands[observer], observer, b.dealer, b.vulnerability, prefix)
                y = np.zeros(52, np.int8)
                for seat, hand in enumerate(b.hands): y[list(hand)] = (seat-observer)%4
                mask = support.sum(-1)>1
                if not np.all(support[np.arange(52),y]): raise ValueError('True owner excluded')
                buffers[source, split].append(dict(**x, play=np.zeros(PLAY_SIZE,np.float32),
                    owner_target=y, owner_loss_mask=mask, support=support,
                    kind=np.int8(kind), split_group=g))
                if len(buffers[source, split]) >= 4096: flush(source, split)
    # Prefer the current bidder's transcript when two exports are identical.
    for name, source in [('g0001-bid40k','bidding'),('g0001','ben'),('g0001-direct','bidding')]:
        p = local/(name+'.jsonl'); input_hashes[str(p)] = sha(p)
        for line in p.read_text().splitlines(): add(json.loads(line), source, name)
        print(json.dumps(dict(event='local_cohort', cohort=name, counts=dict(counts))),flush=True)
    m = json.loads((cohort/'manifest.json').read_text()); count=0
    for e in m['board_shards']:
        p=cohort/e['file']
        if sha(p) != e['sha256'] or p.stat().st_size != e['size_bytes']: raise ValueError('Cohort shard changed')
        input_hashes[str(p)]=e['sha256']
        with gzip.open(p,'rt') as f:
            for line in f:
                row=json.loads(line); add(row['board'],'bidding',m['cohort'],row);count+=1
    if count != m['boards']: raise ValueError('Incomplete cohort')
    for key in list(buffers): flush(*key)
    if families['train'] & families['validation']: raise ValueError('Split leakage')
    atomic_json(out/'sources.json', provenance)
    ds=dict(schema=SCHEMA,validated=True,shards=entries,counts=dict(counts),
        families={s:len(g) for s,g in families.items()},input_sha256=input_hashes,
        source_files_sha256=sha(out/'sources.json'),source_sha256=sha(__file__),
        encoding='Four completed-auction views and four own-turn prefixes per distinct auction. Hidden hands are targets only; no DD inputs.',
        heldout_rule='Preserve all existing family splits including test reservations; use supplied 80/20 split for new cohort.')
    atomic_json(out/'dataset.json',ds)
    print(json.dumps(dict(event='complete',counts=dict(counts),families=ds['families'])),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('base','local','cohort','out'): p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--play',type=Path,action='append',default=[])
    a=p.parse_args();prepare(a.base,a.play,a.local,a.cohort,a.out)
