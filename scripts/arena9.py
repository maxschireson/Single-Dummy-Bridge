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


def _load_gen9_match():
    global G9M
    if G9M is None:
        spec = importlib.util.spec_from_file_location('gen9_match', ROOT / 'scripts' / 'gen9_match.py')
        G9M = importlib.util.module_from_spec(spec)
        sys.modules['gen9_match'] = G9M
        spec.loader.exec_module(G9M)
    return G9M


def _worker_start(source, manifest):
    _load_gen9_match().g8.start(source, manifest)


def _worker_play(index, seed):
    return _load_gen9_match().g8.play(index, seed, None)


class MatchBackend:
    """Real bots through gen9_match: one single-pair manifest (forks off) per pair, as scripts/gen8_match.py builds it."""

    def __init__(self, packages, capsule):
        self.packages, self.capsule = packages, Path(capsule).resolve()
        bots = json.loads((self.capsule / 'manifest.json').read_text())['bots']
        for pid, p in packages.items():           # a package names its nets by hash: the capsule's bot must be those nets
            b = p['bundle']
            if b.get('source') != 'capsule':
                continue
            want = {k: v for k, v in (b.get('artifact_sha256') or {}).items() if k in bots[b['bot']].get('artifact_sha256', {})}
            have = {k: bots[b['bot']]['artifact_sha256'][k] for k in want}
            if want != have:
                raise ValueError(f'{pid}: the capsule bot {b["bot"]} is not the nets the package names')

    def bots_file(self, pair):
        bots = {}
        for pid in set(pair.split('~')):
            b = self.packages[pid]['bundle']
            if b.get('source') != 'capsule':
                raise ValueError(f'{pid}: the match backend plays capsule bots')
            if b.get('overrides') or b.get('bot') != pid:
                bots[pid] = dict(b.get('overrides') or {}, base=b['bot'])
        f = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
        json.dump(bots, f)
        f.close()
        return f.name

    def play(self, m, pair, indices, seed, workers=1):
        g8 = _load_gen9_match().g8
        a, b = pair.split('~')
        man = g8.build_manifest(self.capsule, self.bots_file(pair), pair, seed)
        if a == b:              # self-play: run_board wants two distinct roster ids; the second (the audit reference) never sits
            from bridge_harness.training import digest
            man['roster'] = [a, man['audit_references'][a]]
            man.pop('identity'); man['identity'] = digest(man)
        with ProcessPoolExecutor(workers, initializer=_worker_start, initargs=(str(self.capsule), man)) as pool:
            for idx, row in zip(indices, pool.map(_worker_play, indices, [seed] * len(indices))):
                yield idx, dict(index=idx, family=row['family'], candidate=row['candidate'], opponent=row['opponent'],
                                common=row.get('common'), native=row.get('native'), cpu=row.get('cpu'),
                                contract=row.get('contract'), completed_epoch=time.time(), backend='match')


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
    p = sub.add_parser('run'); p.add_argument('--control', type=Path, required=True); p.add_argument('--players', type=Path, required=True)
    p.add_argument('--epochs', type=int, default=1); p.add_argument('--backend', choices=['sim', 'match'], default='sim')
    p.add_argument('--capsule', type=Path); p.add_argument('--workers', type=int, default=os.cpu_count() or 1); p.add_argument('--slot', type=int, default=0)
    p = sub.add_parser('status'); p.add_argument('--control', type=Path, required=True)
    p = sub.add_parser('queue'); p.add_argument('--control', type=Path, required=True); p.add_argument('--event', required=True)
    p.add_argument('--player', required=True); p.add_argument('--author', required=True); p.add_argument('--authority', required=True)
    a = ap.parse_args()
    if a.cmd == 'init':
        pkgs = a9.load_packages(a.players)
        if a.only:
            pkgs = {k: v for k, v in pkgs.items() if k in a.only}
        m = a9.init(a.control, pkgs, json.loads(a.rules.read_text()), a.champion, a.author, a.authority)
        print(status(a.control))
    elif a.cmd == 'queue':
        e = a9.event(a.event, a.player, a.author, a.authority)
        path = a.control / 'queue' / f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{a.event}-{a.player}.json"
        path.write_text(json.dumps(e, indent=1))
        print(f'queued {path}')
    elif a.cmd == 'status':
        print(status(a.control))
    else:
        pkgs = a9.load_packages(a.players)
        backend = a9.SimBackend(pkgs) if a.backend == 'sim' else MatchBackend(pkgs, a.capsule)
        for _ in range(a.epochs):
            m = a9.current(a.control)
            t = time.time()
            a9.play_epoch(a.control, backend, slot=a.slot, workers=a.workers)
            nxt, decisions = a9.close_epoch(a.control, pkgs, source_commit=commit())
            print(f"epoch {m['epoch']} played in {time.time() - t:.0f}s; decisions: {json.dumps(decisions, default=str)[:600]}")
            print(status(a.control))


if __name__ == '__main__':
    main()
