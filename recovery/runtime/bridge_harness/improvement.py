"""Resumable self-play -> fit -> paired arena -> promote, with bounded runs.

No scheduler is installed and no campaign is started by importing this module.
Trainers are trusted subprocesses; only observation fields may reach networks.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextlib import contextmanager
from dataclasses import replace
import fcntl
import gzip
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time

from .core import Board, Game, imps
from .corpus import generate, load, save
from .loop_registry import freeze_bot, verify_bot, sha, source_hash
from .loop_stats import gate, plan_arena, estimate
from .loop_runtime import managed_ben
from .runner import isolated_pair, replay
from .selfplay import atomic_json
from .training import digest, examples_from_record, split_for


def read(path):
    path = Path(path)
    with (gzip.open(path, 'rt') if path.suffix == '.gz' else path.open()) as f:
        return json.load(f)


@contextmanager
def writer_lock(root):
    """OS-owned lock: released even after SIGKILL; never delete live lock files."""
    path = Path(root) / '.writer.lock'; path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+') as f:
        try: fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise RuntimeError('Another campaign writer is active') from None
        try: yield
        finally: fcntl.flock(f, fcntl.LOCK_UN)


def command(argv, substitutions, cwd, log, timeout):
    """Explicit argv; never a shell. Completed output is verified by its caller."""
    if not argv or not isinstance(argv, list) or not all(isinstance(v, str) for v in argv):
        raise ValueError('A nonempty command argv list is required')
    args = [a.format_map({k: str(v) for k, v in substitutions.items()}) for a in argv]
    Path(log).parent.mkdir(parents=True, exist_ok=True)
    with Path(log).open('a') as f:
        p = subprocess.Popen(args, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            rc = p.wait(timeout=timeout)
            if rc: raise RuntimeError(f'Command exit {rc}; see {log}')
        except BaseException:
            import signal
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGTERM)
                try: p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL); p.wait()
            raise


def bounded_map(fn, jobs, workers):
    """Keep only workers futures in flight, including at 250k deals."""
    jobs = iter(jobs)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = set()
        def submit():
            item = next(jobs, None)
            if item is not None: pending.add(pool.submit(fn, item))
        for _ in range(workers): submit()
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                yield future.result()
                submit()


def validate_record(record, board, config):
    if record['board'] != board.to_dict() or record['config'] != config:
        raise ValueError('Cached record changed deal, auction, bot, or decision settings')
    if record['status'] != 'ok': raise RuntimeError('Failed game retained; inspect before --retry-failures')
    replay(record)
    c, b = config['candidate'], config['baseline']
    expected = [[c] * 4] if config['mode'] == 'selfplay' else [[c, b] * 2, [b, c] * 2]
    if record.get('assignments') != expected or len(record['tables']) != len(expected):
        raise ValueError('Invalid table count or partnership assignments')
    for seats, table in zip(expected, record['tables']):
        if table['status'] != 'ok' or len(table['actions']) != (52 if board.contract else 0):
            raise ValueError('Incomplete game')
        game = Game(board)
        from .core import card
        for action in table['actions']:
            observation = game.observation()
            if action['player'] != seats[observation.controller]:
                raise ValueError('Wrong player controlled a seat')
            probabilities = action.get('behavior_probabilities')
            if probabilities is not None:
                import math
                if (not all(math.isfinite(v) and v >= 0 for v in probabilities.values())
                        or abs(sum(probabilities.values())-1) > 1e-6
                        or probabilities.get(action['card'], 0) <= 0
                        or any(card(k) not in observation.legal for k in probabilities)):
                    raise ValueError('Invalid logged behavior distribution')
            game.play(card(action['card']))
    if config['mode'] == 'partnership':
        difference = record['tables'][0]['ns_score'] - record['tables'][1]['ns_score']
        if record['score_difference'] != difference or record['imps'] != imps(difference):
            raise ValueError('Bad IMP orientation or score')


class Campaign:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.config = read(self.root / 'campaign.json')
        self.state_path = self.root / 'state.json'
        self.state = read(self.state_path)
        self.db = sqlite3.connect(self.root / 'deals.sqlite')
        self.db.execute('CREATE TABLE IF NOT EXISTS deals '
                        '(id TEXT PRIMARY KEY, role TEXT, unit TEXT, board_hash TEXT)')

    def close(self): self.db.close()

    def checkpoint(self, **changes):
        self.state.update(changes)
        atomic_json(self.state_path, self.state)

    @contextmanager
    def timed(self,phase):
        started=time.monotonic()
        try:yield
        finally:
            totals=dict(self.state.get('phase_seconds',{}))
            totals[phase]=totals.get(phase,0)+time.monotonic()-started
            self.checkpoint(phase_seconds=totals)

    def bot(self, name): return self.root / 'bots' / name / 'bot.json'

    def preflight(self):
        c = self.config
        if c['source_sha256'] != source_hash():
            raise ValueError('Code/solver differs from frozen campaign; restore pinned checkout')
        if digest(c['settings']) != c['settings_sha256']:
            raise ValueError('Campaign settings changed')
        for path, expected in c.get('pins', {}).items():
            if sha(path) != expected: raise ValueError(f'External dependency changed: {path}')
        s = c['settings']
        if not s.get('trainer_command'): raise ValueError('Final v2 trainer_command has not been bound')
        if not s.get('corpus_command') and not s.get('smoke'):
            raise ValueError('Real auction corpus_command required')
        for name in {self.state['champion'], s['original'], s['ben']}:
            verify_bot(self.bot(name))
        if not s.get('smoke'):
            ben = read(self.bot(s['ben']))['spec']
            ext = ben.get('external', {})
            if ext.get('mode') != 'full-search' or not ext.get('revision') or not ext.get('operator_verified'):
                raise ValueError('Pin and verify the full-search BEN reference server before launch')
            if not {'config', 'models_manifest'} <= set(ben['artifacts']):
                raise ValueError('BEN config and model-checksum manifest must be frozen artifacts')
            model_file = self.bot(s['ben']).parent / ben['artifacts']['models_manifest']['file']
            model_pins = read(model_file)
            if not model_pins: raise ValueError('BEN model manifest cannot be empty')
            for path, expected in model_pins.items():
                if sha(path) != expected: raise ValueError(f'BEN model changed: {path}')
        return dict(ready=True, champion=self.state['champion'], smoke=bool(s.get('smoke')),
                    training_deals=s['training_stages'], evaluation_deals=s['evaluation_looks'])

    def reserve(self, boards, role, unit):
        with self.db:
            for b in boards:
                if b.family: raise ValueError('This arena requires independent deals, not related-layout families')
                did = digest(b.hands)
                row = (role, unit, digest(b.to_dict()))
                existing = self.db.execute('SELECT role,unit,board_hash FROM deals WHERE id=?', (did,)).fetchone()
                if existing and existing != row:
                    raise ValueError('Duplicate deal or training/evaluation overlap')
                self.db.execute('INSERT OR IGNORE INTO deals VALUES (?,?,?,?)', (did, *row))

    def corpus(self, unit, count, role):
        """One immutable, resumable auction chunk; failed partial chunks are retained."""
        d = self.root / unit; d.mkdir(parents=True, exist_ok=True)
        frozen = d / 'auction' / 'frozen.jsonl'
        manifest = d / 'corpus.json'
        seed = int(digest([self.config['settings']['seed'], self.config['campaign_id'], unit])[:15], 16)
        if manifest.exists():
            m = read(manifest)
            if m['count'] != count or m['seed'] != seed or m['sha256'] != sha(frozen):
                raise ValueError('Frozen corpus changed')
            boards = load(frozen)
        else:
            raw = [replace(b, id=f'{unit}/{i}') for i, b in enumerate(generate(count, seed))]
            if any(self.db.execute('SELECT 1 FROM deals WHERE id=?',(digest(b.hands),)).fetchone() for b in raw):
                raise ValueError('New corpus overlaps a reserved deal')
            rawpath = d / 'input.jsonl'; save(raw, rawpath)
            out = d / 'auction'
            if self.config['settings'].get('smoke'):
                # Clearly labelled synthetic auctions are NEVER accepted by a production campaign.
                save(raw, frozen)
            else:
                exclusions = d / 'exclusions.json'
                # All input identities were checked against the indexed ledger
                # above. Avoid duplicating a 250k-ID list in every 250-deal chunk.
                atomic_json(exclusions, dict(deal_ids=[], prechecked_against_campaign_ledger=True))
                if out.exists():
                    # Preserve interrupted collector work for debugging. New atomic chunk
                    # invocation repeats only this chunk, never completed corpus chunks.
                    out.rename(d / f'auction-interrupted-{time.time_ns()}')
                s = self.config['settings']
                command(s['corpus_command'], dict(input=rawpath, output=out, count=count,
                        seed=seed, exclusions=exclusions), self.config['checkout'],
                        d / 'auction.log', s['command_timeout'])
            boards = load(frozen)
            if len(boards) != count: raise ValueError('Incomplete auction chunk')
            for a, b in zip(raw, boards):
                if (a.id, a.hands, a.dealer, a.vulnerability) != (b.id, b.hands, b.dealer, b.vulnerability):
                    raise ValueError('Collector changed or reordered input deals')
                if b.opening_lead is not None: raise ValueError('Opening leads must be chosen by the players')
                if not self.config['settings'].get('smoke') and (not b.auction or b.auction_source == 'synthetic'):
                    raise ValueError('Genuine frozen auctions required')
            atomic_json(manifest, dict(count=count, seed=seed, sha256=sha(frozen)))
        self.reserve(boards, role, unit)
        return boards

    def pair(self, board, candidate, baseline, path, selfplay=False, retry=False):
        cfg = dict(mode='selfplay' if selfplay else 'partnership',
                   candidate='manifest:' + str(self.bot(candidate)),
                   baseline='manifest:' + str(self.bot(baseline)),
                   common='manifest:' + str(self.bot(baseline)),
                   seed=int(digest([self.config['settings']['seed'], board.id, 'decision'])[:12], 16),
                   behavior_id=read(self.bot(candidate))['identity'],
                   objective=read(self.bot(candidate))['spec']['budget'].get('objective', 'tricks'))
        if not selfplay:cfg['rng_group']='loop-common-worlds-v1'
        path = Path(path)
        if path.exists():
            r = read(path)
            if r.get('status') != 'ok' and retry:
                path.rename(path.with_name(path.name + f'.failed-{time.time_ns()}'))
            else:
                validate_record(r, board, cfg)
                return r
        s = self.config['settings']
        r = isolated_pair(board, cfg, s['board_timeout'] if selfplay else s['arena_board_timeout'])
        atomic_json(path, r, compressed=True)
        validate_record(r, board, cfg)
        if selfplay and board.contract:
            # Check training targets/information separation now; reconstruct on demand
            # during fitting rather than storing 52 duplicate observations per game.
            examples = examples_from_record(r, digest([board.id, candidate]))
            for e in examples:
                p = e['policy_target']; probabilities = p['behavior_probabilities']
                if abs(sum(probabilities.values()) - 1) > 1e-6 or any(v < 0 for v in probabilities.values()):
                    raise ValueError('Invalid logged behavior probabilities')
                if p['selected_probability'] <= 0 or int(p['action']) not in e['observation']['legal']:
                    raise ValueError('Invalid policy target')
                if any(int(k) not in e['observation']['legal'] for k in probabilities):
                    raise ValueError('Illegal action in behavior distribution')
        return r

    def collect(self, generation, target, parent, retry=False):
        s = self.config['settings']; shards = []
        collector=parent
        epsilon=s.get('selfplay_exploration',0.)
        if epsilon:
            m=read(self.bot(parent));spec=json.loads(json.dumps(m['spec']))
            spec.pop('source_sha256',None);spec.pop('factory_sha256',None)
            if spec['factory']!='bridge_harness.combined_player:CombinedPlayer':
                raise ValueError('Exploration override requires the combined v2 factory')
            spec['artifacts']={k:str(self.bot(parent).parent/v['file']) for k,v in spec['artifacts'].items()}
            spec['kwargs']['exploration']=epsilon;collector=parent+'-explore'
            freeze_bot(self.root,collector,spec)
        for start in range(0, target, s['shard_size']):
            count = min(s['shard_size'], target-start)
            unit = f'g{generation}/selfplay/{start:06d}'
            boards = self.corpus(unit, count, 'selfplay')
            d = self.root / unit
            def work(b):
                return self.pair(b, collector, collector, d / 'episodes' / f'{digest(b.hands)}.json.gz', True, retry)
            completed = 0
            for _ in bounded_map(work, boards, s['workers']):
                completed += 1
                if completed % 25 == 0: print(json.dumps(dict(event='selfplay', generation=generation,
                    completed=start+completed, target=target)), flush=True)
            files = {p.name: sha(p) for p in sorted((d / 'episodes').glob('*.json.gz'))}
            if len(files) != count: raise ValueError('Missing or extra self-play records')
            summary = dict(count=count, parent=read(self.bot(parent))['identity'], episodes=files,
                           behavior=read(self.bot(collector))['identity'],exploration=epsilon,
                           splits={key: sum(split_for(b) == key for b in boards) for key in ('train','validation','test')},
                           passed_out=sum(b.contract is None for b in boards))
            atomic_json(d / 'shard.json', summary)
            shards.append(dict(path=str(d), sha256=sha(d / 'shard.json')))
        dataset = dict(schema=1, generation=generation, independent_deals=target,
                       parent=read(self.bot(parent))['identity'], shards=shards,
                       allowed_fit_splits=['train'], allowed_selection_splits=['validation'],
                       test_access=False, behavior='frozen parent, all four seats, logged exploration', exploration=epsilon,
                       policy_labels='actual return/propensity; never an unplayed counterfactual return')
        path = self.root / f'g{generation}/dataset-{target}.json'
        atomic_json(path, dataset)
        return path

    def train(self, generation, target, parent, dataset):
        d = self.root / f'g{generation}/fit-{target}'; d.mkdir(parents=True, exist_ok=True)
        request = dict(schema=1, dataset=str(dataset), dataset_sha256=sha(dataset),
                       parent_manifest=str(self.bot(parent)), parent_identity=read(self.bot(parent))['identity'],
                       seed=int(digest([self.config['settings']['seed'], generation, target, 'fit'])[:8], 16),
                       output=str(d / 'candidate.json'),
                       selection_rule='validation only; parent/epoch zero eligible; no arena access')
        rp = d / 'request.json'
        if rp.exists() and read(rp) != request: raise ValueError('Training inputs changed')
        atomic_json(rp, request)
        candidate = d / 'candidate.json'
        if not candidate.exists():
            command(self.config['settings']['trainer_command'], dict(request=rp, output=candidate),
                    self.config['checkout'], d / 'trainer.log', self.config['settings']['command_timeout'])
        result = read(candidate)
        provenance = result['training']
        for key in ('dataset_sha256', 'parent_identity', 'seed'):
            if provenance.get(key) != request[key]: raise ValueError(f'Trainer provenance mismatch: {key}')
        if provenance.get('selection_split') != 'validation' or provenance.get('test_access') is not False:
            raise ValueError('Trainer must select using validation without test/arena access')
        spec = result['bot']
        if spec['budget'] != read(self.bot(parent))['spec']['budget']:
            raise ValueError('Search budget changed during a weight-only generation')
        spec['training'] = provenance
        name = f'candidate-g{generation}-n{target}'
        freeze_bot(self.root, name, spec)
        return name

    def arena(self, generation, target, candidate, parent, count, retry=False, screen_only=False):
        s = self.config['settings']; all_rows = []
        unit_base = f'g{generation}/arena-{target}'
        comparisons = dict(vs_parent=(candidate, parent), vs_original=(candidate, s['original']),
                           vs_ben=(candidate, s['ben']), parent_vs_ben=(parent, s['ben']))
        if screen_only:comparisons={'vs_parent':(candidate,parent)}
        for start in range(0, count, s['shard_size']):
            # One reserved cohort per generation permits caching parent-vs-BEN
            # across the three predeclared data stages. Never train on it or tune
            # model choices from its outcomes; all stage/look tests spend alpha.
            unit = f'g{generation}/arena-boards/{start:06d}'
            boards = self.corpus(unit, min(s['shard_size'], count-start), 'arena')
            def work(board):
                row = dict(deal_id=digest(board.hands), timings={}, trick_swings={})
                for label, (a, b) in comparisons.items():
                    # Same pair can serve two labels without replaying identical games.
                    pair_id = digest([a, b])[:24]
                    p = self.root / f'g{generation}/arena-games' / pair_id / f'{row["deal_id"]}.json.gz'
                    r = self.pair(board, a, b, p, retry=retry)
                    row[label] = r['imps']
                    row['timings'][label] = sum(t['seconds'] for t in r['tables'])
                    row['trick_swings'][label] = ((r['tables'][0]['declarer_tricks'] - r['tables'][1]['declarer_tricks'])
                        * (1 if board.contract.declarer % 2 == 0 else -1)) if board.contract else 0
                return row
            workers=s['workers'] if screen_only else s.get('arena_workers',s['workers'])
            for row in bounded_map(work, boards, workers): all_rows.append(row)
            print(json.dumps(dict(event='arena', generation=generation, training_deals=target,
                                  completed=len(all_rows), target=count)), flush=True)
        all_rows.sort(key=lambda r:r['deal_id'])
        if screen_only:
            stat=estimate(r['vs_parent'] for r in all_rows)
            result=dict(generation=generation,training_deals=target,evaluation_deals=count,candidate=candidate,parent=parent,
                        decision='screen-pass' if stat['mean']>s.get('screen_min_mean',0.) else 'screen-reject',
                        vs_parent=stat,screen_only=True,rows_sha256=digest(all_rows),
                        note='Compute-allocation screen only; never a promotion test')
            atomic_json(self.root/unit_base/f'screen-{count}.json',result)
            self.report();return result
        result = gate(all_rows, generation, len(s['training_stages']), len(s['evaluation_looks']),
                      s['family_alpha'], s['minimum_imp_gain'])
        result.update(generation=generation, training_deals=target, evaluation_deals=count,
                      candidate=candidate, parent=parent, rows_sha256=digest(all_rows),
                      smoke=bool(s.get('smoke')), total_pair_seconds={
                          k:sum(r['timings'][k] for r in all_rows) for k in comparisons},
                      mean_trick_swings={k:sum(r['trick_swings'][k] for r in all_rows)/count for k in comparisons})
        if s.get('smoke') and result['decision']=='promote': result['decision']='smoke-only-no-promotion'
        path = self.root / unit_base / f'result-{count}.json'
        atomic_json(path, result)
        atomic_json(path.with_name(f'rows-{count}.json.gz'), all_rows, compressed=True)
        self.report()
        return result

    def promote(self, result):
        if self.config['settings'].get('smoke') or result['decision'] != 'promote':
            raise ValueError('Only a production result passing both gates can promote')
        if result['parent'] != self.state['champion']: raise ValueError('Stale candidate parent')
        # State is the single authoritative promotion transaction; aliases/history
        # are embedded in the same atomically replaced JSON document.
        history = list(self.state['promotions'])
        version = self.state['next_version']
        entry = dict(version=f'v{version}', candidate=result['candidate'], parent=result['parent'],
                     generation=result['generation'], training_deals=result['training_deals'],
                     evaluation_deals=result['evaluation_deals'], result=result)
        history.append(entry)
        self.checkpoint(champion=result['candidate'], next_version=version+1,
                        generation=result['generation']+1, promotions=history, status='ready-next-generation')
        self.report()

    def run(self, generations=1, retry=False):
        self.preflight()
        if self.state['status'] == 'exhausted':
            raise ValueError('All data stages exhausted; review/change the learning recipe in a new campaign')
        stop = self.state['generation'] + generations
        s = self.config['settings']
        while self.state['generation'] < stop:
            g = self.state['generation']; parent = self.state['champion']; promoted = False
            for target in s['training_stages']:
                self.checkpoint(status='collecting', training_deals=target)
                with self.timed('collection'):dataset = self.collect(g, target, parent, retry)
                self.checkpoint(status='training')
                with self.timed('training'):candidate = self.train(g, target, parent, dataset)
                if read(self.bot(candidate))['behavior_identity'] == read(self.bot(parent))['behavior_identity']:
                    atomic_json(self.root/f'g{g}/fit-{target}/unchanged.json',
                                dict(generation=g, training_deals=target, evaluation_deals=0,
                                     candidate=candidate, parent=parent, decision='unchanged'))
                    self.report()
                    continue
                self.checkpoint(status='evaluating', candidate=candidate)
                if s.get('screen_deals'):
                    with self.timed('screening'):
                        screen=self.arena(g,target,candidate,parent,s['screen_deals'],retry,screen_only=True)
                    if screen['decision']=='screen-reject':continue
                with self.timed('confirmation'):
                    with managed_ben(s.get('managed_ben'),self.root/f'g{g}/arena-{target}/ben.log',self.checkpoint):
                        for count in s['evaluation_looks']:
                            result = self.arena(g, target, candidate, parent, count, retry)
                            if result['decision'] == 'promote':
                                self.promote(result); promoted = True; break
                            if result['decision'] == 'futile': break
                if promoted: break
            if not promoted:
                self.checkpoint(status='exhausted')
                self.report()
                return self.state
        return self.state

    def report(self):
        results = [read(p) for p in sorted(self.root.glob('g*/arena-*/result-*.json'))]
        results += [read(p) for p in sorted(self.root.glob('g*/fit-*/unchanged.json'))]
        screens=[read(p) for p in sorted(self.root.glob('g*/arena-*/screen-*.json'))]
        latest = {}
        for r in results:
            key = (r['generation'], r['training_deals'])
            if key not in latest or r['evaluation_deals'] > latest[key]['evaluation_deals']: latest[key] = r
        for r in screens:
            if (r['generation'],r['training_deals']) not in latest:latest[(r['generation'],r['training_deals'])]=r
        rows = [latest[k] for k in sorted(latest)]
        atomic_json(self.root / 'progress.json', dict(state=self.state, candidates=rows))
        title = 'SMOKE TEST — NO STRENGTH CLAIMS' if self.config['settings'].get('smoke') else 'Self-improvement progress'
        lines = [f'# {title}', '', f'Current bot: `{self.state["champion"]}`. Status: `{self.state["status"]}`.', '',
                 'Positive IMP/board favors the candidate. Same deals, frozen auctions, partnerships swapped.',
                 'BEN delta is candidate versus BEN minus parent versus BEN on those same deals.', '',
                 '| Generation | Self-play deals | Arena deals | vs original | vs parent | vs BEN | BEN delta | Decision |',
                 '|---|---:|---:|---|---|---|---|---|']
        def cell(x): return f'{x["mean"]:+.3f} [{x["low"]:+.3f}, {x["high"]:+.3f}]'
        for r in rows:
            if r['decision']=='unchanged':
                lines.append(f'| {r["generation"]} | {r["training_deals"]} | 0 | — | — | — | — | unchanged |')
                continue
            if r.get('screen_only'):
                lines.append(f'| {r["generation"]} | {r["training_deals"]} | {r["evaluation_deals"]} | — | '
                             f'{cell(r["vs_parent"])} | — | — | {r["decision"]} |')
                continue
            d = r['descriptive']
            lines.append(f'| {r["generation"]} | {r["training_deals"]} | {r["evaluation_deals"]} | '
                         f'{cell(d["vs_original"])} | {cell(r["vs_parent"])} | {cell(d["vs_ben"])} | '
                         f'{cell(r["improvement_vs_ben"])} | {r["decision"]} |')
        lines += ['', 'Original/BEN columns show descriptive 95% intervals. Parent/BEN-delta columns use',
                  'the predeclared multiplicity-adjusted promotion intervals. Failed games block the gate.',
                  'These are approximate paired Student-t intervals over independent deals; no exact sequential guarantee.',
                  'Timing and trick swings are recorded in progress.json; results are as-configured, not equal-wall-time.', '']
        (self.root / 'progress.md').write_text('\n'.join(lines))


def initialize(root, settings):
    root = Path(root).resolve(); root.mkdir(parents=True, exist_ok=True)
    if (root / 'campaign.json').exists(): raise ValueError('Campaign already exists')
    settings = json.loads(json.dumps(settings))
    if min(settings[k] for k in ('workers','shard_size','board_timeout','arena_board_timeout','command_timeout')) <= 0:
        raise ValueError('Positive worker counts, shard sizes and timeouts required')
    for key in ('training_stages', 'evaluation_looks'):
        values = settings[key]
        if not values or values != sorted(set(values)) or any(not isinstance(v,int) or v<2 for v in values):
            raise ValueError('Expected strictly increasing positive stage sizes')
        if any(v % settings['shard_size'] for v in values):
            raise ValueError('Stage sizes must be multiples of shard_size for stable cumulative chunks')
    if not 0 < settings['family_alpha'] < 1 or settings['minimum_imp_gain'] < 0:
        raise ValueError('Invalid promotion thresholds')
    if not 0 <= settings.get('selfplay_exploration',0.) <= 1 or settings.get('arena_workers',1) < 1:
        raise ValueError('Invalid exploration or arena worker count')
    screen=settings.get('screen_deals',0)
    if screen and (screen<2 or screen % settings['shard_size']):
        raise ValueError('Screen size must be a positive multiple of shard_size')
    for role in ('initial', 'original', 'ben'):
        if settings[role] not in settings['bots']: raise ValueError(f'Missing {role} bot definition')
    for name, spec in settings.pop('bots').items(): freeze_bot(root, name, spec)
    pins = {str(Path(p).resolve()):sha(p) for p in settings.pop('pinned_files', [])}
    config = dict(schema=1, campaign_id=settings.pop('campaign_id'), checkout=str(Path(__file__).resolve().parents[1]), pins=pins,
                  source_sha256=source_hash(), settings=settings, settings_sha256=digest(settings))
    atomic_json(root / 'campaign.json', config)
    atomic_json(root / 'state.json', dict(schema=1, champion=settings['initial'], generation=1,
                next_version=3, promotions=[], status='prepared', training_deals=0))
    c = Campaign(root)
    try:
        for path in settings.get('exclusion_files', []):
            for did in read(path)['deal_ids']:
                c.db.execute('INSERT OR IGNORE INTO deals VALUES (?,?,?,?)', (did, 'prior', path, 'reserved'))
        c.db.commit(); c.report()
    finally: c.close()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('init','check','run','status','report','size-arena'))
    p.add_argument('--root', type=Path)
    p.add_argument('--config', type=Path)
    p.add_argument('--generations', type=int, default=1)
    p.add_argument('--retry-failures', action='store_true')
    p.add_argument('--effect', type=float, help='Target IMP/board gain above promotion margin in both endpoints')
    p.add_argument('--sd-parent', type=float, help='Prior pilot SD of paired IMPs versus parent')
    p.add_argument('--sd-ben-delta', type=float, help='Prior pilot SD of paired BEN improvement')
    p.add_argument('--power', type=float, default=.8)
    a = p.parse_args(argv)
    if a.generations < 1: p.error('--generations must be positive')
    if a.action=='size-arena':
        if any(v is None for v in (a.effect,a.sd_parent,a.sd_ben_delta)):
            p.error('--effect, --sd-parent and --sd-ben-delta required')
        print(json.dumps(plan_arena(a.effect,a.sd_parent,a.sd_ben_delta,joint_power=a.power),indent=2));return
    if a.root is None:p.error('--root required')
    if a.action=='status':
        # Read the atomically replaced state without taking the writer's lock.
        print(json.dumps(read(a.root/'state.json'),indent=2));return
    with writer_lock(a.root):
        if a.action == 'init':
            if not a.config: p.error('--config required for init')
            initialize(a.root, read(a.config)); print('Prepared; nothing started.'); return
        c = Campaign(a.root)
        try:
            if a.action == 'check': result = c.preflight()
            elif a.action == 'run': result = c.run(a.generations, a.retry_failures)
            elif a.action == 'report': c.report(); result = c.state
            else: result = c.state
            print(json.dumps(result, indent=2))
        finally: c.close()


if __name__ == '__main__': main()
