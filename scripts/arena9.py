#!/usr/bin/env python3
"""One-machine epoch runner for the Gen 9 population arena (task G9-D4).

Gen 9 work in progress (dave). Not an arena cohort: nothing here is pooled into arena scores or
touches a feed, the registry on gh-pages or the dashboard. The library is bridge_harness/arena9.py.

  python scripts/arena9.py init --control DIR --players configs/players --rules configs/arena9/rules-v0.json --champion 6-32
  python scripts/arena9.py run  --control DIR --players configs/players --epochs 3 [--backend match --capsule CAPSULE/recovery --workers 2]
  python scripts/arena9.py status --control DIR
  python scripts/arena9.py queue --control DIR --event submit --player 5RZ32 --author max --authority "..."

`run` plays the current epoch, closes it (ratings, betting tests, admissions, retirements, the
people's queued events, an experience snapshot), opens the next and repeats. Nothing between two
epochs is done by hand: a person changes the arena only by queuing an event.

Backends: `sim` (synthetic boards from each package's `bundle.sim`; numpy only) and `match`
(real bots, fork-free, through scripts/gen9_match.py's machinery: the same run_board as the
collectors, `meet` once a board and `auction_by` before each table). A package's bundle for
`match` is a bot of the capsule plus overrides, in the --bots format of scripts/gen8_match.py.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness import arena9 as a9  # noqa: E402


def commit():
    try:
        return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


# ---- the match backend --------------------------------------------------------------------------

G9M = None
WORKER = {}


def _load_gen9_match():
    global G9M
    if G9M is None:
        spec = importlib.util.spec_from_file_location('gen9_match', ROOT / 'scripts' / 'gen9_match.py')
        G9M = importlib.util.module_from_spec(spec)
        sys.modules['gen9_match'] = G9M
        spec.loader.exec_module(G9M)
    return G9M


def _worker_start(source, manifest, ctx):
    _load_gen9_match().start(source, manifest)
    WORKER.update(source=source, m=manifest, **ctx)


def _worker_play(index, seed):
    """One board through the collectors' run_board, then what the pipeline needs from the finished record."""
    from bridge_harness import arena9_pipeline as pl
    from bridge_harness.gen5_arena import run_board
    G = _load_gen9_match()
    m, source = WORKER['m'], WORKER['source']
    started = time.process_time()
    board = G.deal(seed, index)
    r = run_board(source, m, board.to_dict(), index, G.g8.STATE['bidders'], player_factory=G.player)
    cpu = time.process_time() - started
    a = m['roster'][0]
    sign = 1 if r['candidate'] == a else -1
    row = dict(index=index, family=r['family'], candidate=r['candidate'], opponent=r['opponent'], cpu=round(cpu, 2),
               tables=len(r['unique_tables']), contract=r['board'].get('contract'), trace=pl.trace(r), manifest_identity=m['identity'],
               completed_epoch=time.time(), backend='match')
    for regime, v in r['regimes'].items():
        row[regime] = None if v['imps'] is None else sign * v['imps']
    if WORKER.get('experience'):
        row['envelopes'] = pl.board_envelopes(r, f"{WORKER['epoch_id'][:16]}/{WORKER['pair']}/{index}", WORKER['models'], WORKER['declared'],
                                              WORKER['pair'], row['completed_epoch'], root=str(ROOT))
    return row


class MatchBackend:
    """Real bots through gen9_match: one single-pair manifest (forks off) per pair, as scripts/gen8_match.py builds it.
    A Gen 9 bot whose package asks for it (`bundle.epoch_models`) is handed every rostered player's model with the epoch's
    experience snapshot; each finished board's experience envelopes come back with its row."""

    def __init__(self, packages, capsule, control=None, experience=True):
        self.packages, self.capsule, self.control = packages, Path(capsule).resolve(), Path(control) if control else None
        self.experience = experience
        bots = json.loads((self.capsule / 'manifest.json').read_text())['bots']
        for pid, p in packages.items():           # a package names its nets by hash: the capsule's bot must be those nets
            b = p['bundle']
            if b.get('source') != 'capsule':
                continue
            want = {k: v for k, v in (b.get('artifact_sha256') or {}).items() if k in bots[b['bot']].get('artifact_sha256', {})}
            have = {k: bots[b['bot']]['artifact_sha256'][k] for k in want}
            if want != have:
                raise ValueError(f'{pid}: the capsule bot {b["bot"]} is not the nets the package names')

    def models(self, m):
        from bridge_harness import arena9_pipeline as pl
        from bridge_harness import experience_store as xs
        snap = xs.load_snapshot(self.control / 'snapshots' / f"{m['experience_snapshot']}.json.gz")
        return pl.table_models(m, snap)

    def bots_file(self, pair, models=None):
        bots = {}
        for pid in set(pair.split('~')):
            b = self.packages[pid]['bundle']
            if b.get('source') != 'capsule':
                raise ValueError(f'{pid}: the match backend plays capsule bots')
            if b.get('overrides') or b.get('bot') != pid:
                entry = dict(deepcopy(b.get('overrides') or {}), base=b['bot'])
                if b.get('epoch_models') and models is not None:
                    g9 = entry.setdefault('gen9', {})
                    g9['models'] = dict(g9.get('models') or {}, **models)
                bots[pid] = entry
        f = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
        json.dump(bots, f)
        f.close()
        return f.name

    def manifest(self, m, pair, seed):
        from bridge_harness.training import digest
        g8 = _load_gen9_match().g8
        models = self.models(m) if self.control else None
        man = g8.build_manifest(self.capsule, self.bots_file(pair, models), pair, seed)
        a, b = pair.split('~')
        if a == b:              # self-play: run_board wants two distinct roster ids; the second (the audit reference) never sits
            man['roster'] = [a, man['audit_references'][a]]
        man['arena_epoch'], man['arena_epoch_id'], man['experience_snapshot'] = m['epoch'], m['id'], m['experience_snapshot']
        man.pop('identity', None)
        man['identity'] = digest(man)
        return man, models

    def play(self, m, pair, indices, seed, workers=1):
        from bridge_harness import arena9_pipeline as pl
        man, models = self.manifest(m, pair, seed)
        ctx = dict(epoch_id=m['id'], pair=pair, models=models or {}, declared=pl.declared_map(self.packages, ROOT), experience=self.experience)
        with ProcessPoolExecutor(workers, initializer=_worker_start, initargs=(str(self.capsule), man, ctx)) as pool:
            for idx, row in zip(indices, pool.map(_worker_play, indices, [seed] * len(indices))):
                yield idx, row


def arrival_hook(control):
    from bridge_harness import arena9_pipeline as pl
    distances = pl.Distances(ROOT, cache=Path(control) / 'distances')
    return lambda package: pl.arrival_model(package, ROOT, distances)


def replay(control, packages, capsule, epoch, k, slot=0):
    """Play one recorded board again from its epoch's manifest and the snapshot it names; compare the trace."""
    m = json.loads(a9.epoch_path(control, epoch).read_text())
    rows = [json.loads(l) for l in (Path(control) / 'results' / f'e{epoch:04d}' / f'slot{slot}.jsonl').read_text().splitlines() if l.strip()]
    row = next(r for r in rows if r['k'] == k)
    backend = MatchBackend(packages, capsule, control, experience=False)
    (idx, again), = list(backend.play(m, row['pair'], [row['index']], m['deals']['seed'], workers=1))
    same = again['trace'] == row['trace'] and again['manifest_identity'] == row['manifest_identity']
    return dict(epoch=epoch, k=k, pair=row['pair'], index=row['index'], snapshot=m['experience_snapshot'], recorded=row['trace'],
                replayed=again['trace'], manifest_recorded=row['manifest_identity'], manifest_replayed=again['manifest_identity'],
                common=(row.get('common'), again.get('common')), native=(row.get('native'), again.get('native')), same=same)


# ---- commands ------------------------------------------------------------------------------------

def status(control):
    m = a9.current(control)
    st = a9.fold(a9.read_log(control))
    lines = [f"epoch {m['epoch']} ({m['id'][:12]}), champion {m['champion']}, {m['end']['boards']} boards, snapshot {m['experience_snapshot'][:12]}"]
    for p, s in sorted(st.items()):
        lines.append(f"  {p:12s} {s['status']:9s}{' protected' if s['protected'] else ''}{' test vs ' + s['test']['champion'] if s['test'] else ''}")
    lines.append('  pairs: ' + ', '.join(f'{p} x{w}' for p, w in m['schedule']['pair_weights'].items()))
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('init'); p.add_argument('--control', type=Path, required=True); p.add_argument('--players', type=Path, required=True)
    p.add_argument('--rules', type=Path, required=True); p.add_argument('--champion', required=True)
    p.add_argument('--only', nargs='*', help='players to submit now (default: every package)')
    p.add_argument('--author', default='dave'); p.add_argument('--authority', default='G9-D4 demonstration')
    p.add_argument('--no-arrival', action='store_true', help='do not compute first models (sim packages)')
    p = sub.add_parser('run'); p.add_argument('--control', type=Path, required=True); p.add_argument('--players', type=Path, required=True)
    p.add_argument('--epochs', type=int, default=1); p.add_argument('--backend', choices=['sim', 'match'], default='sim')
    p.add_argument('--capsule', type=Path); p.add_argument('--workers', type=int, default=os.cpu_count() or 1); p.add_argument('--slot', type=int, default=0)
    p = sub.add_parser('status'); p.add_argument('--control', type=Path, required=True)
    p = sub.add_parser('experience'); p.add_argument('--control', type=Path, required=True); p.add_argument('--players', type=Path, required=True)
    p.add_argument('--epoch', type=int, required=True); p.add_argument('--reader', default='9a-32')
    p = sub.add_parser('replay'); p.add_argument('--control', type=Path, required=True); p.add_argument('--players', type=Path, required=True)
    p.add_argument('--capsule', type=Path, required=True); p.add_argument('--epoch', type=int, required=True); p.add_argument('--k', type=int, required=True)
    p.add_argument('--slot', type=int, default=0)
    p = sub.add_parser('queue'); p.add_argument('--control', type=Path, required=True); p.add_argument('--event', required=True)
    p.add_argument('--player', required=True); p.add_argument('--author', required=True); p.add_argument('--authority', required=True)
    a = ap.parse_args()
    if a.cmd == 'init':
        pkgs = a9.load_packages(a.players)
        if a.only:
            pkgs = {k: v for k, v in pkgs.items() if k in a.only}
        m = a9.init(a.control, pkgs, json.loads(a.rules.read_text()), a.champion, a.author, a.authority,
                    arrival=None if a.no_arrival else arrival_hook(a.control))
        print(status(a.control))
    elif a.cmd == 'queue':
        e = a9.event(a.event, a.player, a.author, a.authority)
        path = a.control / 'queue' / f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{a.event}-{a.player}.json"
        path.write_text(json.dumps(e, indent=1))
        print(f'queued {path}')
    elif a.cmd == 'status':
        print(status(a.control))
    elif a.cmd == 'experience':
        from bridge_harness import arena9_pipeline as pl
        pk = a9.load_packages(a.players)
        spec = (pk[a.reader]['bundle'].get('overrides') or {}) if a.reader in pk else {}
        print(json.dumps(pl.epoch_experience(a.control, a.epoch, spec), indent=1))
    elif a.cmd == 'replay':
        print(json.dumps(replay(a.control, a9.load_packages(a.players), a.capsule, a.epoch, a.k, a.slot), indent=1))
    else:
        pkgs = a9.load_packages(a.players)
        backend = a9.SimBackend(pkgs) if a.backend == 'sim' else MatchBackend(pkgs, a.capsule, a.control)
        hook = None if a.backend == 'sim' else arrival_hook(a.control)
        for _ in range(a.epochs):
            m = a9.current(a.control)
            t = time.time()
            a9.play_epoch(a.control, backend, slot=a.slot, workers=a.workers)
            nxt, decisions = a9.close_epoch(a.control, pkgs, source_commit=commit(), arrival=hook)
            print(f"epoch {m['epoch']} played in {time.time() - t:.0f}s; decisions: {json.dumps(decisions, default=str)[:600]}")
            print(status(a.control))


if __name__ == '__main__':
    main()
