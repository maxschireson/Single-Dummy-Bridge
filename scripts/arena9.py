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
                                              WORKER['pair'], row['completed_epoch'], root=str(ROOT), occasions=WORKER.get('occasions'))
    return row


OVERRIDE_FILES = ('gen7_policy', 'scorer', 'bidding', 'lead_belief', 'system_scorer')     # gen8_match.build_manifest's path keys


def file_sha256(path, _cache={}):
    import hashlib
    path = Path(path)
    if path not in _cache:
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(1 << 20), b''):
                h.update(chunk)
        _cache[path] = h.hexdigest()
    return _cache[path]


def override_files(bundle):
    """{artifact name: path} of the files a capsule bundle's overrides put in place of its base bot's nets."""
    out = {}
    for k in OVERRIDE_FILES:
        v = (bundle.get('overrides') or {}).get(k)
        if isinstance(v, str):
            path = (ROOT / v).resolve()
            if not path.is_file():
                raise ValueError(f'{v}: not in this checkout (restore the nets first)')
            out[k] = path
    return out


class MatchBackend:
    """Real bots through gen9_match: one single-pair manifest (forks off) per pair, as scripts/gen8_match.py builds it.
    A Gen 9 bot whose package asks for it (`bundle.epoch_models`) is handed every rostered player's model with the epoch's
    experience snapshot; each finished board's experience envelopes come back with its row."""

    def __init__(self, packages, capsule, control=None, experience=True):
        self.packages, self.capsule, self.control = packages, Path(capsule).resolve(), Path(control) if control else None
        self.experience = experience
        bots = json.loads((self.capsule / 'manifest.json').read_text())['bots']
        for pid, p in packages.items():           # a package names its nets by hash: they must be the nets it plays with
            b = p['bundle']
            if b.get('source') != 'capsule':
                continue
            named = b.get('artifact_sha256') or {}
            files = override_files(b)
            for k, path in files.items():         # an override's file replaces the capsule bot's net of that name
                if k in named and file_sha256(path) != named[k]:
                    raise ValueError(f'{pid}: {k} is {path.relative_to(ROOT)} ({file_sha256(path)[:8]}), not the {named[k][:8]} the package names')
            want = {k: v for k, v in named.items() if k in bots[b['bot']].get('artifact_sha256', {}) and k not in files}
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
        for pid in set(pair.split('~')):     # gen8_match copies the base bot's hashes; record the nets an override plays with
            files = override_files(self.packages[pid]['bundle'])
            spec = man['bots'].get(pid)
            if files and spec is not None:
                spec['artifact_sha256'] = dict(spec.get('artifact_sha256') or {}, **{k: file_sha256(v) for k, v in files.items()})
                spec.pop('identity', None)
                spec['identity'] = digest(spec)
        man['arena_epoch'], man['arena_epoch_id'], man['experience_snapshot'] = m['epoch'], m['id'], m['experience_snapshot']
        man.pop('identity', None)
        man['identity'] = digest(man)
        return man, models

    def play(self, m, pair, indices, seed, workers=1):
        from bridge_harness import arena9_pipeline as pl
        man, models = self.manifest(m, pair, seed)
        rules = json.loads((self.control / 'rules.json').read_text()) if self.control and (self.control / 'rules.json').exists() else None
        ctx = dict(epoch_id=m['id'], pair=pair, models=models or {}, declared=pl.declared_map(self.packages, ROOT), experience=self.experience,
                   occasions=pl.occasion_rule(rules))
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


def paired(rows, a_pair, b_pair, condition):
    """Per deal both pairs played: x(a) - x(b), with the mean and its standard error."""
    import math
    A = {(r['epoch'], r['index']): r for r in rows if r['pair'] == a_pair and r.get(condition) is not None}   # a floor's deal index
    B = {(r['epoch'], r['index']): r for r in rows if r['pair'] == b_pair and r.get(condition) is not None}   # repeats each epoch
    d = [A[i][condition] - B[i][condition] for i in sorted(set(A) & set(B))]
    n = len(d)
    if n < 2:
        return dict(n=n, mean=d[0] if d else None, se=None)
    m = sum(d) / n
    return dict(n=n, mean=round(m, 3), se=round(math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1) / n), 3))


def arrival_report(control, packages, bot='9a-32', control_bot='8p-32', replay_result=None):
    """The arrival run's page (G9-D6 done-when), from a control directory."""
    from bridge_harness import arena_ratings as ar
    from bridge_harness import arena9_pipeline as pl
    control = Path(control)
    log = a9.read_log(control)
    rows = a9.read_results(control)
    epochs = sorted({r['epoch'] for r in rows})
    guests = [e['player'] for e in log if e['event'] == 'submit' and e.get('kind') == 'guest']
    spec = packages[bot]['bundle'].get('overrides') or {}
    L = [f'# The arrival run: {control}', '', f'Epochs played: {epochs}. Boards: {len(rows)}. Guests: {guests}.', '']
    L += ['## 1 and 3. The player model at the table', '',
          f'`{bot}` against the guest minus `{control_bot}` against the same guest, on the same deals (the floor), IMPs a board from the bot\'s side.', '',
          '| Guest | Epoch | Deals | Native: mean (SE) | Common: mean (SE) |', '| --- | --- | ---: | --- | --- |']
    for g in guests:
        a_pair, b_pair = f'{bot}~{g}', f'{control_bot}~{g}'
        for ep in epochs + ['all']:
            rs = [r for r in rows if r.get('floor') is not None and (ep == 'all' or r['epoch'] == ep)]
            nat, com = paired(rs, a_pair, b_pair, 'native'), paired(rs, a_pair, b_pair, 'common')
            if nat['n']:
                f = lambda x: '—' if x['mean'] is None else (f"{x['mean']:+.3f}" + (f" ({x['se']:.3f})" if x['se'] is not None else ''))
                L.append(f'| {g} | {ep} | {nat["n"]} | {f(nat)} | {f(com)} |')
    L += ['', '## 2. What experience adds', '',
          'What each epoch\'s bots were handed for each guest (the snapshot frozen when the previous epoch closed), read as the Gen 9 bot reads it.', '',
          '| Guest | Epoch | Boards in the snapshot | Deltas (board-sides) | P(card) as read | Other profiles as read | Honesty as read | Play factor | Snapshot = envelopes of earlier epochs |',
          '| --- | --- | ---: | ---: | ---: | --- | ---: | --- | --- |']
    for ep in sorted(int(p.stem) for p in (control / 'epochs').glob('*.json')):
        rep = pl.epoch_experience(control, ep, spec)
        for g in guests:
            row = rep['players'].get(g)
            if row is None:
                continue
            pc = dict(map(tuple, row['profiles_read'])).get('card')
            h = (row.get('honesty_read') or {}).get('*')
            others = ', '.join(f'{s_} {p_:.2f}' for s_, p_ in sorted(row['profiles_read'], key=lambda x: -x[1]) if s_ != 'card' and p_ >= 0.05) or '—'
            label = ep if ep in epochs else f'{ep} (after the run)'
            L.append(f"| {g} | {label} | {row.get('deals', '—')} | {row['boards']} | {'—' if pc is None else f'{pc:.3f}'} | {others} | {'— (prior)' if h is None else f'{h:.3f}'} | "
                     f"{row.get('play_factor', '—')} | {'yes' if row['snapshot_matches_envelopes'] else '**no**'} |")
    L += ['', '## 4. The arena', '', '**Registry events**', '']
    for e in log:
        if e['player'] in guests or e['event'] in ('activate', 'open-test', 'promote', 'demote', 'retire'):
            extra = ''
            if e['event'] == 'submit' and e.get('model'):
                extra = ' first model ' + ', '.join(f'{s}: {p:.3f}' for s, p in e['model']['profiles'])
            if e.get('evidence'):
                extra += ' evidence ' + json.dumps(e['evidence'], sort_keys=True)[:200]
            L.append(f"- seq {e['seq']} `{e['event']}` {e['player']} (epoch {e.get('epoch')}): {e['authority']}{extra}")
    L += ['', '**Share of boards by epoch**', '', '| Epoch | ' + ' | '.join(guests) + ' |', '| --- |' + ' ---: |' * len(guests)]
    for ep in epochs:
        rs = [r for r in rows if r['epoch'] == ep]
        L.append(f'| {ep} | ' + ' | '.join(f"{sum(g in r['pair'].split('~') for r in rs) / len(rs):.0%}" for g in guests) + ' |')
    L += ['', '**Ratings (native) at the close of each epoch, IMPs a board against the reference, 95% half-width**', '']
    for path in sorted((control / 'ratings').glob('*-native.json')):
        t = json.loads(path.read_text())
        gone = {e['player'] for e in log if e['event'] == 'retire' and e.get('epoch') is not None and e['epoch'] <= t['epoch']}
        L.append(f"- epoch {t['epoch']}: " + ', '.join(f"{p}{' (retired)' if p in gone else ''} {v['strength']:+.2f} ± {1.96 * v['se']:.2f}"
                                                     for p, v in sorted(t['players'].items(), key=lambda kv: -kv[1]['strength'])))
    rules = json.loads((control / 'rules.json').read_text())
    test_pair = f'{bot}~{control_bot}'
    t = ar.BettingTest(alpha=rules['promotion']['alpha'], beta=rules['promotion']['beta'], d=rules['promotion']['d'], cap=rules['promotion']['cap'])
    direct = sorted((r for r in rows if r['pair'] == test_pair and r.get(rules['condition']) is not None), key=lambda r: (r['epoch'], r['slot'], r['k']))
    for r in direct:
        if t.update(float(r[rules['condition']])):
            break
    L += ['', f'**Betting test `{test_pair}`** on every direct board so far ({rules["condition"]}): {t.t} boards, K = {t.K:.3f} (promote at {1 / t.alpha:g}), '
          f'L = {t.L:.3f} (futility at {1 / t.beta:g}), decision {t.decision}. The controller opens the test only once `{bot}` is admitted and rated above the champion.', '']
    L += ['## 5. Replay', '']
    L.append('```\n' + json.dumps(replay_result, indent=1) + '\n```' if replay_result else 'Not run.')
    return '\n'.join(L) + '\n'


def restore_nets():
    """Rebuild any net kept in the repository as parts and not restored yet (will's idempotent restore in run_tests.py):
    a box job gets DDS built in its checkout, not the nets."""
    spec = importlib.util.spec_from_file_location('run_tests', ROOT / 'scripts' / 'run_tests.py')
    rt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rt)
    bad = [m for m in rt.restore_models() if not m['ok']]
    if bad:
        raise SystemExit(f'restoring nets failed: {bad}')


def queue_planned(control, events, epoch):
    """Queue the events the plan gives for `epoch` (taking effect when it opens), once: a planned event that is already
    queued, applied or refused is not queued again."""
    q = Path(control) / 'queue'
    for i, e in enumerate(events.get('before_epoch', {}).get(str(epoch), [])):
        stem = f"plan-e{epoch:04d}-{i}-{e['event']}-{e['player']}"
        if any((q / (stem + ext)).exists() for ext in ('.json', '.applied', '.refused')):
            continue
        extra = {k: v for k, v in e.items() if k not in ('event', 'player', 'author', 'authority', 'epoch')}   # e.g. open-test's champion
        (q / (stem + '.json')).write_text(json.dumps(a9.event(e['event'], e['player'], e.get('author', 'plan'),
                                                               e.get('authority', 'arrival run plan, written before the run'), epoch=epoch, **extra), indent=1))


def arrival(out, players, rules, capsule, events, epochs, workers, backend=None):
    """The arrival run (G9-D6) as one resumable process: initialise once, play and close each epoch with the plan's events
    queued before their epoch, replay one floor board of the plan's replay epoch, write the page."""
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    control = out / 'control'
    restore_nets()
    pkgs = a9.load_packages(players)
    plan = json.loads(Path(events).read_text())
    hook = arrival_hook(control)
    if not (control / 'CURRENT').exists():
        start = plan['start']
        a9.init(control, {k: pkgs[k] for k in start['players']}, json.loads(Path(rules).read_text()), start['champion'],
                start.get('author', 'plan'), start.get('authority', 'arrival run plan, written before the run'), arrival=hook)
    held = a9.lock(control)
    backend = backend(pkgs) if backend else MatchBackend(pkgs, capsule, control)
    while a9.current(control)['epoch'] <= epochs:
        m = a9.current(control)
        t = time.time()
        a9.play_epoch(control, backend, workers=workers, mirror=out / 'results.jsonl')
        queue_planned(control, plan, m['epoch'] + 1)
        nxt, decisions = a9.close_epoch(control, pkgs, source_commit=commit(), arrival=hook)
        print(f"epoch {m['epoch']} played and closed in {time.time() - t:.0f}s; decisions: {json.dumps(decisions, default=str)[:800]}", flush=True)
        print(status(control), flush=True)
    rp = out / 'replay.json'
    if plan.get('replay') and not rp.exists():
        ep = plan['replay']['epoch']
        rows = [json.loads(l) for l in (control / 'results' / f'e{ep:04d}' / 'slot0.jsonl').read_text().splitlines() if l.strip()]
        pick = sorted((r for r in rows if r['pair'] == plan['replay']['pair']), key=lambda r: r['k'])[0]
        rp.write_text(json.dumps(replay(control, pkgs, capsule, ep, pick['k']), indent=1))
    (out / 'report.md').write_text(arrival_report(control, pkgs, bot=plan.get('bot', '9a-32'), control_bot=plan.get('control_bot', '8p-32'),
                                                  replay_result=json.loads(rp.read_text()) if rp.exists() else None))
    held.close()


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
    p = sub.add_parser('report'); p.add_argument('--control', type=Path, required=True); p.add_argument('--players', type=Path, required=True)
    p.add_argument('--replay', type=Path, help='a replay result (JSON) to include'); p.add_argument('--out', type=Path)
    p = sub.add_parser('arrival'); p.add_argument('--out', type=Path, required=True); p.add_argument('--players', type=Path, required=True)
    p.add_argument('--rules', type=Path, required=True); p.add_argument('--capsule', type=Path, required=True); p.add_argument('--events', type=Path, required=True)
    p.add_argument('--epochs', type=int, required=True); p.add_argument('--workers', type=int, default=os.cpu_count() or 1)
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
    elif a.cmd == 'report':
        text = arrival_report(a.control, a9.load_packages(a.players), replay_result=json.loads(a.replay.read_text()) if a.replay else None)
        if a.out:
            a.out.write_text(text)
        print(text)
    elif a.cmd == 'arrival':
        arrival(a.out, a.players, a.rules, a.capsule, a.events, a.epochs, a.workers)
    elif a.cmd == 'replay':
        print(json.dumps(replay(a.control, a9.load_packages(a.players), a.capsule, a.epoch, a.k, a.slot), indent=1))
    else:
        pkgs = a9.load_packages(a.players)
        backend = a9.SimBackend(pkgs) if a.backend == 'sim' else MatchBackend(pkgs, a.capsule, a.control)
        hook = None if a.backend == 'sim' else arrival_hook(a.control)
        held = a9.lock(a.control)
        for _ in range(a.epochs):
            m = a9.current(a.control)
            t = time.time()
            a9.play_epoch(a.control, backend, slot=a.slot, workers=a.workers)
            nxt, decisions = a9.close_epoch(a.control, pkgs, source_commit=commit(), arrival=hook)
            print(f"epoch {m['epoch']} played in {time.time() - t:.0f}s; decisions: {json.dumps(decisions, default=str)[:600]}")
            print(status(a.control))


if __name__ == '__main__':
    main()
