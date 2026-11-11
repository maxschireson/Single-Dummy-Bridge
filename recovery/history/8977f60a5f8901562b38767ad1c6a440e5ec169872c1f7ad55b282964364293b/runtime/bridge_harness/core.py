from __future__ import annotations

from dataclasses import dataclass, replace
import re

SUITS = "SHDC"
RANKS = "23456789TJQKA"
SEATS = "NESW"


def card(text: str) -> int:
    text = text.upper()
    if len(text) != 2 or text[0] not in SUITS or text[1] not in RANKS:
        raise ValueError(f"Invalid card: {text!r}")
    return 13 * SUITS.index(text[0]) + RANKS.index(text[1])


def symbol(c: int) -> str:
    return SUITS[c // 13] + RANKS[c % 13]


def hand_text(hand) -> str:
    return ".".join("".join(RANKS[c % 13] for c in sorted(hand, reverse=True)
                            if c // 13 == s) for s in range(4))


def parse_hand(text: str) -> tuple[int, ...]:
    suits = text.upper().split(".")
    if len(suits) != 4:
        raise ValueError("A hand requires four dot-separated suits")
    result = tuple(sorted(card(SUITS[s] + r) for s, ranks in enumerate(suits)
                          for r in ranks if r != "-"))
    if len(set(result)) != len(result):
        raise ValueError("Duplicate card in hand")
    return result


@dataclass(frozen=True)
class Contract:
    level: int
    strain: str
    declarer: int
    doubled: int = 0

    def __post_init__(self):
        if not (1 <= self.level <= 7 and self.strain in (*SUITS, "N")
                and 0 <= self.declarer < 4 and self.doubled in (0, 1, 2)):
            raise ValueError("Invalid contract")

    @property
    def trump(self):
        return SUITS.index(self.strain) if self.strain != "N" else 4

    @property
    def dummy(self):
        return (self.declarer + 2) % 4

    def text(self):
        return f"{self.level}{self.strain}{'X' * self.doubled}"

    @classmethod
    def parse(cls, text, declarer):
        m = re.fullmatch(r"([1-7])(NT|[SHDCN])(XX|X)?", text.upper())
        if not m:
            raise ValueError(f"Invalid contract: {text}")
        return cls(int(m[1]), m[2].replace("NT", "N"), declarer, len(m[3] or ""))


def normalize_bid(bid):
    b = bid.strip().upper().replace("NT", "N")
    return {"P": "PASS", "--": "PASS", "DB": "X", "RD": "XX"}.get(b, b)


def auction_contract(dealer: int, bids) -> Contract | None:
    """Validate a completed auction, including doubles, redoubles and declarer."""
    bids = tuple(map(normalize_bid, bids))
    last = None
    last_seat = None
    doubled = passes = 0
    first = {}
    ended = False
    for i, b in enumerate(bids):
        if ended:
            raise ValueError("Call after auction ended")
        seat = (dealer + i) % 4
        if b == "PASS":
            passes += 1
        elif b in ("X", "XX"):
            if last is None or (b == "X" and (doubled != 0 or seat % 2 == last_seat % 2)) \
                    or (b == "XX" and (doubled != 1 or seat % 2 != last_seat % 2)):
                raise ValueError("Illegal double/redouble")
            doubled = 1 if b == "X" else 2
            passes = 0
        else:
            if not re.fullmatch(r"[1-7][CDHSN]", b):
                raise ValueError(f"Invalid bid: {b}")
            order = (int(b[0]) - 1) * 5 + "CDHSN".index(b[1])
            if last is not None and order <= last:
                raise ValueError("Insufficient bid")
            first.setdefault((seat % 2, b[1]), seat)
            last, last_seat, doubled, passes = order, seat, 0, 0
        ended = passes >= (4 if last is None else 3)
    if not ended:
        raise ValueError("Incomplete auction")
    if last is None:
        return None
    strain = "CDHSN"[last % 5]
    return Contract(last // 5 + 1, strain, first[(last_seat % 2, strain)], doubled)


def synthetic_auction(dealer, contract):
    if contract is None:
        return ("PASS",) * 4
    bids = ["PASS"] * ((contract.declarer - dealer) % 4)
    bids.append(f"{contract.level}{contract.strain}")
    if contract.doubled:
        bids.append("X")
    if contract.doubled == 2:
        bids.append("XX")
    return tuple(bids + ["PASS"] * 3)


@dataclass(frozen=True)
class Board:
    id: str
    hands: tuple[tuple[int, ...], ...]
    contract: Contract | None
    dealer: int = 0
    vulnerability: str = "None"
    auction: tuple[str, ...] = ()
    family: str | None = None
    opening_lead: int | None = None
    auction_source: str = "synthetic"

    def __post_init__(self):
        if len(self.hands) != 4 or any(len(h) != 13 for h in self.hands) \
                or set(sum(self.hands, ())) != set(range(52)):
            raise ValueError("Deal must partition all 52 cards into four 13-card hands")
        if self.vulnerability not in ("None", "NS", "EW", "Both") or self.dealer not in range(4):
            raise ValueError("Invalid board metadata")
        if self.auction and auction_contract(self.dealer, self.auction) != self.contract:
            raise ValueError("Auction and contract disagree")
        if self.opening_lead is not None and (self.contract is None or
                self.opening_lead not in self.hands[(self.contract.declarer + 1) % 4]):
            raise ValueError("Invalid opening lead")

    @property
    def bids(self):
        return self.auction or synthetic_auction(self.dealer, self.contract)

    def to_dict(self):
        return dict(id=self.id, hands=[hand_text(h) for h in self.hands],
                    contract=self.contract.text() if self.contract else None,
                    declarer=SEATS[self.contract.declarer] if self.contract else None,
                    dealer=SEATS[self.dealer], vulnerability=self.vulnerability,
                    auction=list(self.bids), auction_source=self.auction_source,
                    family=self.family, opening_lead=symbol(self.opening_lead)
                    if self.opening_lead is not None else None)

    @classmethod
    def from_dict(cls, d):
        c = Contract.parse(d["contract"], SEATS.index(d["declarer"])) if d.get("contract") else None
        return cls(str(d["id"]), tuple(parse_hand(h) for h in d["hands"]), c,
                   SEATS.index(d.get("dealer", "N")), d.get("vulnerability", "None"),
                   tuple(d.get("auction", ())), d.get("family"),
                   card(d["opening_lead"]) if d.get("opening_lead") else None,
                   d.get("auction_source", "imported"))


def vulnerable(vul, seat):
    return vul == "Both" or vul == ("NS" if seat % 2 == 0 else "EW")


def score(contract: Contract, tricks: int, vul: bool) -> int:
    """Duplicate score from declarer's perspective."""
    made = tricks - contract.level - 6
    factor = 2 ** contract.doubled
    if made < 0:
        down = -made
        if not contract.doubled:
            return -down * (100 if vul else 50)
        penalty = (200 + 300 * (down - 1)) if vul else (100 + 200 * min(2, down - 1) + 300 * max(0, down - 3))
        return -penalty * (2 if contract.doubled == 2 else 1)
    unit = 20 if contract.strain in "CD" else 30
    base = (contract.level * unit + (10 if contract.strain == "N" else 0)) * factor
    bonus = ((500 if vul else 300) if base >= 100 else 50)
    if contract.level == 6:
        bonus += 750 if vul else 500
    if contract.level == 7:
        bonus += 1500 if vul else 1000
    if contract.doubled:
        bonus += 50 * (factor // 2)
        over = made * (200 if vul else 100) * (factor // 2)
    else:
        over = made * unit
    return base + bonus + over


IMP_LIMITS = (20, 50, 90, 130, 170, 220, 270, 320, 370, 430, 500, 600,
              750, 900, 1100, 1300, 1500, 1750, 2000, 2250, 2500, 3000, 3500, 4000)


def imps(difference):
    return (1 if difference >= 0 else -1) * sum(abs(difference) >= x for x in IMP_LIMITS)


def winner(trick, trump):
    led = trick[0][1] // 13
    return max(trick, key=lambda sc: (2 if sc[1] // 13 == trump else
                                     1 if sc[1] // 13 == led else 0, sc[1] % 13))[0]


@dataclass(frozen=True)
class Observation:
    """Capability boundary: contains no board object, hidden cards or deal seed."""
    controller: int
    actor: int
    known_hands: tuple[tuple[int, ...] | None, ...]
    legal: tuple[int, ...]
    history: tuple[tuple[int, int], ...]
    trick: tuple[tuple[int, int], ...]
    leader: int
    contract: Contract
    dealer: int
    vulnerability: str
    auction: tuple[str, ...]
    declarer_tricks: int

    def original_hand(self, seat):
        if self.known_hands[seat] is None:
            raise ValueError("Hand is not visible")
        return tuple(sorted(self.known_hands[seat] + tuple(c for s, c in self.history if s == seat)))


class Game:
    def __init__(self, board: Board):
        self.board = board
        self.hands = [set(h) for h in board.hands]
        self.history = []
        self.trick = []
        self.leader = (board.contract.declarer + 1) % 4 if board.contract else 0
        self.declarer_tricks = 0

    @property
    def done(self):
        return self.board.contract is None or len(self.history) == 52

    @property
    def actor(self):
        return (self.leader + len(self.trick)) % 4

    def observation(self):
        if self.done:
            raise ValueError("Game already finished")
        c = self.board.contract
        actor = self.actor
        controller = c.declarer if actor == c.dummy else actor
        known = [None] * 4
        known[controller] = tuple(sorted(self.hands[controller]))
        if self.history:
            known[c.dummy] = tuple(sorted(self.hands[c.dummy]))
        hand = sorted(self.hands[actor])
        follow = [x for x in hand if x // 13 == self.trick[0][1] // 13] if self.trick else []
        return Observation(controller, actor, tuple(known), tuple(follow or hand),
                           tuple(self.history), tuple(self.trick), self.leader, c,
                           self.board.dealer, self.board.vulnerability, self.board.bids,
                           self.declarer_tricks)

    def play(self, c):
        o = self.observation()
        if c not in o.legal:
            raise ValueError(f"Illegal card {symbol(c)} by {SEATS[o.actor]}")
        self.hands[o.actor].remove(c)
        self.history.append((o.actor, c))
        self.trick.append((o.actor, c))
        if len(self.trick) == 4:
            self.leader = winner(self.trick, o.contract.trump)
            self.declarer_tricks += self.leader % 2 == o.contract.declarer % 2
            self.trick = []

    def ns_score(self):
        c = self.board.contract
        if not self.done:
            raise ValueError("Cannot score an unfinished board")
        return 0 if c is None else score(c, self.declarer_tricks, vulnerable(self.board.vulnerability, c.declarer)) * (1 if c.declarer % 2 == 0 else -1)
