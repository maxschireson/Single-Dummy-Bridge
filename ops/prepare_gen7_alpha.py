"""Freeze a Gen7 alpha cohort: a drained Gen6 run's unplayed deals, its bots unchanged, plus the Gen7 bots.

The Gen7 bots, their settings, the policy release and the match mix all come from the plan
(configs/round7-alpha.json); nothing about them is fixed here. A Gen7 bot is its Gen6 base bot
(same bidder, lead net, scorer, layout settings and sample count) with the gen7 engine, the
policy net, and the plan's `gen7` block written out in full, defaults included.

Carried over from the source run unchanged: tie-audit and fork settings, bidding conditions, room
seeding, the generation/variant labels the exporter keys on, and the facts about its corpus.

A plan may give the cohort's own `model_note` and `interpretation`; without them the alpha's are used.

Several machines can share one source run without playing a deal twice: each prepares with its
own `--shard K/N` (K from 0 to N-1) and gets every N-th unplayed deal starting at the K-th. The
shard is written into the manifest, so each machine's cohort has its own identity.

The source may also be a drained Gen7 cohort: a new plan then takes over the deals that cohort had
not played, with the same Gen7 bots (same settings, same identity) and a different match mix.

Gen 8 (nothing changes for a plan that uses none of it): a plan may give `systems`, the bidding system
each bot of the cohort declares, and a bot entry may give `bidder` (it bids by a system bidder, a
rule system, in place of its bidding net), `system_scorer` (true: it reads each side's calls by the
declared system, with the plan's `system_scorer` artifact) and `lead_systems` (the systems whose
auctions the lead net serves). docs/gen8_candidate_2026-11-12.md.

  python ops/prepare_gen7_alpha.py --source /path/to/drained/run --run /path/to/new/run [--plan configs/round7-alpha.json] [--shard K/N]
"""
import argparse
from copy import deepcopy
from dataclasses import asdict
import fcntl
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.arena_pairs import pair_members
from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import load, save
from bridge_harness.gen6 import Gen6Config
from bridge_harness.gen7 import ENGINE, resolved
from bridge_harness.loop_registry import sha, source_hash
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest
from ops.prepare_gen6 import verify_source

PLAN = ROOT / 'configs/round7-alpha.json'
GEN7_POLICY = 'artifacts/gen7/policy.npz'
POLICY_KEY = 'gen7_policy'                     # a bot's policy artifact unless its plan entry names another
POLICY_KEYS = re.compile(r'gen7_policy(_[a-z0-9]+)?')


def policy_key(entry):
    return entry.get('policy', POLICY_KEY)


def policy_path(key):
    """Where a policy release sits in a run. The first policy keeps the path it has always had, so a bot that
    uses it keeps its identity; any other is named by its artifact key."""
    return GEN7_POLICY if key == POLICY_KEY else f'artifacts/gen7/{key}.npz'
SYSTEM_SCORER_KEY = 'system_scorer'            # Gen 8: the artifact key of a system-aware hand-fit scorer
SYSTEM_SCORER = 'artifacts/gen8/system_scorer.npz'
RUNTIME = ('ops/gen5_runtime.py', 'ops/prepare_gen7_alpha.py')
# What the plan does not own: how tables are audited and forked, how rooms are seeded, the labels the
# exporter and report registration key on, and facts about the corpus the unplayed deals come from.
CARRIED = ('generation', 'variant', 'audit', 'ben_audit', 'bidding_conditions', 'gap_fork', 'two_self_rooms', 'independent_room_seeds',
           'independent_cohort', 'exclusion_families')


def load_plan(path=None, require_ready=True):
    plan = json.loads(Path(path or PLAN).read_text())
    if require_ready and (not plan['launch_enabled'] or plan['pending']):
        raise ValueError('Gen7 alpha plan is not ready: settle every `pending` item, empty the list and enable launch')
    if not plan['gen7_bots']:
        raise ValueError('Gen7 alpha plan needs at least one Gen7 bot')
    used = {policy_key(bot) for bot in plan['gen7_bots'].values()}
    aware = any(bot.get('system_scorer') for bot in plan['gen7_bots'].values())
    if not plan['artifacts'] or set(plan['artifacts']) - {SYSTEM_SCORER_KEY} != used or not all(isinstance(k, str) and POLICY_KEYS.fullmatch(k) for k in used):
        raise ValueError('Gen7 alpha plan artifacts are exactly the policy releases its bots use: gen7_policy, and gen7_policy_<name> for a bot that names another')
    if (SYSTEM_SCORER_KEY in plan['artifacts']) != aware:
        raise ValueError('The `system_scorer` artifact is there exactly when a bot asks for it (`system_scorer`: true)')
    for entry in plan['artifacts'].values():
        if not all(isinstance(entry.get(k), str) and entry[k] for k in ('release', 'file', 'restore', 'sha256')):
            raise ValueError('A Gen7 policy artifact needs release, file, restore and sha256')
    for bot in plan['gen7_bots'].values():
        resolved(bot.get('gen7'))
        Gen6Config(**bot.get('gen6', {}))
        samples = bot.get('samples', 1)
        if isinstance(samples, bool) or not isinstance(samples, int) or samples < 1:
            raise ValueError('Gen7 bot samples is a positive integer')
    if len(plan['roster']) < 2 or len(set(plan['roster'])) != len(plan['roster']):
        raise ValueError('Roster needs at least two distinct bots')
    for pair, weight in plan['pair_weights'].items():
        pair_members(pair)
        if isinstance(weight, bool) or not isinstance(weight, int) or weight < 1:
            raise ValueError('Pair weights are positive integers')
    check_systems(plan)
    return plan


def check_systems(plan):
    """Gen 8: what a plan says about bidding systems. `systems` maps every bot that bids in the cohort (the roster
    and the common bidder) to the system it declares. Without it nothing is declared and no bot may use a system
    setting."""
    systems = plan.get('systems')
    using = sorted(k for k, bot in plan['gen7_bots'].items() if bot.get('bidder') or bot.get('system_scorer') or 'lead_systems' in bot)
    if systems is None:
        if using:
            raise ValueError(f'Bots {using} use bidding-system settings: the plan needs `systems`')
        return
    if not isinstance(systems, dict) or not systems or not all(isinstance(k, str) and isinstance(v, str) and v for k, v in systems.items()):
        raise ValueError('`systems` maps bot ids to the ids of the systems they declare')
    missing = sorted((set(plan['roster']) | {plan['common_bidder']}) - set(systems))
    if missing:
        raise ValueError(f'`systems` names no system for {missing}')
    for key, bot in plan['gen7_bots'].items():
        entry = bot.get('bidder')
        if entry is not None and not (isinstance(entry, dict) and entry.get('kind') in ('python', 'toy')
                                      and re.fullmatch('[0-9a-f]{64}', str(entry.get('sha256')))):
            raise ValueError(f'{key}: `bidder` is the generator entry of a system bidder (kind python or toy) with its sha256 pin')
        if bot.get('system_scorer') not in (None, False, True):
            raise ValueError(f'{key}: `system_scorer` is true or absent; the file is the plan\'s `system_scorer` artifact')
        if 'lead_systems' in bot and not (isinstance(bot['lead_systems'], list) and all(isinstance(x, str) for x in bot['lead_systems'])):
            raise ValueError(f'{key}: `lead_systems` is a list of system ids')
    entry = plan['artifacts'].get(SYSTEM_SCORER_KEY)
    if entry is not None and not all(isinstance(entry.get(k), str) and entry[k] for k in ('release', 'file', 'restore', 'sha256')):
        raise ValueError('The system scorer artifact needs release, file, restore and sha256')


def make_bots(old, plan):
    """Source bots unchanged, plus each Gen7 bot built from its Gen6 base bot's spec.

    The source run may itself be a drained Gen7 cohort, whose unplayed deals a new plan takes over. It already
    has the plan's Gen7 bots; each must then be exactly the bot this plan builds, and is kept as it is."""
    bots = deepcopy(old['bots'])
    for key, entry in plan['gen7_bots'].items():
        base = old['bots'].get(entry['base'])
        if base is None or base.get('engine') != 'gen6':
            raise ValueError(f'Gen7 bot {key} needs a Gen6 base bot')
        spec = deepcopy(base)
        spec.pop('identity')
        spec.update(id=key, engine=ENGINE, policy_role='gen7-alpha', samples=entry.get('samples', base['samples']),
                    gen6=asdict(Gen6Config(**dict(base['gen6'], **entry.get('gen6', {})))),
                    gen7=resolved(entry.get('gen7')), gen7_policy=policy_path(policy_key(entry)))
        spec['artifact_sha256'] = dict(base['artifact_sha256'], gen7_policy=plan['artifacts'][policy_key(entry)]['sha256'])
        if entry.get('system_scorer'):                  # Gen 8: each side's calls are read by the system it declares
            spec['system_scorer'] = SYSTEM_SCORER
            spec['artifact_sha256'][SYSTEM_SCORER_KEY] = plan['artifacts'][SYSTEM_SCORER_KEY]['sha256']
        if 'lead_systems' in entry:
            spec['lead_systems'] = list(entry['lead_systems'])
        if entry.get('bidder'):                         # Gen 8: this bot bids by a system bidder, not by its net
            spec['bidder'] = deepcopy(entry['bidder'])
        spec['identity'] = digest(spec)
        if key in bots and bots[key] != spec:
            raise ValueError(f'The source run has a different bot called {key}: give the Gen7 bot a new id, or the settings of the bot it continues')
        bots[key] = spec
    return bots


def check_mix(plan, bots, references):
    for name in plan['roster']:
        if name not in bots:
            raise ValueError(f'Unknown roster bot {name}')
    if plan['common_bidder'] not in bots:
        raise ValueError('Unknown common bidder')
    scheduled = set()
    for pair in plan['pair_weights']:
        candidate, opponent = pair_members(pair)
        if candidate not in bots or opponent not in bots:
            raise ValueError(f'Pair {pair} names an unknown bot')
        if references.get(candidate) not in bots:
            raise ValueError(f'{candidate} leads a pair and needs an audit reference bot')
        scheduled |= {candidate, opponent}
    idle = sorted(set(plan['gen7_bots']) - scheduled)
    if idle:
        raise ValueError(f'Gen7 bots in no pair: {idle}')


def gen7_block(plan):
    """What the manifest says about the cohort's Gen7 bots and their policy releases. A plan with the one policy keeps
    the two fields it has always had; a plan whose bots name other releases lists every bot's."""
    block = dict(bots=sorted(plan['gen7_bots']))
    first = plan['artifacts'].get(POLICY_KEY)
    if first:
        block.update(policy_release=first['release'], policy_sha256=first['sha256'])
    if set(plan['artifacts']) - {SYSTEM_SCORER_KEY} != {POLICY_KEY}:
        block['policies'] = {k: dict(artifact=policy_key(e), release=plan['artifacts'][policy_key(e)]['release'], sha256=plan['artifacts'][policy_key(e)]['sha256'])
                             for k, e in sorted(plan['gen7_bots'].items())}
    return block


def release_file(entry, scorers):
    """The policy file of a release folder, rebuilt from its parts if needed, checked against the plan, and
    checked to have been trained on the readings of the hand-fit scorer the bots will play with."""
    folder = ROOT / entry['release']
    path = folder / entry['file']
    if not path.exists():
        subprocess.run([sys.executable, str(folder / entry['restore'])], check=True, cwd=folder, stdout=subprocess.DEVNULL)
    if sha(path) != entry['sha256']:
        raise ValueError('Gen7 policy does not match the plan: ' + entry['file'])
    trained_with = json.loads((folder / 'manifest.json').read_text()).get('scorer_sha256')
    if trained_with is None or scorers != {trained_with}:
        raise ValueError("The policy release names a different hand-fit scorer from the base bots'; its inputs would not mean what it learned")
    return path


def system_scorer_file(entry, scorers):
    """The system-aware scorer of a release folder, rebuilt from its parts if needed, checked against the plan, and
    checked to extend the hand-fit scorer the bots play with: an auction with nothing declared, or declared as a
    system the file does not hold, then reads exactly as that scorer reads it."""
    folder = ROOT / entry['release']
    path = folder / entry['file']
    if not path.exists():
        subprocess.run([sys.executable, str(folder / entry['restore'])], check=True, cwd=folder, stdout=subprocess.DEVNULL)
    if sha(path) != entry['sha256']:
        raise ValueError('System scorer does not match the plan: ' + entry['file'])
    extends = json.loads((folder / 'manifest.json').read_text()).get('init_sha256')
    if extends is None or scorers != {extends}:
        raise ValueError("The system scorer release was not built on the base bots' hand-fit scorer; undeclared auctions would read differently")
    return path


def system_bidders(plan):
    """Every system bidder the plan's bots name, built once to check it against its pinned identity."""
    from bridge_harness.system_bidders import make_bidder
    out = {}
    for key, bot in sorted(plan['gen7_bots'].items()):
        if bot.get('bidder'):
            out[key] = make_bidder(bot['bidder'], ROOT).sha256
    return out


def commit():
    try:
        return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def parse_shard(text):
    """'1/4' -> (1, 4): the second of four machines sharing a source run."""
    try:
        k, n = (int(x) for x in str(text).split('/'))
    except ValueError:
        raise ValueError('A shard is K/N, for example 1/4') from None
    if not 0 <= k < n <= 64:
        raise ValueError('A shard is K/N with 0 <= K < N <= 64')
    return k, n


def inherited_actors(source, old, actor_source):
    """Restore unchanged actors pruned by a direct predecessor's self-play cutover."""
    ancestor = json.loads((actor_source / 'manifest.json').read_text())
    verify_source(actor_source, ancestor)
    if old.get('source_generation') != ancestor['identity']:
        raise ValueError('Actor source must be the direct frozen predecessor')
    for key, spec in old['bots'].items():
        if ancestor['bots'].get(key) != spec:
            raise ValueError('Retained actor differs from predecessor: ' + key)
    return ancestor


def prepare(root, source, plan_path=None, shard=None, actor_source=None, exclude_families=None):
    root, source = Path(root).resolve(), Path(source).resolve()
    plan_path = Path(plan_path or PLAN)
    if root.exists():
        raise ValueError('Refusing to overwrite a frozen run')
    if not all((source / n).exists() for n in ('STOP', 'WATCHDOG_STOP')):
        raise ValueError('Drain the source collector and disable its recovery first')
    with (source / '.writer.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if list((source / 'failures').glob('*.json')):
            raise ValueError('Inspect preserved source failures first')
        old = json.loads((source / 'manifest.json').read_text())
        plan = load_plan(plan_path)
        verify_source(source, old)
        boards = list(load(source / old['corpus']))
        done = set()
        episodes = list((source / 'episodes').glob('*.json.gz'))
        receipts = list((source / 'receipts').glob('*.json'))
        if len(episodes) != len(receipts):
            raise ValueError('Source episodes/receipts incomplete')
        for path in receipts:
            r = json.loads(path.read_text())
            i = r['index']
            if i in done or not 0 <= i < len(boards) or r['manifest_identity'] != old['identity']:
                raise ValueError('Wrong source receipt identity')
            if r['family'] != deal_key(boards[i].hands, True) or r['episode_sha256'] != sha(source / 'episodes' / f'{i:06d}.json.gz'):
                raise ValueError('Source receipt/episode mismatch')
            done.add(i)
        keep = [i for i in range(old['target']) if i not in done]
        excluded = set()
        if exclude_families is not None:
            values = json.loads(Path(exclude_families).read_text())
            if not isinstance(values, list) or any(not isinstance(v, str) or not re.fullmatch(r'[0-9a-f]{64}', v) for v in values):
                raise ValueError('Evaluation exclusions must be a JSON list of canonical family hashes')
            excluded = set(values)
            keep = [i for i in keep if deal_key(boards[i].hands, True) not in excluded]
        if not keep:
            raise ValueError('No unplayed source deals remain')
        if shard is not None:                   # this machine's share: every n-th unplayed deal, starting at the k-th
            k, n = parse_shard('%s/%s' % tuple(shard))
            keep = keep[k::n]
            if not keep:
                raise ValueError('No unplayed source deals fall in this shard')
        actor_source = Path(actor_source).resolve() if actor_source else None
        ancestor = inherited_actors(source, old, actor_source) if actor_source else None
        actor_manifest = dict(old, bots=ancestor['bots']) if ancestor else old
        bots = make_bots(actor_manifest, plan)
        references = dict(old.get('audit_references', {}), **plan['audit_references'])
        check_mix(plan, bots, references)
        policies = {}                           # artifact key -> the release file, checked against the scorer of the bots that use it
        system_scorer = None
        if SYSTEM_SCORER_KEY in plan['artifacts']:
            system_scorer = system_scorer_file(plan['artifacts'][SYSTEM_SCORER_KEY],
                                               {bots[k]['artifact_sha256']['scorer'] for k, e in plan['gen7_bots'].items() if e.get('system_scorer')})
        rule_bidders = system_bidders(plan)
        for key in sorted(set(plan['artifacts']) - {SYSTEM_SCORER_KEY}):
            policies[key] = release_file(plan['artifacts'][key], {bots[k]['artifact_sha256']['scorer'] for k, e in plan['gen7_bots'].items() if policy_key(e) == key})
        root.mkdir(parents=True)
        for folder in ('artifacts', 'assets'):
            if (source / folder).exists():
                shutil.copytree(source / folder, root / folder)
        if ancestor:
            for spec in ancestor['bots'].values():
                for key, expected in spec['artifact_sha256'].items():
                    dest = root / spec[key]
                    if dest.exists() and sha(dest) != expected:
                        raise ValueError('Actor artifact collision: ' + spec[key])
                    if not dest.exists():
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(actor_source / spec[key], dest)
        for key, policy in policies.items():
            (root / policy_path(key)).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(policy, root / policy_path(key))
        if system_scorer is not None:
            (root / SYSTEM_SCORER).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(system_scorer, root / SYSTEM_SCORER)
        if exclude_families is not None:
            exclusion_path = root / 'artifacts/validation/evaluation-exclusions.json'
            exclusion_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(exclude_families, exclusion_path)
        for folder in ('episodes', 'receipts', 'failures'):
            (root / folder).mkdir()
        save([boards[i] for i in keep], root / 'corpus.jsonl')
        atomic_json(root / 'source-indices.json', keep)
        labels = dict(old.get('labels', {}), **plan.get('labels', {}))
        labels.update({key: bot.get('label', key) for key, bot in plan['gen7_bots'].items()})
        m = dict(schema=old['schema'], campaign=plan['campaign'], title=plan['title'],
            target=len(keep), seed=plan.get('seed', old['seed']), roster=plan['roster'], bots=bots,
            pair_weights=plan['pair_weights'], pair_schedule=[p for p, n in plan['pair_weights'].items() for _ in range(n)],
            audit_references=references, common_bidder=plan['common_bidder'],
            corpus='corpus.jsonl', corpus_sha256=sha(root / 'corpus.jsonl'), source_sha256=source_hash(),
            runtime_sha256={name: sha(ROOT / name) for name in RUNTIME},
            created_epoch=time.time(), source_generation=old['identity'], source_completed=len(done),
            source_indices='source-indices.json', source_indices_sha256=sha(root / 'source-indices.json'),
            labels=labels, order=plan['roster'], plan_sha256=sha(plan_path), source_commit=commit(),
            gen7_alpha=gen7_block(plan),
            model_note=plan.get('model_note') or 'Gen 7 alpha bots are their Gen 6 base bot (same bidder, lead net, hand-fit scorer, layouts and sample count) '
                       'with the gen7 engine (bridge_harness/gen7.py): the policy net weights the listed layouts by the play so far, '
                       'breaks ties, and from the tricks named in each bot\'s `gen7.tree` a short tree search over the net\'s likeliest '
                       'cards re-values the cards the Gen 6 search rates near its best. Settings are in each bot\'s `gen7` block. '
                       'Every other bot is unchanged from the source run. docs/gen7_alpha_2026-11-11.md has the details.',
            interpretation=plan.get('interpretation') or 'Alpha cohort to validate the Gen 7 architecture and measure its speed; not a strength claim. '
                           'Common and native auctions are separate conditions; identical auctions reuse physical games. '
                           'Only unplayed source deals are allocated; completed source records are unchanged.')
        for key in CARRIED:
            if key in old:
                m[key] = deepcopy(old[key])
        if plan.get('systems'):                 # Gen 8: the runner tells every player the systems declared at each table
            m['systems'] = dict(plan['systems'])
            m['gen8'] = dict(rule_bidders=rule_bidders,
                             system_scorer=None if system_scorer is None else dict(release=plan['artifacts'][SYSTEM_SCORER_KEY]['release'],
                                                                                 sha256=plan['artifacts'][SYSTEM_SCORER_KEY]['sha256']))
        if ancestor:
            m['actor_source_generation'] = ancestor['identity']
            m['labels'].update(ancestor.get('labels', {}))
            m['bidding_conditions'] = ['common', 'native']
        for key in ('generation', 'variant'):
            if key in plan:
                m[key] = plan[key]
        pairs = [pair_members(p) for p in plan['pair_weights']]
        m['bidding_conditions'] = (['self'] if any(a == b for a, b in pairs) else []) + (
            ['common', 'native'] if any(a != b for a, b in pairs) else [])
        if exclude_families is not None:
            m['evaluation_exclusions'] = dict(path='artifacts/validation/evaluation-exclusions.json',
                sha256=sha(exclusion_path), families=len(excluded), reason='Exclude released-policy training families from fresh comparisons')
        if shard is not None:
            m['shard'] = dict(index=k, of=n)
        m['identity'] = digest(m)
        atomic_json(root / 'manifest.json', m)
        atomic_json(root / 'state.json', dict(manifest_identity=m['identity'], completed=0, target=len(keep), by_pair={}, root_games=0, tables=0, epoch=time.time()))
        atomic_json(root / 'heartbeat.json', dict(epoch=time.time(), completed=0, workers=4, ben_workers=1, in_flight=[]))
        verify_generation(root, m)
        return m


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--plan', type=Path)
    p.add_argument('--shard', help='K/N: take every N-th unplayed deal starting at the K-th (K from 0), for machines sharing one source run')
    p.add_argument('--actor-source', type=Path, help='Verified direct predecessor supplying actors pruned by self-play; deals come only from --source')
    p.add_argument('--exclude-families', type=Path, help='JSON family hashes to exclude from evaluation, preserved with their hash')
    a = p.parse_args()
    m = prepare(a.run, a.source, a.plan, parse_shard(a.shard) if a.shard else None, a.actor_source, a.exclude_families)
    print(json.dumps(dict(identity=m['identity'], target=m['target'], shard=m.get('shard'), allocation=m['pair_weights'], policy=m['gen7_alpha'],
                          gen7={k: v['gen7'] for k, v in m['bots'].items() if v.get('engine') == ENGINE})))
