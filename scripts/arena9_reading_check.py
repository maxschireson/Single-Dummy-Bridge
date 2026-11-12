#!/usr/bin/env python3
"""G9-D6's release check on bid-only deals (g9, 12 Nov 11:57 UTC): item 6 of the arrival run needs no card play.

For each of --deals deals and both rooms: the auction as the bot's side and the guest bid it (the bot's bidder for
its side, the guest's package for the other), a random legal opening lead (and dummy's first card when the bot's side
defends), then arena9_pipeline.reading_gain from the bot's side, for the Gen 9 bot and for its control. The auction
is the same for both (they bid with the same net), so the difference is paired by deal. Two models of the guest:

  arrival   the model the registry stored at its submission, with no experience (the epoch it arrived in)
  snapshot  the model with the experience snapshot of a later epoch of the same control directory (default: the last)

Hidden hands are read only to score the true layout after the auction and the lead; nothing here plays a board.

    python scripts/arena9_reading_check.py --control RUN/control --players configs/players \\
        --capsule CAPSULE/recovery --deals 200 --out check.json
"""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness import arena9 as a9  # noqa: E402
from bridge_harness import arena9_pipeline as pl  # noqa: E402

THRESHOLDS = {'guest-b': dict(arrival=-0.45, snapshot=-0.15), 'guest-a': dict(arrival=3.0, snapshot=3.0)}


def cli_module():
    spec = importlib.util.spec_from_file_location('arena9_cli', ROOT / 'scripts' / 'arena9.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def stats(xs):
    n = len(xs)
    if n == 0:
        return dict(n=0, mean=None, se=None)
    m = sum(xs) / n
    se = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) / n) if n > 1 else None
    return dict(n=n, mean=round(m, 4), se=None if se is None else round(se, 4))


def tables_for(board, bot, guest, bidders, auction, rng):
    """{table: entry} for the two native rooms of one deal: the auction as the seats' packages bid it and three random
    legal cards (the lead, then up to the bot side's first decision; reading_gain stops before that decision's card)."""
    from bridge_harness.core import SEATS, Game, symbol
    out = {}
    for swapped in (0, 1):
        assignments = ['candidate' if s % 2 == swapped else 'opponent' for s in range(4)]
        native = [bot if r == 'candidate' else guest for r in assignments]
        b, _ = auction(board, [bidders[x] for x in native])
        if b.contract is None:
            continue
        game, actions = Game(b), []
        for _ in range(3):
            o = game.observation()
            c = int(rng.choice(o.legal))
            actions.append(dict(seat=SEATS[o.actor], card=symbol(c)))
            game.play(c)
        out[f'table-{swapped}'] = dict(board=b.to_dict(), assignments=assignments, tables=[dict(actions=actions)])
    return out


def summarise(rows, bot, control_bot):
    """{guest: {condition: {bot, control, difference, threshold, met}}} from per-deal rows (any number of shards)."""
    out = {}
    for guest in sorted({r['guest'] for r in rows}):
        rs = [r for r in rows if r['guest'] == guest]
        ctl = {r['deal']: r['gains'] for r in rs if r['who'] == control_bot}
        conds = sorted({r['condition'] for r in rs if r['who'] == bot})
        out[guest] = {}
        for c in conds:
            mine = {r['deal']: r['gains'] for r in rs if r['who'] == bot and r['condition'] == c}
            both = [k for k in sorted(mine) if mine[k] and ctl.get(k)]
            d = [sum(mine[k]) / len(mine[k]) - sum(ctl[k]) / len(ctl[k]) for k in both]
            t = THRESHOLDS.get(guest, {}).get(c)
            ds = stats(d)
            out[guest][c] = dict(epoch=next(r['epoch'] for r in rs if r['condition'] == c), bot=stats([x for k in both for x in mine[k]]),
                                 control=stats([x for k in both for x in ctl[k]]), difference=ds, threshold=t,
                                 met=None if t is None or ds['mean'] is None else bool(ds['mean'] > t),
                                 errors=sum(1 for r in rs if r.get('error') and r['condition'] in (c, 'any')))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--control', type=Path)
    ap.add_argument('--players', type=Path)
    ap.add_argument('--capsule', type=Path)
    ap.add_argument('--deals', type=int, default=200)
    ap.add_argument('--seed', type=int, default=9157)
    ap.add_argument('--bot', default='9a-32')
    ap.add_argument('--control-bot', default='8p-32')
    ap.add_argument('--snapshot-epoch', type=int, help='default: the last epoch manifest')
    ap.add_argument('--guests', nargs='*')
    ap.add_argument('--rows', type=Path, help='per-deal rows (jsonl), appended')
    ap.add_argument('--summarise', nargs='*', type=Path, help='only summarise these rows files')
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    if a.summarise:
        rows = [json.loads(l) for f in a.summarise for l in f.read_text().splitlines() if l.strip()]
        res = dict(schema='arena9-reading-check-v1', bot=a.bot, control_bot=a.control_bot, rows=len(rows),
                   guests=summarise(rows, a.bot, a.control_bot))
        text = json.dumps(res, indent=1) + '\n'
        print(text)
        if a.out:
            a.out.write_text(text)
        return
    A = cli_module()
    G = A._load_gen9_match()
    from bridge_harness import gen5_arena
    from bridge_harness import gen9 as engine
    pkgs = a9.load_packages(a.players)
    mb = A.MatchBackend(pkgs, a.capsule, control=a.control)
    log = a9.read_log(a.control)
    arrived = {e['player']: e['epoch'] for e in log if e['event'] == 'submit' and e.get('kind') == 'guest'}
    snap_n = a.snapshot_epoch or max(int(p.stem) for p in (a.control / 'epochs').glob('*.json'))
    rows = []
    sink = a.rows.open('a') if a.rows else None
    for guest in a.guests or sorted(arrived):
        conds = dict(arrival=arrived[guest], snapshot=snap_n)
        readers = {}
        for c, n in conds.items():
            m = json.loads(a9.epoch_path(a.control, n).read_text())
            man, _ = mb.manifest(m, f'{a.bot}~{guest}', a.seed)
            readers[c] = engine.player(man['bots'][a.bot], str(mb.capsule))
            if c == 'arrival':
                G.start(str(mb.capsule), man)              # the bidders: the bot's net and the guest's package
                bidders = dict(G.g8.STATE['bidders'])
                man8, _ = mb.manifest(m, f'{a.control_bot}~{guest}', a.seed)
                control_reader = engine.player(man8['bots'][a.control_bot], str(mb.capsule))   # no player model: one condition
        rng = np.random.default_rng([a.seed, sum(map(ord, guest))])
        started = time.time()
        for k in range(a.deals):
            tables = tables_for(G.deal(a.seed, k), a.bot, guest, bidders, gen5_arena.auction, rng)
            if not tables:
                continue
            for c, who, reader in [('any', a.control_bot, control_reader)] + [(c, a.bot, readers[c]) for c in conds]:
                rec = dict(candidate=who, opponent=guest, unique_tables=tables, bidding={f'native/{t[-1]}': dict(table=t) for t in tables})
                row = dict(guest=guest, deal=k, condition=c, who=who, epoch=conds.get(c), gains=[])
                try:
                    row['gains'] = [x['gain'] for x in pl.reading_gain(reader, rec, who, guest)]
                except Exception as e:                          # counted and reported, never hidden
                    row['error'] = f'{type(e).__name__}: {e}'[:300]
                rows.append(row)
                if sink:
                    sink.write(json.dumps(row) + '\n'); sink.flush()
            if k % 20 == 19:
                print(f'{guest}: {k + 1} deals, {time.time() - started:.0f}s', file=sys.stderr, flush=True)
    if sink:
        sink.close()
    res = dict(schema='arena9-reading-check-v1', control=str(a.control), deals=a.deals, seed=a.seed, bot=a.bot,
               control_bot=a.control_bot, snapshot_epoch=snap_n, guests=summarise(rows, a.bot, a.control_bot))
    text = json.dumps(res, indent=1) + '\n'
    print(text)
    if a.out:
        a.out.write_text(text)


if __name__ == '__main__':
    main()
