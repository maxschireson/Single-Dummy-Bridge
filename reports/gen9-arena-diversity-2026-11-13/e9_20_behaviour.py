#!/usr/bin/env python3
"""E9-20 part 2: behaviour distance between bots from the arena's common-auction boards (g9, Gen 9).

In a common auction both tables hold the same hands and the same auction, and the two bots sit in swapped seats. So
until the first card where the two tables' plays differ, every card is a decision taken by one bot at table 1 and by
the other bot at table 2 in the same position. For each pair of bots: the share of such paired decisions, forced moves
left out, where they chose different cards; the same for opening leads alone, by card and by suit.

  python3 e9_20_behaviour.py --ladder-wt DIR --meta rows.meta.json --cache DIR --out e9_20_behaviour.json [--shards 5]
"""
import argparse, json, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SEATS = 'NESW'


def name(x):
    if isinstance(x, str):
        return x
    if isinstance(x, dict):
        return str(x.get('id') or x.get('bot') or x.get('name') or json.dumps(x, sort_keys=True)[:40])
    return str(x)


def legal_count(hand, played, trick_cards):
    """How many legal cards the player had: hand minus played; must follow the suit led if able."""
    left = [c for c in hand if c not in played]
    if not trick_cards:
        return len(left)
    suit = trick_cards[0][0]
    follow = [c for c in left if c[0] == suit]
    return len(follow) if follow else len(left)


def cards_of(hand_pbn):
    """'9542.76432.2.985' (S.H.D.C) -> ['S9', 'S5', ...]."""
    out = []
    for suit, ranks in zip('SHDC', hand_pbn.split('.')):
        out += [suit + r for r in ranks]
    return out


def paired_decisions(board):
    """[(bot_table1, bot_table2, same_card, is_opening_lead, same_suit)] up to the first divergence."""
    tabs = board['conditions']['common']['tables']
    if len(tabs) != 2 or tabs[0]['auction'] != tabs[1]['auction']:
        return []
    hands = {SEATS[k]: cards_of(h) for k, h in enumerate(board['board']['hands'])}
    a1, a2 = [name(x) for x in tabs[0]['assignments']], [name(x) for x in tabs[1]['assignments']]
    p1, p2 = tabs[0]['plays'], tabs[1]['plays']
    out, played, trick = [], set(), []
    for n in range(min(len(p1), len(p2))):
        seat1, card1 = p1[n][0], p1[n][1:]
        seat2, card2 = p2[n][0], p2[n][1:]
        if seat1 != seat2:
            break
        k = SEATS.index(seat1)
        b1, b2 = a1[k], a2[k]
        forced = legal_count(hands[seat1], played, trick) <= 1
        if not forced and b1 != b2:
            out.append((b1, b2, card1 == card2, n == 0, card1[0] == card2[0]))
        if card1 != card2:
            break
        played.add(card1)
        trick.append(card1)
        if len(trick) == 4:
            trick = []
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ladder-wt', type=Path, required=True)
    ap.add_argument('--meta', type=Path, required=True)
    ap.add_argument('--cache', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--shards', type=int, default=5)
    ap.add_argument('--workers', type=int, default=8)
    a = ap.parse_args()
    sys.path.insert(0, str(a.ladder_wt / 'scripts')); sys.path.insert(0, str(a.ladder_wt))
    import arena_feed_rows as afr
    meta = json.loads(a.meta.read_text())

    def one(m):
        base = f"arena/replays/data/{m['cohort']}"
        try:
            index = afr.fetch(a.cache, m['ref'], f'{base}/index.json')
            names = []
            recs = list(index.get('records') or [])
            for sh in index.get('record_shards') or []:
                recs += afr.fetch(a.cache, m['ref'], f'{base}/{sh}')
            for r in recs:
                if r.get('shard') and r['shard'] not in names:
                    names.append(r['shard'])
            res = []
            for name in names[:a.shards]:
                shard = afr.fetch(a.cache, m['ref'], f'{base}/{name}')
                for b in shard.values():
                    if 'conditions' in b:
                        res += paired_decisions(b)
            return m['source'], res, None
        except Exception as e:  # a feed that cannot be read is reported, not fatal
            return m['source'], [], repr(e)[:200]

    agg, errors = {}, {}
    with ThreadPoolExecutor(a.workers) as pool:
        for src, res, err in pool.map(one, meta['sources']):
            if err:
                errors[src] = err
            for b1, b2, same, lead, same_suit in res:
                key = '~'.join(sorted((b1, b2)))
                x = agg.setdefault(key, dict(decisions=0, different=0, leads=0, different_leads=0, different_lead_suits=0))
                x['decisions'] += 1; x['different'] += (not same)
                if lead:
                    x['leads'] += 1; x['different_leads'] += (not same); x['different_lead_suits'] += (not same_suit)
    for x in agg.values():
        x['share_different'] = x['different'] / x['decisions'] if x['decisions'] else None
        x['share_different_leads'] = x['different_leads'] / x['leads'] if x['leads'] else None
        x['share_different_lead_suits'] = x['different_lead_suits'] / x['leads'] if x['leads'] else None
    a.out.write_text(json.dumps(dict(pairs=agg, errors=errors, shards_per_source=a.shards), indent=1))
    print(f'{len(agg)} pairs of bots, {sum(x["decisions"] for x in agg.values()):,} paired decisions, {len(errors)} feeds failed -> {a.out}')


if __name__ == '__main__':
    main()
