#!/usr/bin/env python3
"""Read frozen arena archives; distinguish Gen3 references from PIMC maxima.

No model fitting, board collection, or arena mutations. Archives are streamed
without extracting paths. All uncertainty is clustered by canonical deal.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import tarfile

EPS = 1e-7
IMP_LIMITS = (20, 50, 90, 130, 170, 220, 270, 320, 370, 430, 500, 600,
              750, 900, 1100, 1300, 1500, 1750, 2000, 2250, 2500, 3000, 3500, 4000)


def imps(x):
    return (1 if x >= 0 else -1) * sum(abs(x) >= k for k in IMP_LIMITS)


def stats(rows, value='gain_imps'):
    n = len(rows)
    if not n:
        return dict(n=0, families=0)
    groups = defaultdict(list)
    for row in rows:
        groups[row['family']].append(row[value])
    total = sum(sum(v) for v in groups.values())
    mean = total / n
    g = len(groups)
    se = (math.sqrt(g / (g - 1) * sum((sum(v) - len(v) * mean) ** 2
                                     for v in groups.values())) / n if g > 1 else None)
    family_means = [statistics.mean(v) for v in groups.values()]
    family_se = statistics.stdev(family_means) / math.sqrt(g) if g > 1 else None
    return dict(n=n, families=g, total=total, mean=mean, cluster_se=se,
                ci95=[mean - 1.96 * se, mean + 1.96 * se] if se is not None else None,
                family_equal_mean=statistics.mean(family_means), family_equal_se=family_se,
                positive=sum(r[value] > 0 for r in rows), negative=sum(r[value] < 0 for r in rows),
                zero=sum(r[value] == 0 for r in rows))


def subsets(rows):
    changed = [r for r in rows if not r['identical']]
    best = [r for r in rows if r['reference_gap'] <= EPS]
    result = {}
    for name, subset in [
        ('all_gen3_reference_audits', rows),
        ('changed_vs_gen3', changed),
        ('reference_is_global_pimc_best', best),
        ('changed_vs_global_pimc_best', [r for r in best if not r['identical']]),
        ('non_tie_override_vs_global_pimc_best', [r for r in best if r['candidate_gap'] > EPS]),
        ('tie_change_vs_global_pimc_best', [r for r in best if r['candidate_gap'] <= EPS and not r['identical']]),
        ('both_selectors_below_global_pimc_best', [r for r in rows if r['candidate_gap'] > EPS and r['reference_gap'] > EPS]),
    ]:
        result[name] = dict(imps=stats(subset), tricks=stats(subset, 'gain_tricks'))
    return result


def process(archive, label, commit, output, blobs=None):
    rows, decisions, episodes = [], [], []
    counts = Counter()
    manifest = None
    expected = json.loads(Path(blobs).read_text())['files'] if blobs else None
    seen = set()
    with tarfile.open(archive, 'r|gz') as tar:
        for member in tar:
            if member.name.endswith('/recovery/manifest.json'):
                manifest = json.load(tar.extractfile(member))
            if not re.search(r'/recovery/episodes/[0-9]+\.json\.gz$', member.name):
                continue
            raw = tar.extractfile(member).read()
            filename = member.name.rsplit('/', 1)[1]
            assert filename not in seen, filename
            seen.add(filename)
            blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            if expected:
                assert blob == expected[filename], filename
            e = json.loads(gzip.decompress(raw))
            assert int(filename.split('.')[0]) == e['index']
            episodes.append(dict(index=e['index'], family=e['family'], candidate=e['candidate'],
                                 pair=e['pair'], blob_sha=blob, manifest_identity=e['manifest_identity']))
            common_ids = set(e['regimes'].get('common', {}).get('tables', []))
            for room_id, room in e['unique_tables'].items():
                if room['board']['contract'] is None:
                    assert not room['audits'] and not any(t['actions'] for t in room['tables'])
                    counts['passed_out_rooms'] += 1
                    continue
                assert room['family'] == e['family']
                declarer = 'NESW'.index(room['board']['declarer'])
                base = dict(cohort=label, index=e['index'], family=e['family'], candidate=e['candidate'],
                            opponent=e['opponent'], room=room_id, common=room_id in common_ids)
                tables = room['tables']
                audits = {(a['candidate_table'], a['ply']): a for a in room['audits']}
                for ti, table in enumerate(tables):
                    for action in table['actions']:
                        if action.get('replayed_prefix') or action.get('counterfactual_forced'):
                            continue
                        if action.get('player') != 'candidate' or 'reference_card' not in action:
                            continue
                        estimates = action['estimates']
                        gap = estimates[action['card']]['gap_to_best']
                        ref_gap = estimates[action['reference_card']]['gap_to_best']
                        d = dict(base, depth=table['depth'], ply=action['ply'], candidate_gap=gap,
                                 reference_gap=ref_gap, identical=action['card'] == action['reference_card'],
                                 audited=(ti, action['ply']) in audits,
                                 audit_draw=action.get('audit_draw'), samples=action['samples'])
                        decisions.append(d)
                for audit in room['audits']:
                    a, b = tables[audit['candidate_table']], tables[audit['reference_table']]
                    ply, actor = audit['ply'], audit['actor']
                    action = a['actions'][ply]
                    assert a['status'] == b['status'] == 'ok'
                    assert a['depth'] == audit['depth']
                    assert action['player'] == 'candidate'
                    assert action['card'] == audit['candidate_card']
                    assert b['actions'][ply]['card'] == audit['reference_card'] == action['reference_card']
                    assert [x['card'] for x in a['actions'][:ply]] == [x['card'] for x in b['actions'][:ply]]
                    assert actor == 'NESW'.index(action['seat'])
                    gain = imps((a['ns_score'] - b['ns_score']) * (1 if actor % 2 == 0 else -1))
                    assert gain == audit['gain_imps']
                    gain_tricks = (a['declarer_tricks'] - b['declarer_tricks']) * (1 if actor % 2 == declarer % 2 else -1)
                    estimates = action['estimates']
                    best = max(v['utility'] for v in estimates.values())
                    cg = estimates[action['card']]['gap_to_best']
                    rg = estimates[audit['reference_card']]['gap_to_best']
                    assert abs(cg - (best - estimates[action['card']]['utility'])) < 1e-6
                    assert abs(rg - (best - estimates[audit['reference_card']]['utility'])) < 1e-6
                    rows.append(dict(base, depth=audit['depth'], ply=ply, actor=actor,
                                     role='declarer' if actor % 2 == declarer % 2 else 'defence',
                                     candidate_card=action['card'], reference_card=audit['reference_card'],
                                     candidate_gap=cg, reference_gap=rg,
                                     identical=audit['identical_action'], gain_imps=gain, gain_tricks=gain_tricks,
                                     samples=action['samples']))
                    counts['verified_audits'] += 1
                counts['budget_skips'] += len(room['budget_skips'])
                counts['continuation_tables'] += len(tables)
                counts['unique_rooms'] += 1
            if len(episodes) % 500 == 0:
                print(label, len(episodes), 'episodes', len(rows), 'audits', flush=True)
    if expected:
        assert set(expected) == seen, (len(expected), len(seen))
    summary = dict(cohort=label, commit=commit, episodes=len(episodes), families=len({e['family'] for e in episodes}),
                   counts=dict(counts), manifests=sorted({e['manifest_identity'] for e in episodes}),
                   audit_references=manifest.get('audit_references') if manifest else None,
                   candidates=sorted({e['candidate'] for e in episodes}), scopes={}, coverage={})
    for scope, predicate in [
        ('common_root', lambda r: r['common'] and r['depth'] == 0),
        ('all_unique_rooms_root', lambda r: r['depth'] == 0),
        ('all_unique_rooms_all_depths', lambda r: True),
    ]:
        scoped = [r for r in rows if predicate(r)]
        decisions_scope = [r for r in decisions if predicate(r)]
        summary['scopes'][scope] = {'all': subsets(scoped)}
        for candidate in summary['candidates']:
            summary['scopes'][scope][candidate] = subsets([r for r in scoped if r['candidate'] == candidate])
        overrides = [r for r in decisions_scope if r['candidate_gap'] > EPS]
        summary['coverage'][scope] = dict(
            selector_decisions=len(decisions_scope), overrides=len(overrides),
            override_with_gen3_global_best=sum(r['reference_gap'] <= EPS for r in overrides),
            override_audited_against_global_best=sum(r['reference_gap'] <= EPS and r['audited'] for r in overrides),
            override_gen3_agrees=sum(r['identical'] for r in overrides),
            total_audits=len(scoped))
    root_best = [r for r in rows if r['common'] and r['depth'] == 0 and r['reference_gap'] <= EPS and r['candidate_gap'] > EPS]
    summary['common_root_override_by_role'] = {role: dict(imps=stats([r for r in root_best if r['role'] == role]),
                                                        tricks=stats([r for r in root_best if r['role'] == role], 'gain_tricks'))
                                              for role in ('declarer', 'defence')}
    output.mkdir(parents=True, exist_ok=True)
    (output / f'{label}-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (output / f'{label}-episodes.json').write_text(json.dumps(episodes, separators=(',', ':')) + '\n')
    if manifest:
        (output / f'{label}-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    with gzip.GzipFile(str(output / f'{label}-audit-rows.jsonl.gz'), 'wb', mtime=0) as f:
        for row in rows:
            f.write((json.dumps(row, separators=(',', ':')) + '\n').encode())
    with gzip.GzipFile(str(output / f'{label}-decision-rows.jsonl.gz'), 'wb', mtime=0) as f:
        for row in decisions:
            f.write((json.dumps(row, separators=(',', ':')) + '\n').encode())
    print(label, 'DONE', summary['episodes'], summary['counts'], flush=True)
    print(json.dumps(summary['scopes']['common_root']['all'], indent=2), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--archive', required=True)
    p.add_argument('--label', required=True)
    p.add_argument('--commit', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--blobs')
    args = p.parse_args()
    process(args.archive, args.label, args.commit, args.output, args.blobs)
