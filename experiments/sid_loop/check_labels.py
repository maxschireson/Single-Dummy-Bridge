"""Checks of the label builder against independent code (SPEC.md 5.5).

  python check_labels.py EPISODES_DIR --cells BIN --sure BIN --scorer FILE [--limit N] [--cards 7] [--brute 4]

1. Declaring rows: `guar` for each target equals sure_cpp's answer through bridge_harness.x8_claims.Finder.root, which
   builds its position from the Observation (the builder builds it from the game state).
2. Defender rows: `guar` at the contract equals Finder.handovers on the true hands.
3. Every table whose declaring side played a `guar` (contract) card at each of its labelled decisions from the first
   such row on made its contract.
4. cert <= single <= 1, guar <= cert, on every labelled entry; floor <= ceil.
5. With --brute K: on rows with K cards or fewer, `single` and `guar` of declaring rows against a brute-force search
   over explicit layouts (celllib.Brute), and the same for the value with a defender on lead.
"""
import argparse
import gzip
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sidlabel as S                                                        # noqa: E402
from celllib import Brute, cards_of, enumerate_cells, layouts_of           # noqa: E402
from bridge_harness.core import Board, Game, card                          # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument('episodes', type=Path)
    p.add_argument('--cells', required=True)
    p.add_argument('--sure', required=True)
    p.add_argument('--scorer', required=True)
    p.add_argument('--limit', type=int, default=20)
    p.add_argument('--cards', type=int, default=7)
    p.add_argument('--brute', type=int, default=0)
    a = p.parse_args()
    os.environ['SURE_BIN'] = a.sure
    from bridge_harness import x8_claims as X
    finder = X.Finder(a.sure, each=30.)
    L = S.Labeller(a.cells, a.scorer, cards=a.cards)
    n = dict(episodes=0, rows=0, decl_cards=0, decl_diff=0, decl_unknown=0, def_cards=0, def_diff=0, def_unknown=0, tables_kept=0,
             tables_kept_down=0, order_bad=0, brute_single=0, brute_single_diff=0, brute_guar=0, brute_guar_diff=0)
    for f in sorted(a.episodes.glob('*.json.gz'))[:a.limit]:
        d = json.load(gzip.open(f, 'rt'))
        rows = dict(L.episode(d))
        n['episodes'] += 1
        for ei, e in enumerate(d['unique_tables'].values()):
            if e.get('schema_version') == 'v4-passed-out-v1':
                continue
            board = Board.from_dict(e['board'])
            c = board.contract
            side = c.declarer % 2
            for ti, table in enumerate(e['tables']):
                game = Game(board)
                kept, started = True, False
                for ai, act in enumerate(table['actions']):
                    x = card(act['card'])
                    r = rows.get((ei, ti, ai))
                    if r is not None:
                        n['rows'] += 1
                        o = game.observation()
                        assert sorted(o.legal) == r['legal']
                        for i in range(len(r['legal'])):
                            for t in range(3):
                                g, s_, ce = r['guar'][i][t], r['single'][i][t], r['cert'][i][t]
                                fl, cl = r['floor'][i][t], r['ceil'][i][t]
                                if (g == 1 and ce == 0) or (s_ == 0 and ce == 1) or (g == 1 and s_ == 0) or \
                                        (fl is not None and cl is not None and fl > cl + 1e-9):
                                    n['order_bad'] += 1
                        if r['role'] == S.DECLARING:
                            for t, j in enumerate(S.TARGETS):
                                state, sure = finder.root(o, need=r['need'][t])
                                for i, y in enumerate(r['legal']):
                                    mine = r['guar'][i][t]
                                    if state == 'unknown' or mine < 0:
                                        n['decl_unknown'] += 1
                                        continue
                                    theirs = 1 if state == 'made' else 0 if state == 'lost' else int(sure[y])
                                    n['decl_cards'] += 1
                                    if theirs != mine:
                                        n['decl_diff'] += 1
                                        if n['decl_diff'] <= 5:
                                            print('DECL DIFF', f.name[:12], (ei, ti, ai), 'card', y, 'target', j, 'need', r['need'][t], 'mine', mine, 'sure_cpp', theirs, state)
                            if started or any(r['guar'][i][1] == 1 for i in range(len(r['legal']))):
                                played = r['guar'][r['legal'].index(x)][1]
                                if not started:
                                    started = True
                                if played != 1:
                                    kept = False
                            if a.brute and r['held'] <= a.brute:
                                brute_decl(L, board, game, r, n)
                        else:
                            world = [sorted(h) for h in game.hands]
                            got = finder.handovers(o, [world], r['legal'], allowance=60.)[0]
                            for i, y in enumerate(r['legal']):
                                mine = r['guar'][i][1]
                                if got[i] < 0 or mine < 0:
                                    n['def_unknown'] += 1
                                    continue
                                n['def_cards'] += 1
                                if int(got[i]) != mine:
                                    n['def_diff'] += 1
                                    if n['def_diff'] <= 5:
                                        print('DEF DIFF', f.name[:12], (ei, ti, ai), 'card', y, 'mine', mine, 'handover', int(got[i]))
                    game.play(x)
                if started and kept:
                    n['tables_kept'] += 1
                    if table['declarer_tricks'] < c.level + 6:
                        n['tables_kept_down'] += 1
                        print('KEPT AND DOWN', f.name[:12], (ei, ti))
    print(json.dumps(n))
    L.close()


def brute_decl(L, board, game, r, n):
    """`guar` and `single` of a declaring row with few cards against brute force over explicit layouts."""
    voids = L.show_outs(game.history)
    pos, east = L.view(board, game.hands, game.trick, game.leader, voids)
    cells = enumerate_cells(pos['pool'], pos['cE'], pos['cW'], pos['vE'], pos['vW'], 0)
    every = layouts_of([(eu, pin) for eu, pin, _ in cells], pos['pool'])
    from celllib import cell_of
    true_cell = cell_of(east, pos['pool'])
    own = layouts_of([true_cell], pos['pool'])
    seat = (pos['leader'] + len(pos['trick'])) & 3
    b = Brute(pos['trump'])
    for i, y in enumerate(r['legal']):
        hN, hS = (pos['hN'] ^ (1 << y), pos['hS']) if seat == 0 else (pos['hN'], pos['hS'] ^ (1 << y))
        for t in range(3):
            nd = r['need'][t]
            for name, lays in (('guar', every), ('single', own)):
                mine = r[name][i][t]
                if mine < 0:
                    continue
                v = b._after(hN, hS, pos['pool'], frozenset(lays), pos['leader'], tuple(pos['trick']) + (y,))
                n['brute_' + name] += 1
                if int(v >= nd) != mine:
                    n['brute_' + name + '_diff'] += 1
                    if n['brute_' + name + '_diff'] <= 5:
                        print('BRUTE DIFF', name, 'card', y, 'need', nd, 'mine', mine, 'brute value', v)


if __name__ == '__main__':
    main()
