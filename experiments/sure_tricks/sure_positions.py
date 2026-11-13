"""Guaranteed total tricks by card (pooled-defender search) at positions from the sets.
Usage: sure_positions.py fusion_deals.json name [name ...]   -> appends JSON lines to stdout"""
import json, sys, time
from sure import Sure
from fusionlab import Board, card, SEATS

P = {
 'A6_7': ('A6', 'A6-QW', 'HQ H4 H2 HK SA S5 S2 S3 S4 S6 SK H5 HA H6 H3 H9 C3 C8 CK C2 C4 C5 CA CT', {}, 'after hearts and both top clubs'),
 'A6_8': ('A6', 'A6-QW', 'HQ H4 H2 HK SA S5 S2 S3 S4 S6 SK H5 HA H6 H3 H9 C3 C8 CK C2', {}, 'after hearts and one top club'),
 'A4_8': ('A4', 'A4-QW', 'HQ H4 H2 HK SA S5 S2 S3 S4 S6 SK H5 HA H6 H3 H9 S7 C2 S9 H9'.replace(' S7 C2 S9 H9', ''), {}, 'after both top hearts'),
 'S6_8': ('S6', 'S6-QW', 'CK C6 C2 CA SA S5 S2 S3 S4 S6 SK C3 HA H5 H2 H9 H4 H6 HK HT', {}, 'after both top hearts, third heart not yet ruffed'),
 'S6_6': ('S6', 'S6-QW', 'CK C6 C2 CA SA S5 S2 S3 S4 S6 SK C3 HA H5 H2 H9 H4 H6 HK HT H3 HJ S7 H7 C7 C8 C5 C9'.replace(' C7 C8 C5 C9', ''), {}, 'after the third heart is ruffed'),
 'B6_8': ('B6', 'B6-QW', 'CQ C2 C5 CA SA S9 S2 ST SK SJ S5 H5 CK C4 C3 C6 HA H8 H2 H6', {}, 'after two top trumps, top club, heart ace'),
 'B6_8p': ('B6', 'B6-QW', 'CQ C2 C5 CA SA S9 S2 ST SK SJ S5 H5 CK C4 C3 C6 HA H8 H2 H6', {'W': 'HT H9 CJ'}, 'same position'),
 'B6m_8p': ('B6m', 'B6m-QE', 'C5 C2 C4 CA SA ST S2 S9 SK H5 S5 SJ CK C6 C3 C9 HA H6 H2 H8', {'E': 'HT H9 CJ'}, 'mirror position'),
}
if __name__ == '__main__':
    data = json.load(open(sys.argv[1]))
    deals = {d['id']: d for d in data['deals']}
    KEYS = ('id', 'hands', 'contract', 'declarer', 'dealer', 'vulnerability', 'auction', 'opening_lead')
    for name in sys.argv[2:]:
        st, did, prefix, pins, note = P[name]
        b = Board.from_dict({k: deals[did][k] for k in KEYS})
        known = {SEATS.index(s): [card(c) for c in cs.split()] for s, cs in pins.items()}
        t = time.time()
        s = Sure.from_game(b, [card(c) for c in prefix.split()], known)
        left = 13 - len(prefix.split()) // 4
        r = s.root_cards(left)
        print(json.dumps(dict(name=name, set=st, deal=did, left=left, on_lead=SEATS[s.leader0], note=note,
                              pinned=' '.join('%s to %s' % (cs, {'W': 'West', 'E': 'East'}[x]) for x, cs in pins.items()),
                              guaranteed={c: s.won + n for c, n in r.items()}, nodes=s.nodes, seconds=round(time.time() - t, 1))), flush=True)
