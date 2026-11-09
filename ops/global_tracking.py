"""Build dashboard totals from cumulative, deduplicated training/audit ledgers.

This is read-only with respect to collectors. Run in the publishing environment,
then publish the output as arena/global-stats.json on research/direct-pairs-current.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path


def integer(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError('Expected a nonnegative integer')
    return value


def play_equivalents(work):
    """One unit = two full table plays at 32 samples; forks count remaining plies.

    Each item describes actual played work, not a planned quota. main_tables is
    the count of complete table plays; fork_plies excludes replayed prefixes.
    This is nominal search-budget normalization, not measured CPU consumption.
    """
    result = 0.
    for row in work:
        samples = integer(row['samples'])
        if not samples:
            raise ValueError('Sample budget must be positive')
        result += (integer(row['main_tables']) + integer(row['fork_plies']) / 52) * samples / 64
    return result


def learning_metric(evaluation, equivalents):
    """Numerator is the isolated successor-minus-parent IMP gain per eval board."""
    if evaluation is None or equivalents is None or equivalents == 0:
        return None
    if not math.isfinite(equivalents) or equivalents < 0:
        raise ValueError('Invalid normalized training work')
    if evaluation['samples'] != 32 or not integer(evaluation['boards']):
        raise ValueError('Use a nonempty common 32-sample evaluation')
    gain = evaluation['gain_imps_per_board']
    interval = evaluation.get('gain_ci95')
    if not math.isfinite(gain):
        raise ValueError('Invalid IMP gain')
    if interval is not None and (len(interval) != 2 or not all(map(math.isfinite, interval)) or interval[0] > interval[1]):
        raise ValueError('Invalid gain interval')
    return dict(value=gain / equivalents,
                ci95=[x / equivalents for x in interval] if interval else None)


def build_tracking(baseline, ledger):
    out = deepcopy(baseline)
    if out['schema'] != 'bridge-global-tracking-v1':
        raise ValueError('Unknown baseline schema')
    for domain in ('bidding', 'play'):
        families = set()
        for dataset in ledger.get('training_datasets', []):
            if dataset['domain'] != domain:
                continue
            # IDs must already be canonical deal families, shared across datasets.
            for family, split in dataset['families'].items():
                if split == 'train':
                    families.add(family)
        complete = ledger.get('training_history_complete', {}).get(domain, False)
        if families or complete:
            previous = integer(out['training'][domain]['value'])
            if complete and len(families) < previous:
                raise ValueError('Complete history cannot silently discard confirmed boards')
            metric = out['training'][domain]
            metric.update(value=len(families) if complete else max(previous, len(families)),
                          coverage='exact' if complete else 'lower_bound',
                          detail='Distinct canonical training families across registered datasets; validation/test, repeated epochs, rooms and forks do not add boards.')

    runs = {r['id']: deepcopy(r) for r in out.get('audit_runs', [])}
    for run in ledger.get('audit_runs', []):
        # A run ID is the immutable manifest identity, not its mutable path/name.
        rows = {}
        for row in run['receipts']:
            key = integer(row['index'])
            count = integer(row['deviations'])
            if key in rows and rows[key] != count:
                raise ValueError('Conflicting duplicate receipt')
            rows[key] = count
        total = sum(rows.values())
        previous = runs.get(run['id'], {}).get('lines', 0)
        if total < previous:
            raise ValueError('Run receipts must include previously confirmed lines')
        runs[run['id']] = dict(id=run['id'], lines=total)
    if ledger.get('audit_runs'):
        out['audit_runs'] = list(runs.values())
        out['policy_audit_lines'].update(value=sum(r['lines'] for r in runs.values()),
            coverage='exact' if ledger.get('audit_history_complete') else 'lower_bound',
            detail='Completed nonidentical policy-audit continuations across registered runs, including recursive forks. Identical-action audits, skips and ordinary match tables are excluded.')

    if 'models' in ledger:
        for model in ledger['models']:
            integer(model['parameters'])
            decisions = model.get('decisions_seen')
            if decisions is not None:
                if decisions.get('kind') not in ('decisions', 'observations') or decisions.get('scope') != 'latest_fit':
                    raise ValueError('Training counts require an explicit kind and latest-fit scope')
                if decisions.get('coverage') == 'pending':
                    if decisions.get('value') is not None:
                        raise ValueError('Pending training count must be null')
                elif decisions.get('coverage') in ('exact', 'lower_bound'):
                    integer(decisions['value'])
                else:
                    raise ValueError('Unknown training-count coverage')
            if not model.get('sha256') or not model.get('component'):
                raise ValueError('Model identity and component required')
        out['models'] = deepcopy(ledger['models'])
    if 'generations' in ledger:
        out['generations'] = deepcopy(ledger['generations'])
        for gen in out['generations']:
            work = gen.get('new_training_work', {})
            play = play_equivalents(work['play']) if 'play' in work else None
            bidding = None
            calibration = work.get('bidding_calibration')
            if calibration:
                seconds = calibration['cpu_seconds_per_32_sample_pair']
                spent = work['bidding_cpu_seconds']
                if not math.isfinite(seconds) or seconds <= 0 or not math.isfinite(spent) or spent < 0:
                    raise ValueError('Invalid bidding cost calibration')
                bidding = spent / seconds
            gen['normalized_training_boards'] = dict(play=play, bidding=bidding)
            gen['learning_efficiency'] = {domain: learning_metric(gen.get('evaluations', {}).get(domain), denominator)
                for domain, denominator in [('bidding', bidding), ('play', play)]}
    out['updated_utc'] = datetime.now(timezone.utc).isoformat()
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = build_tracking(json.loads(args.baseline.read_text()), json.loads(args.ledger.read_text()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.out.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, indent=2) + '\n')
    temporary.replace(args.out)


if __name__ == '__main__':
    main()
