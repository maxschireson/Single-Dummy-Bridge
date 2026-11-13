"""Scripted declarer lines against the oracle, to check that the defence does its job."""
import sys, json
from fusionlab import *

class Script:
    """Plays the listed cards in order when legal (skipping ones no longer held); afterwards, and when
    the next listed card is not legal, plays double-dummy optimally on the TRUE deal (lowest such card)."""
    def __init__(self, board, cards, dds):
        self.board, self.cards, self.dds = board, [card(c) for c in cards.split()], dds
    def choose(self, o, rng):
        played = {c for _, c in o.history}
        while self.cards and self.cards[0] in played:
            self.cards.pop(0)
        if self.cards and self.cards[0] in o.legal:
            return Decision(self.cards.pop(0), {})
        hands = tuple(tuple(c for c in h if c not in played) for h in self.board.hands)
        v = self.dds.solve(hands, o.contract.trump, o.leader, o.trick)[0]
        best = max(v[c] for c in o.legal)
        return Decision(min(c for c in o.legal if v[c] == best), {})

if __name__ == '__main__':
    deals = json.load(open(sys.argv[1]))
    dds = DDS(cache_path='')
    lines = {'sound': 'H4 HK SA S2 S4 SK HA H3 C3 CK C4 CA C7 C6',
             'toA': 'H4 HK SA S2 S4 SK D4 DA', 'toK': 'H4 HK SA S2 S4 SK C3 CK D5 DK', 'runJ': 'H4 HK SA S2 S4 SK C3 CK DJ',
             'trump4': 'H4 HK SA S2 S4 SK SQ S9 S7 SJ S8 ST'}
    for d in deals:
        b = Board.from_dict({k: v for k, v in d.items() if k in ('id','hands','contract','declarer','dealer','vulnerability','auction','opening_lead')})
        out = []
        for name, line in lines.items():
            t = run(b, Script(b, line, dds), avoid=d['avoid'], critical=d['critical'], dds=dds)
            out.append('%s:%d' % (name, t['declarer_tricks']))
            if len(sys.argv) > 2 and sys.argv[2] == name:
                print('   ' + ' | '.join(tricks_text(t['actions'])))
        print(d['id'], 'DD', dd_tricks(b, dds), ' '.join(out))
