"""JSONL is lossless; PBN support covers deal/auction/contract/lead tags."""
from dataclasses import replace
import json
from pathlib import Path
import random
import re

from .core import Board, Contract, SEATS, auction_contract, card, hand_text, normalize_bid, parse_hand, symbol

VUL_CYCLE = ("None", "NS", "EW", "Both", "NS", "EW", "Both", "None",
             "EW", "Both", "None", "NS", "Both", "None", "NS", "EW")


def generate(count=1000, seed=1, family_size=1):
    """Synthetic contracts, explicitly not a realistic bidding distribution."""
    if count < 1 or family_size < 1:
        raise ValueError("Positive count and family size required")
    rng = random.Random(seed)
    base = None
    for i in range(count):
        group = i // family_size
        if i % family_size == 0:
            deck = list(range(52)); rng.shuffle(deck)
            base = tuple(tuple(sorted(deck[13*s:13*(s+1)])) for s in range(4))
        hands = base
        if family_size > 1:
            ew = list(base[1] + base[3]); rng.shuffle(ew)
            hands = (base[0], tuple(sorted(ew[:13])), base[2], tuple(sorted(ew[13:])))
        scenario = group if family_size > 1 else i
        strain = "NSHDC"[scenario % 5]
        level = (3 if strain == "N" else 4 if strain in "SH" else 5) if scenario % 3 else 2
        declarer = 2 if family_size > 1 else scenario % 4
        c = Contract(level, strain, declarer)
        yield Board(f"{i+1}", hands, c, scenario % 4, VUL_CYCLE[scenario % 16],
                    family=f"family-{group+1}" if family_size > 1 else None)


def load(path):
    p = Path(path)
    if p.suffix.lower() == ".pbn":
        return list(read_pbn(p.read_text()))
    return [Board.from_dict(json.loads(line)) for line in p.read_text().splitlines() if line.strip()]


def save(boards, path):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix.lower() == ".pbn":
        p.write_text("\n\n".join(write_pbn(b) for b in boards) + "\n")
    else:
        p.write_text("".join(json.dumps(b.to_dict(), sort_keys=True) + "\n" for b in boards))


def write_pbn(b):
    tags = dict(Board=b.id, Dealer=SEATS[b.dealer], Vulnerable=b.vulnerability,
                Deal="N:" + " ".join(hand_text(h) for h in b.hands),
                Declarer=SEATS[b.contract.declarer] if b.contract else "",
                Contract=b.contract.text() if b.contract else "Pass",
                AuctionSource=b.auction_source)
    if b.family:
        tags["Family"] = b.family
    if b.opening_lead is not None:
        tags["OpeningLead"] = symbol(b.opening_lead)
    return "\n".join(f'[{k} "{v}"]' for k, v in tags.items()) + \
        f'\n[Auction "{SEATS[b.dealer]}"]\n' + " ".join(b.bids)


def read_pbn(text):
    # Accept standard tags and comments. Reject unsupported partial deals.
    text = re.sub(r"\{.*?\}", "", text, flags=re.S)
    text = re.sub(r";[^\n]*", "", text)
    blocks = re.split(r'(?=\[Board\s+")', text)
    for block in blocks:
        tags = dict(re.findall(r'\[(\w+)\s+"([^"]*)"\]', block))
        if "Deal" not in tags:
            continue
        start, data = tags["Deal"].split(":", 1)
        hands = [None] * 4
        parsed = data.split()
        if len(parsed) != 4:
            raise ValueError("PBN requires four complete hands")
        for i, h in enumerate(parsed):
            hands[(SEATS.index(start) + i) % 4] = parse_hand(h)
        dealer = SEATS.index(tags.get("Dealer", tags.get("Auction", "N")))
        auction = ()
        match = re.search(r'\[Auction\s+"[NESW]"\]([^\[]*)', block, re.S)
        if match:
            calls = re.sub(r"=\d+=|\$\d+|[!*?]", "", match[1]).split()
            auction = tuple(calls)
        ct = tags.get("Contract", "")
        c = (None if ct.lower() == "pass" else Contract.parse(ct, SEATS.index(tags["Declarer"]))) if ct else auction_contract(dealer, auction)
        vul = {"All": "Both", "Love": "None", "-": "None", "NS": "NS", "EW": "EW", "N-S": "NS", "E-W": "EW"}.get(tags.get("Vulnerable", "None"), tags.get("Vulnerable", "None"))
        yield Board(tags.get("Board", "1"), tuple(hands), c, dealer, vul,
                    tuple(normalize_bid(x) for x in auction),
                    tags.get("Family"), card(tags["OpeningLead"]) if tags.get("OpeningLead") else None,
                    tags.get("AuctionSource", "imported"))


def freeze_auction(board, bidder):
    calls, transcript = [], []
    for i in range(320):
        seat = (board.dealer + i) % 4
        bid, details = bidder.bid(board.hands[seat], seat, board.dealer, board.vulnerability, calls)
        calls.append(bid)
        transcript.append({"seat": SEATS[seat], "bid": bid, **details})
        try:
            c = auction_contract(board.dealer, calls)
        except ValueError as e:
            if str(e) == "Incomplete auction":
                continue
            raise
        return replace(board, contract=c, auction=tuple(calls), opening_lead=None,
                       auction_source="BEN"), transcript
    raise RuntimeError("Auction exceeded legal call limit")
