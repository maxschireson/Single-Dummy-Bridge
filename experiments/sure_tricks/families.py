"""Strategy-fusion test deals. Each *set* is a group of layouts that look the same to declarer until
the critical decision; a declarer passes a set only by making the contract in every layout of it.

Hands are N, E, S, W in S.H.D.C order (bridge_harness.core.Board.from_dict format). South declares.
"""
import json

AUC6 = ["1S", "PASS", "2N", "PASS", "3S", "PASS", "4N", "PASS", "5H", "PASS", "6S", "PASS", "PASS", "PASS"]
AUC4 = ["1S", "PASS", "2N", "PASS", "4S", "PASS", "PASS", "PASS"]
AUC6B = ["2C", "PASS", "2D", "PASS", "2S", "PASS", "3S", "PASS", "4N", "PASS", "5C", "PASS", "6S", "PASS", "PASS", "PASS"]


def deal(id, set_id, n, e, s, w, contract, auction, lead, layout, **extra):
    d = dict(id=id, set=set_id, hands=[n, e, s, w], contract=contract, declarer='S', dealer='S', vulnerability='None',
             auction=auction, opening_lead=lead, layout=layout, avoid='D', critical=['DQ'], weight=1)
    d.update(extra)
    return d


SETS = {}
DEALS = []


def add_set(set_id, kind, title, theme, sound, script, cert_tricks, deals, **extra):
    SETS[set_id] = dict(id=set_id, kind=kind, title=title, theme=theme, sound_line=sound, script=script,
                        cert_tricks=cert_tricks, deals=[d['id'] for d in deals], **extra)
    DEALS.extend(deals)


# ---- A6: two-way queen, strip and exit in clubs, 6S. No squeeze, 12 tricks is the limit -> exact tie. ----
N, S = "KQ872.A4.KT4.A73", "AJT94.K3.AJ5.K64"
SOUND_A = ("Win the heart, draw trumps in two rounds, cash the other top heart and the two top clubs, exit with the "
           "third club. Whoever wins must lead a diamond (three diamond tricks whatever he leads) or give a ruff "
           "and discard (ruff in one hand, throw a diamond from the other, ruff the third diamond).")
add_set('A6', 'tie', "Two-way queen, strip and club exit, 6S",
        "AJ5 opposite K104. Every card that does not commit the diamonds is double-dummy equal, including the low "
        "diamond lead and extra rounds of trumps that destroy the ending.",
        SOUND_A, 'H4 HK SA S2 S4 SK HA H3 C3 CK C4 CA C7 C6', 3, [
            deal('A6-QW', 'A6', N, "3.87652.9862.QT8", S, "65.QJT9.Q73.J952", '6S', AUC6, 'HQ', "DQ West (3 diamonds, 2 trumps)", weight=15),
            deal('A6-QE', 'A6', N, "3.87652.Q862.QT8", S, "65.QJT9.973.J952", '6S', AUC6, 'HQ', "DQ East (4 diamonds, 1 trump)", weight=20),
        ])
add_set('A6m', 'tie', "Two-way queen, strip and club exit, 6S (East-West hands exchanged)",
        "Mirror of A6, so a declarer with a fixed habit in the diamond suit is caught on the other side as well.",
        SOUND_A, 'H4 HK SA S2 S4 SK HA H3 C3 CK C4 CA C7 C6', 3, [
            deal('A6m-QE', 'A6m', N, "65.QJT9.Q73.J952", S, "3.87652.9862.QT8", '6S', AUC6, 'H8', "DQ East (3 diamonds, 2 trumps)", weight=15),
            deal('A6m-QW', 'A6m', N, "65.QJT9.973.J952", S, "3.87652.Q862.QT8", '6S', AUC6, 'H8', "DQ West (4 diamonds, 1 trump)", weight=20),
        ])

# ---- A4: same theme in 4S, A105 opposite KJ4, three club losers as the exit. ----
N, S = "KQ872.A4.KJ4.763", "AJT94.K3.AT5.854"
add_set('A4', 'tie', "Two-way queen, strip and club exit, 4S",
        "A105 opposite KJ4 with three club losers. Declarer gives up the clubs only after hearts are gone.",
        "Win the heart, draw trumps, cash the other top heart, play a club. The defenders take their three clubs and "
        "the one on lead must open diamonds or give a ruff and discard.",
        'H4 HK SA S2 S4 SK HA H3 C3 C4', 3, [
            deal('A4-QW', 'A4', N, "3.87652.9862.KQT", S, "65.QJT9.Q73.AJ92", '4S', AUC4, 'HQ', "DQ West (3 diamonds)", weight=15),
            deal('A4-QE', 'A4', N, "3.87652.Q862.KQT", S, "65.QJT9.973.AJ92", '4S', AUC4, 'HQ', "DQ East (4 diamonds)", weight=20),
        ])

# ---- B6: throw-in with the master trump. ----
N, S = "8752.Q42.KT4.732", "AK643.AK3.AJ5.AK"
SOUND_B = ("Win the club, cash the two top trumps (one defender keeps the master trump), cash the other top club and "
           "three hearts ending in dummy, ruff dummy's last club, exit with a trump. The defender with the master "
           "trump must lead a diamond or give a ruff and discard.")
add_set('B6', 'tie', "Two-way queen, throw-in with the master trump, 6S",
        "The only loser is the master trump, so it is also the exit card. Cashing the wrong top diamond first leaves "
        "the defender a safe diamond lead through the remaining honour.",
        SOUND_B, 'C2 CA SA S2 SK S5 CK C3 HA H2 HK H4 H3 HQ C7 S3 S4 S7', 3, [
            deal('B6-QW', 'B6', N, "T.J765.9862.T865", S, "QJ9.T98.Q73.QJ94", '6S', AUC6B, 'CQ', "master trump West, DQ West (3 diamonds)", weight=15),
            deal('B6-QE', 'B6', N, "T.J765.Q862.T865", S, "QJ9.T98.973.QJ94", '6S', AUC6B, 'CQ', "master trump West, DQ East (4 diamonds)", weight=20),
        ])
add_set('B6m', 'tie', "Two-way queen, throw-in with the master trump, 6S (East-West hands exchanged)",
        "Mirror of B6: the master trump is with East.",
        SOUND_B, 'C2 CA SA S2 SK S5 CK C3 HA H2 HK H4 H3 HQ C7 S3 S4 S7', 3, [
            deal('B6m-QE', 'B6m', N, "QJ9.T98.Q73.QJ94", S, "T.J765.9862.T865", '6S', AUC6B, 'C5', "master trump East, DQ East (3 diamonds)", weight=15),
            deal('B6m-QW', 'B6m', N, "QJ9.T98.973.QJ94", S, "T.J765.Q862.T865", '6S', AUC6B, 'C5', "master trump East, DQ West (4 diamonds)", weight=20),
        ])

# ---- S6: K1042 opposite AJ5 with the club stopper knocked out at trick one. ----
N, S = "KQ872.A4.KT42.76", "AJT94.K32.AJ5.A5"
add_set('S6', 'strict', "Two-way queen where keeping the guess looks worth an overtrick, 6S",
        "K1042 opposite AJ5, club lead taking out the ace. If the queen is picked up and the suit runs, the fourth "
        "diamond takes care of the club and thirteen tricks make, so every card that keeps the guess averages above "
        "12 over the sampled layouts; the club exit concedes a trick and is exactly 12. On tricks or score the exit "
        "is strictly below the rest. A wrong view of the queen loses a diamond and a club.",
        "Win the club, draw trumps, cash the top hearts and ruff the third, exit with the club. The defender on lead "
        "must open diamonds or give a ruff and discard.",
        'C6 CA SA S2 S4 SK HA H2 H4 HK H3 S7 C7 C5', 3, [
            deal('S6-QW', 'S6', N, "3.8765.986.T8432", S, "65.QJT9.Q73.KQJ9", '6S', AUC6, 'CK', "DQ West, diamonds 3-3", weight=1),
            deal('S6-QE', 'S6', N, "3.8765.Q86.T8432", S, "65.QJT9.973.KQJ9", '6S', AUC6, 'CK', "DQ East, diamonds 3-3", weight=1),
        ])

N, S = "T872.Q42.KT4.K73", "AKQJ9.AK3.AJ5.A4"
AUC7 = ["2C", "PASS", "2D", "PASS", "2S", "PASS", "3S", "PASS", "4N", "PASS", "5C", "PASS", "7S", "PASS", "PASS", "PASS"]
# ---- G7: reference only, not a test. No sound line: how does the declarer guess, and when? ----
add_set('G7', 'guess', "Two-way queen in a grand slam with a full count available, 7S (reference, not scored)",
        "Nothing removes the guess. After trumps, hearts and clubs the count is complete: diamonds are 3-4, so the "
        "queen is 4:3 to be in the four-card hand. A declarer who guesses with that count makes G7-QE and fails "
        "G7-QW; one who guesses before the count is at even money on both.",
        "None. The percentage line is to take the count and play the four-card hand for the queen.",
        'C3 CA SA S2 SK S7', 2, [
            deal('G7-QW', 'G7', N, "43.T8765.9862.52", S, "65.J9.Q73.QJT986", '7S', AUC7, 'CQ', "DQ in the three-card hand (West)", weight=15),
            deal('G7-QE', 'G7', N, "43.T8765.Q862.52", S, "65.J9.973.QJT986", '7S', AUC7, 'CQ', "DQ in the four-card hand (East)", weight=20),
        ])

# ---- Controls: double dummy itself needs the endplay, or there is no guess left. ----
N, S = "KQ872.A4.Q42.A73", "AJT94.K3.J53.K64"
add_set('C1', 'control', "Frozen suit (Q42 opposite J53), strip and club exit, 4S",
        "Control. With the diamond honours split, leading the suit loses three tricks in it even double dummy, so the "
        "sampled layouts themselves show that the exit is needed. A search on double-dummy values should pass.",
        "As A6: draw trumps, cash hearts and top clubs, exit with the third club; the defenders must open diamonds or "
        "give a ruff and discard.",
        'H4 HK SA S2 S4 SK HA H3 C3 CK C4 CA C7 C6', 3, [
            deal('C1', 'C1', N, "3.87652.AT86.QT8", S, "65.QJT9.K97.J952", '4S', AUC4, 'HQ', "DK West, DA East", critical=[]),
        ])
N, S = "KQ872.A4.KT4.A73", "AJT94.K3.AJ5.K64"
add_set('L6', 'tie', "The A6 hands on a low diamond lead",
        "The lead comes round to the tenace. Low or the ten from dummy gives three diamond tricks whatever East does. "
        "The king is double-dummy equal to both and leaves the same guess as before.",
        "Play low (or the ten) from dummy and win as cheaply as possible in hand; then draw trumps and cash the other "
        "two top diamonds.",
        'D4', 0, [
            deal('L6-QW', 'L6', N, "3.87652.9862.QT8", S, "65.QJT9.Q73.J952", '6S', AUC6, 'D3', "DQ West (led from the queen)", weight=15),
            deal('L6-QE', 'L6', N, "3.87652.Q862.QT8", S, "65.QJT9.973.J952", '6S', AUC6, 'D3', "DQ East", weight=20),
        ])

if __name__ == '__main__':
    json.dump(dict(sets=list(SETS.values()), deals=DEALS), open('fusion_deals.json', 'w'), indent=1)
    print(len(SETS), 'sets', len(DEALS), 'deals')
