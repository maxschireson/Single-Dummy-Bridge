"""E9-11 on the reading bench: the replayed house bidder's log-likelihood of each hidden seat's calls, on p41's pools.

For every stored decision of p41's reading bench (`transfer/gen8-p41-reading-pools-20261112`, files described in its
README) and every stored layout plus the true deal, this writes for each of the two hidden seats

  replay   the log-likelihood of that seat's calls under the house bidder (profile house-gen6), replayed on the
           seat's original hand in the layout: bridge_harness.cards.replay.ReplayReader, eps 0.02, as 9r-32 uses it
  scorer   the hand-fit scorer's log weight of the same hand and calls (the term the replay replaces)

and, per decision, whether each seat's actual calls are the house bidder's own choices on its true hand (every call
the arg max of the bidder: then the house bidder made them). The scorer rows summed over the two seats equal the
part's scw file up to a constant per decision; the script checks that.

What 9r-32 adds to 8p-32's weights (gen9.Gen9Player.replay_correction) is then, per side whose calls it replays,
replay - scorer for that side's hidden seats. `gen9_reading_bench.py replay-reading` turns these files into readings.

Needs bridge_harness.cards.replay (branch feature/gen9-bidding-cards, 82ab89f), so run it with that checkout first on
the path:

  PYTHONPATH=CHECKOUT python scripts/gen9_replay_terms.py --pools POOLS [--shard k/n]

Writes rpl-SS-PPPP.npz next to each part: replay [2, sum of L+1], scorer [2, sum of L+1], house [decisions, 4]
(int8: 1 if that seat's calls are the house bidder's own).
"""
import argparse
import gzip
import json
import os
from pathlib import Path
import sys
import time

import numpy as np

from bridge_harness.cards.replay import ProfileReplay, ReplayReader  # noqa: E402  (first: the checkout on PYTHONPATH)
from bridge_harness.core import card as parse_card  # noqa: E402
from bridge_harness.gen6_nets import FitScorer, hand_types  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(1, str(HERE))
from gen8_reading_bench import SCORER, load  # noqa: E402

SEATS = 'NESW'


def hand_cards(text):
    return [parse_card(suit + c) for suit, cards in zip('SHDC', text.split('.')) for c in cards]


def terms(part, reader, hard, scorer):
    rows, tables, _ = load(part)
    with np.load(part.with_name(part.name.replace('pools-', 'uns-'))) as z:
        unseen, hidden = z['cards'], z['hidden'].reshape(-1, 2)
    with gzip.open(part.with_name(part.name.replace('pools-', 'tab-').replace('.npz', '.json.gz')), 'rt') as f:
        tabs = json.load(f)
    with np.load(part.with_name(part.name.replace('pools-', 'scw-'))) as z:
        scw = z['scorer']
    replay_out, scorer_out, house_out, worst = [], [], [], 0.
    house_of, at, sw = {}, 0, 0
    for k, r in enumerate(rows):
        L, U = int(r['layouts']), int(r['unseen'])
        cards = unseen[at:at + U]
        at += U
        t = tabs[int(r['table'])]
        b = t['board']
        dealer, vul, auction = SEATS.index(b['dealer']), b['vulnerability'], tuple(b['auction'])
        hands = [hand_cards(h) for h in b['hands']]
        owner = {c: s for s, h in enumerate(hands) for c in h}
        if int(r['table']) not in house_of:                   # is each seat's every call the house bidder's arg max?
            flags = []
            for s in range(4):
                m = np.zeros((1, 52), np.int8)
                m[0, hands[s]] = 1
                ln, hn = hand_types(m)
                flags.append(int(float(hard.type_log_score(ln, hn, s, dealer, vul, auction)[0]) > -1e-3))
            house_of[int(r['table'])] = flags
        house_out.append(house_of[int(r['table'])])
        played = [parse_card(x) for x in t['played'][:int(r['ply'])]]
        both = np.concatenate([r['assign'], r['truth'][None]]).astype(np.int8)       # [L+1, U]
        rep, sco = np.zeros((2, L + 1)), np.zeros((2, L + 1))
        for j in range(2):
            seat = int(hidden[k, j])
            member = np.zeros((L + 1, 52), np.int8)
            member[:, [c for c in played if owner[c] == seat]] = 1
            member[:, cards] = (both == j)
            assert (member.sum(1) == 13).all(), (part.name, k, j)
            ln, hn = hand_types(member)
            rep[j] = reader.type_log_score(ln, hn, seat, dealer, vul, auction)
            sco[j] = scorer.type_log_score(ln, hn, seat, dealer, vul, auction)
        d = sco.sum(0) - scw[sw:sw + L + 1]
        sw += L + 1
        worst = max(worst, float(d.max() - d.min()))
        replay_out.append(rep)
        scorer_out.append(sco)
    assert at == len(unseen) and sw == len(scw)
    return (np.concatenate(replay_out, 1).astype(np.float32), np.concatenate(scorer_out, 1).astype(np.float32),
            np.array(house_out, np.int8).reshape(-1, 4), worst, len(rows))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--pools', required=True)
    ap.add_argument('--profile', default='house-gen6')
    ap.add_argument('--root', default='.', help='checkout holding the bidder (feature/gen9-bidding-cards)')
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--redo', action='store_true')
    a = ap.parse_args()
    k, n = (int(x) for x in a.shard.split('/'))
    reader = ProfileReplay(a.root).reader(a.profile)
    if reader is None:
        raise SystemExit(f'no replay reader for {a.profile}')
    hard = ReplayReader(reader.b, eps=0., temperature=1e-3)
    root = Path(a.root).resolve()
    path = next((q for q in (root / SCORER, HERE.parent / SCORER) if q.exists()), None)   # joined from its parts in either
    if path is None:
        raise SystemExit(f'{SCORER}: not joined from its parts in {root} or {HERE.parent}')
    scorer = FitScorer(str(path))
    parts = [p for i, p in enumerate(sorted(Path(a.pools).glob('pools-*-*.npz'))) if i % n == k]
    for p in parts:
        target = p.with_name(p.name.replace('pools-', 'rpl-'))
        if target.exists() and not a.redo:
            continue
        t0 = time.time()
        rep, sco, house, worst, decisions = terms(p, reader, hard, scorer)
        tmp = target.with_name(target.name + '.tmp.npz')
        np.savez_compressed(tmp, replay=rep, scorer=sco, house=house)
        os.replace(tmp, target)
        print(f'{p.name}: {decisions} decisions, {time.time() - t0:.0f} s, scorer vs scw spread {worst:.2e}, '
              f'house seats {house.mean():.2f}', flush=True)


if __name__ == '__main__':
    main()
