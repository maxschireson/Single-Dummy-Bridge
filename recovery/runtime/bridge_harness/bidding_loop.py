"""Resumable DDS-only bidding league. Run via scripts/run_bidding_loop.py."""
import argparse
from dataclasses import asdict, dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

import numpy as np

from .bidding_env import TableCache, make_board, paired_auctions
from .bidding_ppo import Policy, PPO
from .loop_stats import estimate


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.flush(); os.fsync(f.fileno())
    os.replace(temporary, path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class Config:
    seed: int = 2026110807
    train_stages: tuple = (10000, 50000, 250000)
    batch_pairs: int = 128
    dev_pairs: int = 1000
    confirmation_pairs: int = 10000
    max_attempts: int = 20
    dds_workers: int = 2
    tf_threads: int = 2
    ppo_epochs: int = 2
    minibatch: int = 256
    learning_rate: float = 1e-5
    exploration: float = .005
    anchor_weight: float = .02
    family_alpha: float = .05

    def validate(self):
        counts = (self.batch_pairs, self.dev_pairs, self.confirmation_pairs, self.max_attempts,
                  self.dds_workers, self.tf_threads, self.ppo_epochs, self.minibatch)
        if min(counts) < 1 or min(self.dev_pairs, self.confirmation_pairs) < 2:
            raise ValueError('Positive sizes and at least two evaluation pairs required')
        if not self.train_stages or list(self.train_stages) != sorted(set(self.train_stages)) or min(self.train_stages)<1:
            raise ValueError('Training stages must be positive and strictly increasing')
        if not 0 <= self.exploration < 1 or not 0 < self.family_alpha < 1 or self.learning_rate <= 0:
            raise ValueError('Invalid optimizer/exploration settings')


def promotion(rows, attempt, stages, family_alpha=.05):
    if len({r['deal_id'] for r in rows}) != len(rows):
        raise ValueError('Confirmation deals must be independent')
    # Sum over attempts 1/[a(a+1)] = 1. One fixed-size look per stage.
    alpha = family_alpha/(attempt*(attempt+1)*stages*3)
    adjusted = {key: estimate([r[key] for r in rows], alpha)
                for key in ('vs_parent', 'vs_original', 'vs_league')}
    return dict(promoted=all(v['informative'] and v['low'] > 0 for v in adjusted.values()),
                adjusted_alpha=alpha, adjusted=adjusted,
                descriptive={key: estimate([r[key] for r in rows]) for key in adjusted})


def run(root, origin, library, config, *, run_seconds=3600, max_updates=None):
    config.validate()
    root, origin, library = Path(root).resolve(), Path(origin).resolve(), Path(library).resolve()
    root.mkdir(parents=True, exist_ok=True)
    lock = (root/'worker.lock').open('a+')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(json.dumps(dict(status='already_running', run=str(root))), flush=True)
        return
    start = time.monotonic()
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(config.tf_threads)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(config.seed)
    source_files = ['bidding_env.py', 'bidding_ppo.py', 'bidding_loop.py', 'core.py', 'dds.py', 'loop_stats.py']
    manifest = dict(schema='dds-bidding-loop-v1', config=asdict(config),
                    origin=str(origin), origin_sha256=sha(origin), dds_library=str(library),
                    dds_sha256=sha(library), tensorflow=tf.__version__,
                    source_sha256={f: sha(Path(__file__).with_name(f)) for f in source_files},
                    reward='IMPs(NS score candidate-NS room minus NS score candidate-EW room)',
                    information='Own 13 cards, public past auction, dealer, vulnerability only',
                    evaluation='Greedy legal net-only calls; DD terminal scores; no card play',
                    confirmation='Fresh deal families per attempt/stage; fixed-size, alpha-spent t intervals')
    manifest = json.loads(json.dumps(manifest))
    if (root/'manifest.json').exists():
        if json.loads((root/'manifest.json').read_text()) != manifest:
            raise ValueError('Resume provenance/config mismatch: start a separate run or explicitly migrate it')
    else:
        atomic_json(root/'manifest.json', manifest)
    state_path = root/'state.json'
    if state_path.exists():
        state = json.loads(state_path.read_text())
    else:
        state = dict(attempt=1, stage=0, trained_pairs=0, total_train_pairs=0, step=0,
                     phase='train', parent=str(origin), champions=[str(origin)], checkpoint=None,
                     elapsed_seconds=0., promotions=0)
        atomic_json(state_path, state)

    anchor = Policy.load(origin)

    def new_trainer(path):
        policy = Policy.load(path, critic=True)
        trainer = PPO(policy, anchor, learning_rate=config.learning_rate,
                      epsilon=config.exploration, anchor_weight=config.anchor_weight)
        return policy, trainer

    candidate, trainer = new_trainer(origin)
    if state['checkpoint']:
        trainer.restore(state['checkpoint'])
    loaded = {str(origin): anchor}

    def get_policy(path):
        if path not in loaded:
            loaded[path] = Policy.load(path)
        return loaded[path]

    cache = TableCache(root/'dds.sqlite', library, config.dds_workers)
    start_step = state['step']
    prior_elapsed = state['elapsed_seconds']

    def event(kind, **extra):
        status = dict(kind=kind, time_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                      attempt=state['attempt'], stage=state['stage'], phase=state['phase'],
                      trained_pairs=state['trained_pairs'], total_train_pairs=state['total_train_pairs'],
                      step=state['step'], elapsed_seconds=prior_elapsed+time.monotonic()-start,
                      solved_deals=cache.counts(), **extra)
        atomic_json(root/'status.json', status)
        with (root/'events.jsonl').open('a') as log:
            log.write(json.dumps(status, allow_nan=False)+'\n')
            log.flush()
        print(json.dumps(status), flush=True)

    def commit_state(save_weights=False):
        if save_weights:
            prefix = root/'checkpoints'/f"update-{state['step']:07d}"/'ckpt'
            state['checkpoint'] = trainer.save(prefix)
        state['elapsed_seconds'] = prior_elapsed+time.monotonic()-start
        atomic_json(state_path, state)
        # Keep the two latest optimizer checkpoints; promoted models remain separate.
        dirs = sorted((root/'checkpoints').glob('update-*'))
        for old in dirs[:-2]:
            if str(old) not in state['checkpoint']:
                shutil.rmtree(old)

    def expired():
        return (time.monotonic()-start >= run_seconds or
                (max_updates is not None and state['step']-start_step >= max_updates))

    def evaluate(phase):
        n = config.dev_pairs if phase == 'dev' else config.confirmation_pairs
        split = 'dev' if phase == 'dev' else 'test'
        eval_dir = root/'evaluations'/f"a{state['attempt']:03d}-s{state['stage']}-{phase}"
        eval_dir.mkdir(parents=True, exist_ok=True)
        seed = config.seed+state['attempt']*100003+state['stage']*1009+(50000000 if phase=='dev' else 100000000)
        opponent_paths = dict(vs_parent=state['parent'], vs_original=str(origin))
        older = state['champions'][:-1] or [str(origin)]
        all_rows = []
        for offset in range(0, n, config.batch_pairs):
            dest = eval_dir/f'{offset:07d}.json'
            if dest.exists():
                all_rows.extend(json.loads(dest.read_text()))
                continue
            if expired():
                return None
            boards = [make_board(seed, i, split) for i in range(offset, min(n, offset+config.batch_pairs))]
            tables = cache.get_many(boards, lambda done,total: event('dds', completed=offset,
                                    batch_dds_done=done, batch_dds_total=total, evaluation=phase))
            results = [dict(deal_id=b.id) for b in boards]
            common = {}
            for label in ('vs_parent', 'vs_original', 'vs_league'):
                paths = ([opponent_paths[label]]*len(boards) if label in opponent_paths else
                         [older[(offset+i) % len(older)] for i in range(len(boards))])
                signature = tuple(paths)
                if signature not in common:
                    rows, _ = paired_auctions(boards, tables, candidate, [get_policy(p) for p in paths],
                                               np.random.default_rng(seed+offset))
                    common[signature] = rows
                for result, row in zip(results, common[signature]):
                    result[label] = row['imps']
                    result[label+'_tables'] = row['tables']
            atomic_json(dest, results)
            all_rows.extend(results)
            event('evaluation', completed=len(all_rows), target=n, evaluation=phase,
                  means={k: float(np.mean([r[k] for r in all_rows])) for k in opponent_paths})
        result = promotion(all_rows, state['attempt'], len(config.train_stages), config.family_alpha)
        result.update(attempt=state['attempt'], stage=state['stage'], phase=phase,
                      trained_pairs=state['trained_pairs'], parent=state['parent'], pairs=n,
                      elapsed_seconds=prior_elapsed+time.monotonic()-start)
        if phase == 'dev':
            result['promoted'] = False
            result['screen_passed'] = all(v['mean'] > 0 for v in result['descriptive'].values())
        atomic_json(eval_dir/'summary.json', result)
        return result

    def advance_attempt(promoted):
        nonlocal candidate, trainer
        if promoted:
            state['promotions'] += 1
            dest = root/'champions'/f"B{state['promotions']:04d}.keras"
            candidate.save(dest)
            state['parent'] = str(dest)
            state['champions'].append(str(dest))
            atomic_json(dest.with_suffix('.json'), dict(sha256=sha(dest), attempt=state['attempt'],
                                                       stage=state['stage'], trained_pairs=state['trained_pairs']))
        else:
            candidate, trainer = new_trainer(state['parent'])
        state.update(attempt=state['attempt']+1, stage=0, trained_pairs=0, phase='train')
        if state['attempt'] > config.max_attempts:
            state['phase'] = 'complete'
        # Use a new checkpoint number even when resetting after an evaluation.
        state['step'] += 1
        commit_state(save_weights=True)

    try:
        event('started')
        while state['phase'] != 'complete' and not expired():
            if state['phase'] == 'train':
                goal = config.train_stages[state['stage']]
                if state['trained_pairs'] >= goal:
                    state['phase'] = 'dev'; commit_state(); continue
                count = min(config.batch_pairs, goal-state['trained_pairs'])
                offset = state['trained_pairs']
                seed = config.seed+state['attempt']*100003
                boards = [make_board(seed, i, 'train') for i in range(offset, offset+count)]
                begin = time.monotonic()
                tables = cache.get_many(boards, lambda done,total: event('dds', batch_dds_done=done,
                                                                        batch_dds_total=total))
                dds_seconds = time.monotonic()-begin
                rng = np.random.default_rng(np.random.SeedSequence([config.seed, state['attempt'], offset]))
                older = state['champions'][:-1] or [str(origin)]
                old = older[int(rng.integers(len(older)))]
                choices = rng.choice(3, size=count, p=[.5, .25, .25])
                paths = [state['parent'], old, str(origin)]
                opponents = [get_policy(paths[int(i)]) for i in choices]
                begin = time.monotonic()
                rows, decisions = paired_auctions(boards, tables, candidate, opponents, rng,
                                                  explore=True, epsilon=config.exploration)
                auction_seconds = time.monotonic()-begin
                begin = time.monotonic()
                metrics = trainer.train(decisions, rng, config.ppo_epochs, config.minibatch)
                update_seconds = time.monotonic()-begin
                # Persist the collected outcome before advancing the resumable checkpoint.
                batch_dir = root/'batches'/f"a{state['attempt']:03d}-{offset:07d}"
                atomic_json(batch_dir/'auctions.json', rows)
                atomic_json(batch_dir/'metrics.json', dict(**metrics, pairs=count, dds_seconds=dds_seconds,
                            auction_seconds=auction_seconds, update_seconds=update_seconds,
                            training_mean_imps=float(np.mean([r['imps'] for r in rows]))))
                state['trained_pairs'] += count; state['total_train_pairs'] += count; state['step'] += 1
                commit_state(save_weights=True)
                event('updated', dds_seconds=dds_seconds, auction_seconds=auction_seconds,
                      update_seconds=update_seconds, metrics=metrics,
                      training_mean_imps=float(np.mean([r['imps'] for r in rows])))
            else:
                phase = state['phase']
                result = evaluate(phase)
                if result is None:
                    break
                event('evaluated', result=result)
                if phase == 'dev' and result['screen_passed']:
                    state['phase'] = 'confirm'; commit_state(); continue
                if phase == 'confirm' and result['promoted']:
                    advance_attempt(True)
                elif state['stage']+1 < len(config.train_stages):
                    state.update(stage=state['stage']+1, phase='train'); commit_state()
                else:
                    advance_attempt(False)
        commit_state()
        event('complete' if state['phase'] == 'complete' else 'paused')
    finally:
        cache.close()
        lock.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', required=True, type=Path)
    p.add_argument('--initial-model', required=True, type=Path)
    p.add_argument('--dds-library', required=True, type=Path)
    p.add_argument('--config', type=Path)
    p.add_argument('--run-seconds', type=float, default=3600)
    p.add_argument('--max-updates', type=int)
    args = p.parse_args()
    values = json.loads(args.config.read_text()) if args.config else {}
    if 'train_stages' in values:
        values['train_stages'] = tuple(values['train_stages'])
    run(args.run, args.initial_model, args.dds_library, Config(**values),
        run_seconds=args.run_seconds, max_updates=args.max_updates)


if __name__ == '__main__':
    main()
