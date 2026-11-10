"""Two frozen 100-family common-auction comparisons of 16/32 DDS budgets."""
import argparse
from collections import defaultdict
import fcntl
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

from match_gen5rz_ben import (ROOT, MODELS, EXPECTED, sha, make_board, deal_key,
    Board, imps, auction, reduction, load_plan, read_gz, write_gz, atomic_json,
    play_table, replay, np)

PAIRS = {'5R16-vs-5-32': ('5R16', '5-32'), '5RZ16-vs-5R32': ('5RZ16', '5R32')}


def prepare(a):
    if (a.run / 'manifest.json').exists():
        return verify(a.run)
    from bridge_harness.bidding_ppo import Policy
    a.run.mkdir(parents=True, exist_ok=True)
    for k, path in MODELS.items():
        assert sha(ROOT / path) == EXPECTED[k], path
    specs = {}
    for name, budget, representative, window in [('5R16',16,True,.125),
            ('5-32',32,False,.125), ('5RZ16',16,True,0.), ('5R32',32,True,.125)]:
        s = dict(id=name, samples=budget, near_tie=window, exploration=0.,
                 belief_kind='public', policy=MODELS['policy'], belief=MODELS['belief'])
        if representative:
            s['layout_reduction'] = reduction(load_plan(), budget)
        specs[name] = s
    boards = [make_board(a.seed, i, 'test') for i in range(a.boards)]
    families = [deal_key(b.hands, True) for b in boards]
    assert len(set(families)) == a.boards
    atomic_json(a.run / 'reserved-families.json', families)
    bidder = Policy.load(ROOT / MODELS['bidding'])
    rows = []
    for i, board in enumerate(boards):
        bid, decisions = auction(board, [bidder]*4)
        rows.append(dict(index=i, family=families[i], board=bid.to_dict(),
                         raw_board=board.to_dict(), bidding=decisions))
        if (i+1) % 20 == 0:
            print(json.dumps(dict(phase='auctions', completed=i+1)), flush=True)
    atomic_json(a.run / 'auctions.json', rows)
    code = {str(p.relative_to(ROOT)): sha(p) for p in (ROOT / 'bridge_harness').glob('*.py')}
    for rel in ('scripts/match_gen5r16.py', 'scripts/match_gen5rz_ben.py'):
        code[rel] = sha(ROOT / rel)
    m = dict(schema='gen5r16-common-v1', target=a.boards, seed=a.seed, pairs=PAIRS,
             bots=specs, model_paths=MODELS, model_sha256=EXPECTED, code_hashes=code,
             dds_sha256=sha(ROOT/'bridge_harness/libbridge_dds.so'),
             auctions_sha256=sha(a.run/'auctions.json'),
             families_sha256=sha(a.run/'reserved-families.json'),
             created=time.time(), source_commit=subprocess.check_output(
                 ['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
             evaluation_only=True, rng_group='gen5-budget-common',
             bidding='current Gen5 candidate-2 neural-only, all four seats, common auction',
             rooms='candidate NS / baseline EW, then baseline NS / candidate EW; alternating execution order',
             timing='single-thread process CPU and elapsed time per decision; model loading excluded',
             interpretation='positive IMPs favor first bot; two comparisons share families, do not pool as independent boards')
    atomic_json(a.run/'manifest.json', m)
    return m


def verify(run):
    m = json.loads((run/'manifest.json').read_text())
    for k, rel in m['model_paths'].items():
        assert sha(ROOT/rel) == m['model_sha256'][k], rel
    for rel, digest in m['code_hashes'].items():
        assert sha(ROOT/rel) == digest, rel
    for name, key in [('auctions.json','auctions_sha256'), ('reserved-families.json','families_sha256')]:
        assert sha(run/name) == m[key], name
    assert sha(ROOT/'bridge_harness/libbridge_dds.so') == m['dds_sha256']
    return m


def check_action(action, spec):
    if action.get('forced'):
        return
    assert action['estimates'][action['card']]['gap_to_best'] <= spec['near_tie']+1.0001e-9
    large = 13-action['ply']//4 >= 10
    if large and 'layout_reduction' in spec:
        r = action['layout_reduction']
        assert r['pool'] == spec['samples']*4, r
        assert r['requested_budget'] == spec['samples'], r
        assert 0 < action['samples'] <= spec['samples'], action['samples']
    else:
        assert 'layout_reduction' not in action
        assert action['samples'] == spec['samples'], action['samples']


def worker(a):
    from bridge_harness.mixed_arena import ArenaPlayer
    from bridge_harness.players import Decision
    class TimedPlayer(ArenaPlayer):
        def choose(self, observation, rng):
            start = time.process_time()
            d = super().choose(observation, rng)
            return Decision(d.card, dict(d.details, process_cpu_seconds=time.process_time()-start))
    m = verify(a.run)
    pair = list(m['pairs'])[a.worker]
    names = m['pairs'][pair]
    dest = a.run/pair
    dest.mkdir(exist_ok=True)
    players = {name: TimedPlayer(m['bots'][name], ROOT) for name in names}
    try:
        rows = json.loads((a.run/'auctions.json').read_text())
        for row in rows:
            i = row['index']
            if a.limit is not None and i >= a.limit:
                continue
            target = dest/'episodes'/f'{i:04d}.json.gz'
            if target.exists():
                continue
            started = time.time(); tables = []
            board = Board.from_dict(row['board'])
            for room in ((0,1) if (i+a.worker)%2 == 0 else (1,0)):
                room_file = dest/'tables'/f'{i:04d}-{room}.json.gz'
                assignments = [names[0] if seat%2 == room else names[1] for seat in range(4)]
                if room_file.exists():
                    record = read_gz(room_file)
                    assert record['board'] == row['board'] and record['assignments'] == assignments
                    replay(record)
                else:
                    def progress(action):
                        check_action(action, m['bots'][action['player']])
                        atomic_json(dest/'status.json', dict(index=i, room=room, ply=action['ply'],
                                    player=action['player'], updated=time.time()))
                    table = play_table(board, assignments, players, seed=m['seed']+i,
                                       rng_group=m['rng_group'], on_event=progress)
                    record = dict(board=row['board'], assignments=assignments, tables=[table])
                    if table['status'] != 'ok':
                        atomic_json(dest/f'failed-{i}-{room}.json', record)
                        raise RuntimeError(table['traceback'])
                    replay(record)
                    write_gz(room_file, record)
                tables.append(dict(room=room, record=record))
            tables.sort(key=lambda t: t['room'])
            scores = [t['record']['tables'][0]['ns_score'] for t in tables]
            result = dict(index=i, family=row['family'], pair=pair, tables=tables,
                          score_difference=scores[0]-scores[1], imps=imps(scores[0]-scores[1]),
                          seconds=time.time()-started, completed=time.time())
            write_gz(target, result)
            print(json.dumps(dict(pair=pair, index=i, imps=result['imps'], seconds=result['seconds'])), flush=True)
    except Exception:
        atomic_json(dest/'error.json', dict(error=traceback.format_exc(), updated=time.time()))
        raise
    finally:
        for player in players.values():
            player.close()


def summarize(run, legal=False):
    from scipy.stats import t
    m = json.loads((run/'manifest.json').read_text())
    output = {}
    for pair, names in m['pairs'].items():
        rows = [read_gz(p) for p in sorted((run/pair/'episodes').glob('*.json.gz'))]
        n = len(rows); assert len({r['family'] for r in rows}) == n
        vals = np.array([r['imps'] for r in rows], float)
        stats = {name: defaultdict(float) for name in names}
        for row in rows:
            scores = []
            for room in row['tables']:
                rec = room['record']
                if legal:
                    replay(rec)
                table = rec['tables'][0]; scores.append(table['ns_score'])
                for action in table['actions']:
                    name=action['player']; st=stats[name]
                    check_action(action, m['bots'][name])
                    st['seconds'] += action['seconds']
                    st['cpu_seconds'] += action['process_cpu_seconds']
                    st['decisions'] += 1
                    if not action.get('forced'):
                        st['nonforced'] += 1
                        st['samples'] += action['samples']
                        st['reduced_positions'] += 'layout_reduction' in action
                        st['policy_selections'] += 'selector_predictions' in action
                        st['max_selected_pimc_gap'] = max(st['max_selected_pimc_gap'],
                            action['estimates'][action['card']]['gap_to_best'])
            assert row['imps'] == imps(scores[0]-scores[1])
        se = float(vals.std(ddof=1)/math.sqrt(n)) if n>1 else None
        mean = float(vals.mean()) if n else None
        for st in stats.values():
            st['cpu_seconds_per_board'] = st['cpu_seconds']/n if n else None
            st['seconds_per_board'] = st['seconds']/n if n else None
        output[pair] = dict(boards=n, target=m['target'], complete=n==m['target'], total_imps=int(vals.sum()),
                           imps_per_board=mean, se=se, ci95=[mean-t.ppf(.975,n-1)*se,mean+t.ppf(.975,n-1)*se] if n>1 else None,
                           wins=int((vals>0).sum()), losses=int((vals<0).sum()), ties=int((vals==0).sum()),
                           timing_and_checks=stats, replay_verified_tables=n*2 if legal else None)
    result=dict(matches=output, updated=time.time())
    atomic_json(run/'result.json', result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare','run','worker','summary'])
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--boards', type=int, default=100)
    p.add_argument('--seed', type=int, default=20261110183016)
    p.add_argument('--worker', type=int, default=0)
    p.add_argument('--limit', type=int)
    a=p.parse_args(); a.run=a.run.resolve()
    if a.command=='summary':
        print(json.dumps(summarize(a.run,True)),flush=True); return
    if a.command=='worker':
        worker(a); return
    prepare(a)
    if a.command=='prepare':
        return
    lock=(a.run/'writer.lock').open('a'); fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    children=[]
    for i in range(2):
        log=(a.run/f'worker-{i}.log').open('a')
        cmd=[sys.executable,'-u',__file__,'worker','--run',str(a.run),'--worker',str(i)]
        if a.limit is not None:
            cmd += ['--limit',str(a.limit)]
        children.append((subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT),log))
    last=None
    while any(c.poll() is None for c,_ in children):
        time.sleep(10)
        result=summarize(a.run)
        counts=[r['boards'] for r in result['matches'].values()]
        if counts != last:
            print(json.dumps(result),flush=True); last=counts
    for _,log in children:
        log.close()
    print(json.dumps(summarize(a.run,True)),flush=True)
    if any(c.returncode for c,_ in children):
        raise SystemExit('Worker failed; see retained error.json')


if __name__=='__main__':
    main()
