"""Frozen mixed environments, random local audits, and matched whole-bot play.

Each unique deal has two main tables with the same focal seats and opponent.
The focal partnership alternates NS/EW independently of results. The candidate
table also supplies recursive random audits; the reference table is never an
unmatched historical score. Only complete replay-checked deals are committed.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import math
from pathlib import Path
import random
import time

import numpy as np

from .auction_policy import AuctionSelectorWeights, encode_decision
from .belief_capacity import Weights
from .bidding_sampling import AuctionWeights, WeightedSampler
from .bidding_env import deal_key
from .core import Board, Game, SEATS, card, imps, symbol
from .fork_audit import ForkBudget, collect_board, stream
from .improvement import read
from .loop_registry import sha, source_hash
from .players import Decision, PIMCPlayer
from .policy_selector import SelectorWeights
from .runner import replay
from .selfplay import atomic_json
from .training import digest


class IMPSelector(AuctionSelectorWeights):
    """Contrast-trained neural action scores; shared state value cancels."""
    def predict(self, x):
        w = self.weights
        state = np.concatenate([x['state'], w['call_embedding'][x['calls']].reshape(len(x['state']), -1),
                                w['seat_embedding'][x['seats']].reshape(len(x['state']), -1)], 1)
        h = np.maximum(state @ w['state_hidden_kernel'] + w['state_hidden_bias'], 0)
        shared = np.broadcast_to(h[:, None, :], (len(h), x['actions'].shape[1], h.shape[1]))
        z = np.concatenate([x['actions'], shared], -1)
        for name in ('action_hidden', 'action_hidden_2'):
            z = np.maximum(z @ w[name + '_kernel'] + w[name + '_bias'], 0)
        return (z @ w['action_score_kernel'] + w['action_score_bias'])[..., 0] + float(w.get('imp_q_scale', 0.))*x['q']


def selector(path):
    with np.load(path, allow_pickle=False) as z:
        cls = IMPSelector if 'imp_neural' in z else AuctionSelectorWeights if 'call_embedding' in z or 'v5_mode' in z else SelectorWeights
    return cls(path)


class ArenaPlayer(PIMCPlayer):
    def __init__(self, spec, root, reference=None):
        self.spec = spec
        self.selector = selector(Path(root) / spec['policy']) if spec.get('policy') else None
        self.reference = selector(Path(root) / reference['policy']) if reference else None
        belief = Path(root) / spec['belief'] if spec.get('belief') else None
        if belief:
            self.belief = (Weights if spec['belief_kind'] == 'public' else AuctionWeights)(belief)
            super().__init__(samples=spec['samples'], objective='tricks', batch=True, near_tie=spec['near_tie'],
                sampler_factory=lambda o: WeightedSampler(o, self.belief.logits(o), 1.),
                layout_reduction=spec.get('layout_reduction'))
        else:
            super().__init__(samples=spec['samples'], objective='tricks', batch=True, near_tie=spec['near_tie'],
                layout_reduction=spec.get('layout_reduction'))

    def choose(self, o, rng):
        result = super().choose(o, rng)
        d = result.details
        if self.selector is None: return result
        if d.get('forced') or sum(p > 0 for p in d['behavior_probabilities'].values()) < 2:
            return result
        ranking = random.Random(); ranking.setstate(rng.getstate())
        _, values = self.selector.choose(o, d, ranking)
        best = max(values.values())
        ties = {c for c, v in values.items() if abs(v - best) <= 1e-7}
        epsilon = self.spec.get('exploration', 0.)
        probs = {c: epsilon / len(values) + (1 - epsilon) * (c in ties) / len(ties) for c in values}
        ticket = rng.random()
        for chosen, probability in sorted(probs.items()):
            ticket -= probability
            if ticket <= 0: break
        details = dict(d, selector='mixed-arena-' + self.spec['id'],
            proposal_probabilities=d['behavior_probabilities'],
            behavior_probabilities={symbol(c): p for c, p in probs.items()},
            selected_probability=probs[chosen], selector_predictions={symbol(c): v for c, v in values.items()},
            selected_pimc_gap=d['estimates'][symbol(chosen)]['gap_to_best'])
        if self.reference:
            reference_rng = random.Random(); reference_rng.setstate(rng.getstate())
            ref, _ = self.reference.choose(o, d, reference_rng)
            details.update(reference_card=symbol(ref),
                expected_gain_imps=float(values[chosen] - values[ref]) if isinstance(self.selector, IMPSelector) else None,
                prediction_units='matched-fork-imps' if isinstance(self.selector, IMPSelector) else 'remaining-partnership-tricks')
        return Decision(chosen, details)


def mixture(roster):
    if not roster or len(set(roster)) != len(roster): raise ValueError('Distinct nonempty roster required')
    # Unrepresented geometric tail stays on the oldest available actual version.
    return [dict(version=v, weight=2. ** (-i-1) if i < len(roster)-1 else 2. ** (-i))
            for i, v in enumerate(roster)]


def schedule(manifest, index):
    rng = stream(manifest['seed'], 'environment', index)
    ticket = rng.random()
    for row in manifest['mixture']:
        ticket -= row['weight']
        if ticket <= 0: break
    # Hash-derived side avoids correlation with dealer/vulnerability cycles.
    return row['version'], stream(manifest['seed'], 'focal-side', index).randrange(2)


def split(family):
    return 'validation' if int(family[:8], 16) % 5 == 0 else 'train'


def verify_generation(root, manifest):
    if digest({k:v for k,v in manifest.items() if k != 'identity'}) != manifest['identity']:
        raise ValueError('Generation manifest changed')
    if source_hash() != manifest['source_sha256']: raise ValueError('Pinned generation source changed')
    for file, expected in manifest.get('runtime_sha256', {}).items():
        if sha(Path(__file__).resolve().parents[1]/file) != expected: raise ValueError('Pinned arena runtime changed')
    for spec in manifest['bots'].values():
        if digest({k:v for k,v in spec.items() if k != 'identity'}) != spec['identity']:
            raise ValueError('Bot identity changed')
        for key, expected in spec['artifact_sha256'].items():
            if sha(Path(root) / spec[key]) != expected: raise ValueError('Frozen bot artifact changed')
    if sha(Path(root) / manifest['corpus']) != manifest['corpus_sha256']: raise ValueError('Frozen corpus changed')


def run_board(root, manifest, board_dict, index):
    board = Board.from_dict(board_dict)
    opponent, side = schedule(manifest, index)
    candidate, reference = manifest['candidate'], manifest['reference']
    specs = manifest['bots']
    players = dict(candidate=ArenaPlayer(specs[candidate], root, specs[reference]),
                   reference=ArenaPlayer(specs[reference], root),
                   environment=ArenaPlayer(specs[opponent], root))
    versions = dict(candidate=specs[candidate]['identity'], reference=specs[reference]['identity'],
                    opponent=specs[opponent]['identity'])
    seed = int(digest([manifest['seed'], index, 'play'])[:12], 16)
    try:
        control_assignment = ['reference' if s % 2 == side else 'environment' for s in range(4)]
        control = collect_board(board, players, control_assignment, seed,
            ForkBudget(probability=0, multiplier=1, max_depth=0), versions)
        # Both main tables fund the shared branch budget, once per family.
        budget = ForkBudget(**manifest['audit'], base_cpu=control['compute']['base_cpu'])
        assignment = ['candidate' if s % 2 == side else 'environment' for s in range(4)]
        focal = collect_board(board, players, assignment, seed, budget, versions)
        difference = (focal['tables'][0]['ns_score'] - control['tables'][0]['ns_score']) * (1 if side == 0 else -1)
        r = dict(schema='mixed-fork-pair-v1', status='ok', generation=manifest['generation'], index=index,
            family=deal_key(board.hands, True), board=board.to_dict(), split=split(deal_key(board.hands, True)),
            candidate=candidate, reference=reference, opponent=opponent, focal_side=side,
            versions=versions, manifest_identity=manifest['identity'], focal=focal, control=control,
            score_difference=difference, imps=imps(difference), completed_epoch=time.time(),
            base_cpu=budget.base_cpu, branch_cpu=budget.branch_cpu)
        validate_pair(r, manifest, board, index)
        return r
    finally:
        for player in players.values(): player.close()


def validate_pair(r, manifest, board, index):
    opponent, side = schedule(manifest, index)
    if (r['board'] != board.to_dict() or r['index'] != index or r['manifest_identity'] != manifest['identity']
        or r['opponent'] != opponent or r['focal_side'] != side or r['family'] != deal_key(board.hands, True)
        or r['split'] != split(r['family']) or r['candidate'] != manifest['candidate'] or r['reference'] != manifest['reference']):
        raise ValueError('Mismatched frozen paired record')
    for label in ('focal', 'control'):
        e = r[label]; replay(e)
        if e['versions'] != r['versions'] or e['board'] != r['board']: raise ValueError('Nested record mismatch')
        focal_name = 'candidate' if label == 'focal' else 'reference'
        expected = [focal_name if s % 2 == side else 'environment' for s in range(4)]
        if e['assignments'] != expected: raise ValueError('Changed partnership')
        for t in e['tables']:
            for action in t['actions']:
                if not action.get('counterfactual_forced') and action['player'] != expected[SEATS.index(action['controller'])]:
                    raise ValueError('Wrong controller')
        for audit in e['audits']:
            a = e['tables'][audit['candidate_table']]; b = e['tables'][audit['reference_table']]; ply = audit['ply']
            if [x['card'] for x in a['actions'][:ply]] != [x['card'] for x in b['actions'][:ply]]:
                raise ValueError('Counterfactual prefix mismatch')
            if audit['gain_imps'] != imps((a['ns_score']-b['ns_score'])*(1 if audit['actor'] % 2 == 0 else -1)):
                raise ValueError('Audit reward mismatch')
    delta = (r['focal']['tables'][0]['ns_score'] - r['control']['tables'][0]['ns_score']) * (1 if side == 0 else -1)
    if r['score_difference'] != delta or r['imps'] != imps(delta): raise ValueError('Bad pair score')


def compact(r):
    audits = r['focal']['audits']
    actual = [e for e in audits if not e['identical_action']]
    return dict(index=r['index'], family=r['family'], split=r['split'], imps=r['imps'], opponent=r['opponent'],
        audits=len(audits), deviations=len(actual), recursive=sum(e['depth'] > 0 for e in actual),
        local_imp_sum=sum(e['gain_imps'] for e in actual), skips=len(r['focal']['budget_skips']),
        tables=len(r['focal']['tables'])+1, base_cpu=r['base_cpu'], branch_cpu=r['branch_cpu'],
        completed_epoch=r['completed_epoch'])


def summarize(rows, manifest):
    from scipy.stats import t
    rows = sorted(rows, key=lambda r: r['index'])
    values = np.array([r['imps'] for r in rows], float); n = len(values)
    mean = float(values.mean()) if n else None
    half = float(t.ppf(.975, n-1)*values.std(ddof=1)/math.sqrt(n)) if n > 1 else None
    contiguous = 0
    for row in rows:
        if row['index'] != contiguous: break
        contiguous += 1
    looks = [k for k in manifest['demotion_looks'] if k <= contiguous]
    demotion = None
    # Predeclared looks, Bonferroni within generation and summable across generations.
    alpha = .05 / (manifest['generation']*(manifest['generation']+1)*len(manifest['demotion_looks']))
    for k in looks:
        v = values[:k]; se = v.std(ddof=1)/math.sqrt(k)
        upper = float(v.mean()+t.ppf(1-alpha, k-1)*se)
        if upper < 0:
            demotion = dict(boards=k, mean_imps=float(v.mean()), upper_bound=upper, one_sided_alpha=alpha)
            break
    base = sum(r['base_cpu'] for r in rows); branch = sum(r['branch_cpu'] for r in rows)
    groups = {}
    for op in sorted({r['opponent'] for r in rows}):
        v = [r['imps'] for r in rows if r['opponent'] == op]
        groups[op] = dict(boards=len(v), imps=sum(v), mean_imps=sum(v)/len(v))
    return dict(completed=n, target=manifest['target'], complete=n==manifest['target'], contiguous=contiguous,
        total_imps=int(values.sum()), mean_imps=mean, descriptive_95_ci=[mean-half, mean+half] if half is not None else None,
        wins=int((values>0).sum()), losses=int((values<0).sum()), ties=int((values==0).sum()),
        audited_deviations=sum(r['deviations'] for r in rows), audits=sum(r['audits'] for r in rows),
        recursive_deviations=sum(r['recursive'] for r in rows), budget_skips=sum(r['skips'] for r in rows),
        tables=sum(r['tables'] for r in rows), split_boards=dict(Counter(r['split'] for r in rows)),
        base_cpu=base, branch_cpu=branch, compute_multiplier=(base+branch)/base if base else None,
        by_opponent=groups, demotion=demotion, best=manifest['reference'] if demotion else manifest['candidate'],
        candidate_status='demoted' if demotion else 'latest-validated-default', epoch=time.time(),
        interpretation='Whole-bot matched IMPs. Local audit rewards are training contrasts, never summed into the match score.',
        next_step='train-successor' if n==manifest['target'] else 'collect')

# Schema dispatch preserves validation of retained substitution training data.
_legacy_run_board, _legacy_validate_pair = run_board, validate_pair
_legacy_compact, _legacy_summarize = compact, summarize

def run_board(root, manifest, board_dict, index):
    if manifest.get('protocol') == 'direct-pairs-v1':
        from .direct_arena import run_board as direct
        return direct(root, manifest, board_dict, index)
    return _legacy_run_board(root, manifest, board_dict, index)

def validate_pair(r, manifest, board, index):
    if manifest.get('protocol') == 'direct-pairs-v1':
        from .direct_arena import validate_pair as direct
        return direct(r, manifest, board, index)
    return _legacy_validate_pair(r, manifest, board, index)

def compact(r):
    if r.get('schema') == 'direct-fork-pair-v1':
        from .direct_arena import compact as direct
        return direct(r)
    return _legacy_compact(r)

def summarize(rows, manifest):
    if manifest.get('protocol') == 'direct-pairs-v1':
        from .direct_arena import summarize as direct
        return direct(rows, manifest)
    return _legacy_summarize(rows, manifest)
