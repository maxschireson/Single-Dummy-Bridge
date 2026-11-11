"""Prepare a new, independently seeded all-Gen6-fast collection stream."""
import gzip
import json
from pathlib import Path
import secrets
import shutil
import sys
import time

BASE = Path(__file__).resolve().parent
RUNTIME = BASE / 'runtime'
sys.path.insert(0, str(RUNTIME))
from bridge_harness.bidding_env import deal_key
from bridge_harness.core import Board
from bridge_harness.corpus import generate, load, save
from bridge_harness.loop_registry import sha, source_hash
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest

SOURCE = BASE.parent / 'arena-artifact-snapshot/recovery'
RUN = BASE / 'run'
COUNT = 25000
BRANCH = 'arena-gen6-fast-selfplay-codex-20261111'
assert not RUN.exists(), 'Never overwrite a prepared run'
old = json.loads((SOURCE / 'manifest.json').read_text())
assert digest({k: v for k, v in old.items() if k != 'identity'}) == old['identity']
assert source_hash() == old['source_sha256']
bots = {k: old['bots'][k] for k in ('6-32', '3')}
for spec in bots.values():
    assert digest({k: v for k, v in spec.items() if k != 'identity'}) == spec['identity']
    for role, checksum in spec['artifact_sha256'].items():
        assert sha(SOURCE / spec[role]) == checksum
assert bots['6-32']['samples'] == 32 and bots['6-32']['gen6']['list_from_trick'] == 7
assert bots['6-32']['gen6']['list_solve'] == 256
assert old['audit']['probability'] == .5
assert sha(SOURCE / old['corpus']) == old['corpus_sha256']
blocked = {deal_key(b.hands, True) for b in load(SOURCE / old['corpus'])}
training = BASE.parent / 'gen5-training-families.json.gz'
with gzip.open(training, 'rt') as f:
    blocked.update(r['family'] for r in json.load(f))
seed = secrets.randbits(63)
boards = []
seen = set()
for board in generate(COUNT + 1000, seed):
    family = deal_key(board.hands, True)
    if family in blocked or family in seen:
        continue
    seen.add(family)
    boards.append(Board('gen6-selfplay-' + family, board.hands, None, board.dealer,
                        board.vulnerability, auction=(), auction_source='independent-unbid'))
    if len(boards) == COUNT:
        break
assert len(boards) == COUNT and not (seen & blocked)
RUN.mkdir()
for folder in ('episodes', 'receipts', 'failures'):
    (RUN / folder).mkdir()
for spec in bots.values():
    for role in spec['artifact_sha256']:
        relative = spec[role]
        target = RUN / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(SOURCE / relative, target)
save(boards, RUN / 'corpus.jsonl')
plan = dict(schema='gen6-independent-selfplay-stream-plan-v1',
    authorized_by='Max: start a new Bridge Bot Arena collection stream; all self-play Gen 6 fast',
    campaign='gen6-fast-selfplay-codex-20261111', title='Gen 6 · new fast self-play stream',
    target=COUNT, workers=3, seed=seed, pair_weights={'6-32~6-32': 1},
    common_bidder='6-32', audit=old['audit'], gap_fork=old['gap_fork'],
    publication_branch=BRANCH, two_self_rooms=False,
    notes=['All four root-table seats use the frozen Gen6 fast actor.',
           'Gen3 is an audit reference only and is never a scheduled opponent.',
           'Independent fresh cohort; excludes published source corpus and Gen5 training families.',
           'Self-play has null strength IMPs. Existing producers and frozen observations are unchanged.'])
atomic_json(RUN / 'plan.json', plan)
m = dict(schema='gen5-arena-manifest-v1', generation=6, variant='6',
    campaign=plan['campaign'], title=plan['title'], target=COUNT, seed=seed,
    roster=['6-32', '3'], order=['6-32'], bots=bots,
    labels={k: old['labels'][k] for k in bots}, pair_weights=plan['pair_weights'],
    pair_schedule=['6-32~6-32'], common_bidder='6-32', audit_references={'6-32': '3'},
    audit=old['audit'], ben_audit=old['ben_audit'], gap_fork=old['gap_fork'],
    bidding_conditions=['self'], two_self_rooms=False,
    corpus='corpus.jsonl', corpus_sha256=sha(RUN / 'corpus.jsonl'), source_sha256=source_hash(),
    runtime_sha256={n: sha(RUNTIME / n) for n in old['runtime_sha256']},
    created_epoch=time.time(), independent_cohort=True, fresh_corpus=True,
    plan_sha256=sha(RUN / 'plan.json'), preparation_sha256=sha(Path(__file__)),
    artifact_source_manifest_identity=old['identity'],
    artifact_source_commit='13e0fc7b884ecfa546f693a9bac0d92b520f1247',
    artifact_source_branch='arena-gen6-chatgpt-feed',
    exclusion_families=len(blocked), training_families_sha256=sha(training),
    worker_lifecycle=dict(normal_workers=3, ben_workers=0, retry_failures=False),
    model_note='100% Gen6 fast self-play. Frozen bidder, belief, scorer and policy; '
               '32 early layouts, compatible-layout listing from trick 7, 256-solve ceiling. '
               'Gen7 capture and 50% tie audits retained.',
    interpretation='One all-Gen6-fast root table per independent deal. Tie/gap forks supply '
                   'training contrasts; self-play has no strength IMP estimate. '
                   'Full hidden hands are labels, never player inputs.')
m['identity'] = digest(m)
atomic_json(RUN / 'manifest.json', m)
atomic_json(RUN / 'state.json', dict(manifest_identity=m['identity'], completed=0,
    target=COUNT, by_pair={}, root_games=0, tables=0, failures=0, epoch=time.time()))
atomic_json(RUN / 'heartbeat.json', dict(epoch=time.time(), completed=0,
    workers=3, ben_workers=0, in_flight=[]))
shutil.copy2(SOURCE / 'manifest.json', RUN / 'artifact-source-manifest.json')
verify_generation(RUN, m)
atomic_json(BASE / 'stream.json', dict(run=str(RUN), runtime=str(RUNTIME),
    publication=str(BASE / 'publication'), branch=BRANCH, key='gen6newselfplay',
    manifest=m['identity'], target=COUNT, seed=seed))
print(json.dumps(dict(manifest=m['identity'], target=COUNT, seed=seed,
    exclusions=len(blocked), actor=bots['6-32']['identity'], pair_weights=m['pair_weights'])))
