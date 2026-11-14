#!/usr/bin/env python3
"""Bots' tables on the USBC deals scored exactly as the humans' are (lost_tricks.py's own code), for analyze.py.

  python3 bot_lost_tricks.py RUN_DIR OUT.lt2.json.gz [--tables TABLES.jsonl] [--label NAME]

RUN_DIR is a gen8_match / x8_match run with --episodes on a deal file of make_tests.py. Each recorded table is turned
into the events lost_tricks.py reads (the deal, the contract, every card), so a bot's card is rated by the same double-
dummy code as a human's. The players' names are the bots' ids. With --tables (make_tests.py's tables.jsonl, or its fit or
sample file) each row also carries the human table it was played from (session, board, room, event) for pairing.
TEST DATA ONLY.
"""
import argparse, glob, gzip, json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2]))
import lost_tricks as LT                                    # noqa: E402
from bridge_harness.core import Board, card                # noqa: E402

SEATS = 'NESW'
RANKS = '23456789TJQKA'
VUL_BACK = {'None': 'NONE', 'NS': 'NORTH_SOUTH', 'EW': 'EAST_WEST', 'Both': 'BOTH'}


def hand_text(cards):
    return ', '.join(''.join(RANKS[c % 13] for c in sorted((c for c in cards if c // 13 == s), reverse=True)) for s in range(4))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('--tables')
    ap.add_argument('--label', default='')
    a = ap.parse_args()
    human = {}
    if a.tables:
        for line in open(a.tables):
            r = json.loads(line)
            human[r.get('sample_index', r.get('fit_index', r['index']))] = r
    out = []
    for f in sorted(glob.glob(str(a.run / 'episodes' / '*.json.gz'))):
        index = int(os.path.basename(f).split('.')[0])
        d = json.load(gzip.open(f, 'rt'))
        who = {'candidate': d['candidate'], 'opponent': d['opponent']}
        for e in d['unique_tables'].values():
            if e.get('schema_version') == 'v4-passed-out-v1' or not e.get('tables'):
                continue
            board = Board.from_dict(e['board'])
            c = board.contract
            if c is None:
                continue
            for ti, t in enumerate(e['tables']):
                if t.get('depth', 0) or t.get('fork_kind'):
                    continue
                names = {}
                events = [dict(tt='FULL', payload=dict(bd={SEATS[s]: hand_text(board.hands[s]) for s in range(4)}, room=f'T{ti}', ps={}, tname=a.label))]
                events.append(dict(tt='END_AUCTION', payload=dict(suit=c.strain, level=c.level, dec=SEATS[c.declarer],
                                                                  mod={0: '', 1: 'D', 2: 'R'}[c.doubled], **{'pass': 'f'})))
                for act in t['actions']:
                    seat = act['seat'] if isinstance(act['seat'], str) else SEATS[act['seat']]
                    names.setdefault(seat, who.get(act.get('player') or act.get('role'), '?'))
                    x = card(act['card'])
                    events.append(dict(tt='PLAY_CARD', payload=dict(c=f'{seat}{"SHDC"[x // 13]}{x % 13 + 2}')))
                events[0]['payload']['ps'] = {s: dict(name=n, playerId=n) for s, n in names.items()}
                r = LT.one_table(f'bots:{a.run.name}', dict(namePlus=a.label or a.run.name), None, dict(board=index, events=events),
                                 board.vulnerability)
                if not r or 'error' in r:
                    continue
                h = human.get(index)
                if h:
                    r.update(human_sid=h['sid'], human_board=h['board'], human_room=h['room'], event=h.get('event'), start=h.get('start'),
                             text=f"{h.get('event')} bots {a.label}")
                r['run'] = a.run.name
                out.append(r)
    with gzip.open(a.out, 'wt') as f:
        for r in out:
            f.write(json.dumps(r, separators=(',', ':')) + '\n')
    print(f'{len(out)} tables -> {a.out}')


if __name__ == '__main__':
    main()
