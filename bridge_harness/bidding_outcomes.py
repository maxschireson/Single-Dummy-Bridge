"""Information-legal bidding examples from observed, unbranched table results.

These greedy logs support outcome regression and advantage-weighted imitation.
They do not support importance-sampled estimates of unchosen policies. No neural
probability is substituted for an unavailable behavior propensity.
"""
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from .bidding_env import BidObservation, CALL_ID, deal_key, encode, legal_mask, pack_inputs
from .core import Board, imps, normalize_bid, score, vulnerable


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_record(row):
    if row.get('table_kind') != 'unbranched-root' or not row.get('fork_outcomes_excluded'):
        raise ValueError('Only unbranched actual outcomes are accepted')
    if row.get('split') not in ('train', 'validation'):
        raise ValueError('Missing preserved source partition')
    board = Board.from_dict(row['board'])
    if not board.auction:
        raise ValueError('An actual auction is required')
    if row['family'] != deal_key(board.hands, True):
        raise ValueError('Family is not the canonical rotation-invariant deal')
    if board.contract is None:
        expected = 0
    else:
        tricks = row['declarer_tricks']
        if not isinstance(tricks, int) or not 0 <= tricks <= 13:
            raise ValueError('Invalid actual trick count')
        expected = score(board.contract, tricks,
                         vulnerable(board.vulnerability, board.contract.declarer))
        expected *= 1 if board.contract.declarer % 2 == 0 else -1
    if expected != row['ns_score']:
        raise ValueError('Actual score disagrees with contract, tricks, and vulnerability')
    return board


def prepare(rows, sources):
    """One example per auction decision; average repeated actual table returns.

    Return utility is signed IMP(score relative to zero)/10, NOT observed paired
    IMP gain. A fitted information-legal baseline adjusts for hand strength.
    Every family has mass one, split equally between the two partnerships.
    """
    grouped = {}; splits = {}; seen = {}; counts = Counter()
    for row in rows:
        if row['source'] not in sources:
            counts['excluded_source_tables'] += 1
            continue
        board = validate_record(row)
        family = row['family']; split = row['split']
        if family in splits and splits[family] != split:
            raise ValueError('Deal family crosses train/validation')
        splits[family] = split
        identity = row['trajectory_identity']
        fingerprint = json.dumps(row, sort_keys=True)
        if identity in seen:
            if seen[identity] != fingerprint:
                raise ValueError('Conflicting duplicate trajectory')
            counts['duplicate_tables'] += 1
            continue
        seen[identity] = fingerprint
        key = (board.hands, board.dealer, board.vulnerability, board.auction)
        item = grouped.setdefault(key, dict(board=board, family=family, split=split, returns=[]))
        item['returns'].append(imps(row['ns_score']) / 10.)
        counts['actual_tables'] += 1
        counts['source:' + row['source']] += 1
    if not grouped:
        raise ValueError('No eligible actual outcomes')
    examples = []
    for item in grouped.values():
        board = item['board']; reward = float(np.mean(item['returns']))
        for turn, call in enumerate(board.auction):
            seat = (board.dealer + turn) % 4
            obs = BidObservation(board.hands[seat], seat, board.dealer,
                                 board.vulnerability, board.auction[:turn])
            action = CALL_ID[normalize_bid(call)]
            mask = legal_mask(board.dealer, board.auction[:turn])
            if not mask[action]:
                raise ValueError('Logged bid is illegal')
            examples.append(dict(x=encode(obs), mask=mask, action=action,
                                 reward=reward * (1 if seat % 2 == 0 else -1),
                                 family=item['family'], split=item['split'], side=seat % 2))
    masses = Counter((e['family'], e['side']) for e in examples)
    for e in examples:
        e['weight'] = .5 / masses[(e['family'], e['side'])]
    counts['distinct_auctions'] = len(grouped)
    counts['decisions'] = len(examples)
    for split in ('train', 'validation'):
        counts[split + '_families'] = sum(s == split for s in splits.values())
        counts[split + '_decisions'] = sum(e['split'] == split for e in examples)
    return examples, dict(counts)


def load_outcomes(path, manifest, sources):
    meta = json.loads(Path(manifest).read_text())
    if sha(path) != meta['sha256']:
        raise ValueError('Outcome archive hash mismatch')
    with gzip.open(path, 'rt') as f:
        return prepare((json.loads(line) for line in f), sources)


def arrays(examples):
    x, lengths = pack_inputs([e['x'] for e in examples])
    return dict(x=x, lengths=lengths, masks=np.array([e['mask'] for e in examples]),
                actions=np.array([e['action'] for e in examples], np.int32),
                reward=np.array([e['reward'] for e in examples], np.float32),
                weight=np.array([e['weight'] for e in examples], np.float32),
                family=np.array([e['family'] for e in examples]),
                split=np.array([e['split'] for e in examples]))


def fit_ridge(features, target, weights, alpha=10.):
    """Fixed-regularization baseline, fitted only on the supplied families."""
    x = np.asarray(features, np.float64); y = np.asarray(target, np.float64)
    w = np.asarray(weights, np.float64)
    mean = np.average(x, axis=0, weights=w)
    scale = np.sqrt(np.average((x-mean)**2, axis=0, weights=w))
    scale = np.maximum(scale, .05)
    z = (x-mean)/scale
    ym = float(np.average(y, weights=w))
    coef = np.linalg.solve(z.T @ (w[:, None]*z) + alpha*np.eye(z.shape[1]),
                           z.T @ (w*(y-ym)))
    return dict(mean=mean, scale=scale, coef=coef, intercept=np.array(ym))


def predict_ridge(model, features):
    return ((features-model['mean'])/model['scale']) @ model['coef'] + model['intercept']


def crossfit_baseline(features, data, folds=5):
    training = data['split'] == 'train'
    fold = np.array([int(f[8:16], 16) % folds for f in data['family']])
    predictions = np.zeros(len(features))
    for k in range(folds):
        fit = training & (fold != k); held = training & (fold == k)
        if not fit.any() or not held.any():
            raise ValueError('Empty cross-fitting fold')
        model = fit_ridge(features[fit], data['reward'][fit], data['weight'][fit])
        predictions[held] = predict_ridge(model, features[held])
    full = fit_ridge(features[training], data['reward'][training], data['weight'][training])
    predictions[~training] = predict_ridge(full, features[~training])
    return predictions.astype(np.float32), full, fold


def advantage_weights(reward, baseline, temperature=.6, cap=4.):
    if temperature <= 0 or cap < 1:
        raise ValueError('Invalid advantage weighting')
    return np.exp(np.clip((reward-baseline)/temperature, -np.log(cap), np.log(cap)))


def family_metrics(data, probabilities, anchor, outcome_weights, mask):
    ix = np.flatnonzero(mask); p = probabilities[ix]; q = anchor[ix]
    ce = -np.log(np.maximum(p[np.arange(len(ix)), data['actions'][ix]], 1e-12))
    kl = np.sum(q*(np.log(np.maximum(q, 1e-12))-np.log(np.maximum(p, 1e-12))), axis=1)
    groups = defaultdict(lambda: np.zeros(6))
    for j, i in enumerate(ix):
        w = float(data['weight'][i]); ow = w*float(outcome_weights[i])
        groups[data['family'][i]] += [ow*ce[j], ow, w*ce[j], w, w*kl[j],
                                      w*(np.argmax(p[j]) != np.argmax(q[j]))]
    rows = {f: dict(weighted_nll=float(a[0]/a[1]), nll=float(a[2]/a[3]),
                    kl=float(a[4]/a[3]), changed=float(a[5]/a[3])) for f, a in groups.items()}
    means = {k: float(np.mean([r[k] for r in rows.values()])) for k in next(iter(rows.values()))}
    means['families'] = len(rows); means['decisions'] = len(ix)
    return means, rows


def paired_loss(before, after):
    if set(before) != set(after):
        raise ValueError('Mismatched evaluation families')
    delta = np.array([before[f]['weighted_nll']-after[f]['weighted_nll'] for f in before])
    se = float(delta.std(ddof=1)/np.sqrt(len(delta))) if len(delta)>1 else None
    return dict(reduction=float(delta.mean()), se=se, families=len(delta),
                descriptive_95=[float(delta.mean()-1.96*se), float(delta.mean()+1.96*se)] if se else None)
