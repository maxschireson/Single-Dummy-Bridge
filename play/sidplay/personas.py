"""Sid's personalities at the play server (Max, 21:14 UTC on 14 November 2026: "Update Sid to randomize personalities").

Each board the three Sids get personas from the bundle source's bridge_harness/persona.py: North (your partner) one of
its own, East and West a partnership (each latent draw correlated 0.5 with the partner's). A persona is a card-play
style and a bidding style (bridge_harness/style.py, bid_style.py), how much of them the partner knows, and how much
of them the partner tells the opponents.

What each side may know (the "(to be publicly known) level of variability and disclosure"):
  - everyone: how personas are drawn (`public_lines`), and that every Sid is `SidVariable`;
  - you, as North's partner: North's styles at the strength its partner knows them (`describe(p, 'partner')`);
  - you, about East-West: what their partner says when asked (`describe(p, 'opponent')`);
  - the Sids: each other by the identifier `SidVariable`, never by persona (sidplay/engine.py).
After the board the actual styles are shown, since the next board draws new ones.

A board played again keeps its personas, so the comparison is with the same opponents.
"""
import logging

log = logging.getLogger('sidplay.personas')

try:
    from bridge_harness import persona as P
except Exception:           # a bundle source without personas: the server plays plain Sid
    P = None

SIDS = (0, 1, 3)            # North (your partner), East, West
NAMES = {0: 'North', 1: 'East', 3: 'West'}


def available():
    return P is not None


def draw(rng):
    """{seat: persona} for one board. rng: random.Random."""
    north = P.draw(rng)
    east, west = P.draw_partnership(rng)
    return {0: north, 1: east, 3: west}


def bid_style(personas, seat):
    p = (personas or {}).get(seat)
    return p['bid_style'] if p else None


def play_style(personas, seat):
    """{'play': style, 'near': margin} for an 8X seat (persona.PLAY_NEAR_X8), or None."""
    p = (personas or {}).get(seat)
    return {'play': p['play_style'], 'near': P.PLAY_NEAR_X8} if p else None


def told(personas):
    """What the person may know during the board: partner's styles as its partner knows them, and East-West as their
    partner describes them."""
    if not personas:
        return None
    return dict(N=P.describe(personas[0], 'partner'), E=P.describe(personas[1], 'opponent'),
                W=P.describe(personas[3], 'opponent'))


def full(personas):
    """The actual personas, for after the board: words and numbers."""
    if not personas:
        return None
    out = {}
    for seat, name in NAMES.items():
        p = personas[seat]
        out[name[0]] = dict(text=P.describe(p, 'full'), play=p['play_style'], bid=p['bid_style'],
                            knowledge=p['knowledge'], disclosure=p['disclosure'])
    return out


def public_lines(identifier='SidVariable'):
    """How personas are drawn, in a few lines anyone may read."""
    if P is None:
        return None
    pub = P.public(identifier)
    return [
        f'Every Sid here is {identifier}: each board, each Sid gets a personality drawn afresh.',
        f"Card play: {', '.join(pub['play']['dimensions'])}, each with a weight {pub['play']['weights'][:-14].replace('uniform', 'drawn uniformly')}; "
        f"a random choice {pub['play']['random'][0]:.0%} to {pub['play']['random'][1]:.0%} of the time; only among cards Sid "
        f'rates within {P.PLAY_NEAR_X8} tricks of its best.',
        f"Bidding: aggressive (more or less bidding) and shape (shape or high cards), each {pub['bid']['weights'][:-14].replace('uniform', 'drawn uniformly')}; "
        f"a random call {pub['bid']['random'][0]:.0%} to {pub['bid']['random'][1]:.0%} of the time; only among calls Sid rates "
        f"at least e^-{pub['bid']['near']:g} as likely as its best. About 0.24 IMP a board, double dummy.",
        'Partners: each knows 0 to 80% of the other’s style; asked by the opponents, a partner describes it at 0 to '
        '150% of what it knows (usually 75%). Partners’ personalities are correlated (0.5); opponents’ are independent.',
    ]


def to_json(personas):
    return {str(k): v for k, v in personas.items()} if personas else None


def from_json(d):
    return {int(k): v for k, v in d.items()} if d else None
