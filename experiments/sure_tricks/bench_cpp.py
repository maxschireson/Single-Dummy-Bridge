"""Time the C++ solver on positions from the test sets at a range of depths.
Each position is the stated deal after the first k tricks of its sound line (cards-left = 13 - k)."""
import json, sys, time
from sure import Sure
from csure import line, solve
from fusionlab import Board, card, symbol

LINES = {   # full sound-line play (all four hands) as played against the oracle, enough tricks to cut anywhere
 'A6': ('A6-QW', 'HQ H4 H2 HK SA S5 S2 S3 S4 S6 SK H5 HA H6 H3 H9 C3 C8 CK C2 C4 C5 CA CT C7 CQ C6 C9'),
 'S6': ('S6-QW', 'CK C6 C2 CA SA S5 S2 S3 S4 S6 SK C3 HA H5 H2 H9 H4 H6 HK HT H3 HJ S7 H7'),
 'A4': ('A4-QW', 'HQ H4 H2 HK SA S5 S2 S3 S4 S6 SK H5 HA H6 H3 H9'),
 'B6': ('B6-QW', 'CQ C2 C5 CA SA S9 S2 ST SK SJ S5 H5 CK C4 C3 C6 HA H8 H2 H6 HK H9 H4 H7'),
}
KEYS = ('id', 'hands', 'contract', 'declarer', 'dealer', 'vulnerability', 'auction', 'opening_lead')

def positions(deals, name, lefts):
    did, play = LINES[name]
    cards = play.split()
    b = Board.from_dict({k: deals[did][k] for k in KEYS})
    for left in lefts:
        k = 13 - left
        if 4 * k > len(cards):
            continue
        s = Sure.from_game(b, [card(c) for c in cards[:4 * k]])
        yield name, left, s

def b_need(deals, name):
    return int(deals[LINES[name][0]]['contract'][0]) + 6


if __name__ == '__main__':
    data = json.load(open('fusion_deals.json'))
    deals = {d['id']: d for d in data['deals']}
    lefts = [int(x) for x in sys.argv[1].split(',')]
    args = sys.argv[2:]
    for name in LINES:
        for nm, left, s in positions(deals, name, lefts):
            t0 = time.time()
            a2 = list(args)
            if '--contract' in a2:
                a2.remove('--contract'); a2 += ['--need', str(b_need(deals, nm) - s.won)]
            r = solve([line(s)], *a2)[0]
            g = {symbol(int(c)): (v if '--need' in a2 else s.won + v) for c, v in r['cards'].items()}
            print('%s %2d left %-28s search %8.4f s  total %8.3f s  nodes above %9d  probes %8d  new table positions %7d | %s'
                  % (nm, left, ' '.join(args), r['search_seconds'], r['seconds'], r['nodes_above'], r['probes'], r['table_new'], g), flush=True)
