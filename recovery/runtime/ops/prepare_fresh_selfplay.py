"""Prepare a new independent Gen6 fast self-play stream without changing actors."""
import concurrent.futures
from copy import deepcopy
import gzip
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.bidding_env import deal_key
from bridge_harness.core import Board
from bridge_harness.corpus import generate, load, save
from bridge_harness.loop_registry import sha, source_hash
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest

WORK = Path('/workspace/work')
RUN = WORK / 'bridge-gen6-fast-selfplay-new'
REPO = 'maxschireson/Single-Dummy-Bridge'
REVISION = '13e0fc7b884ecfa546f693a9bac0d92b520f1247'

def download(path):
    with urllib.request.urlopen('https://raw.githubusercontent.com/' + REPO + '/' + path, timeout=60) as response:
        return response.read()

def exclusion(entry):
    ref = json.loads(subprocess.check_output(['gh', 'api', 'repos/' + REPO + '/git/ref/heads/' + entry['branch']]))
    revision = ref['object']['sha']
    manifest = json.loads(download(revision + '/recovery/manifest.json'))
    assert digest({k:v for k,v in manifest.items() if k != 'identity'}) == manifest['identity']
    import hashlib
    cached = WORK / 'bridge-exclusions' / entry['branch'] / 'corpus.jsonl'
    if cached.exists() and sha(cached) == manifest['corpus_sha256']:
        data = cached.read_bytes()
    else:
        try:
            data = download(revision + '/recovery/' + manifest['corpus'])
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            tree = json.loads(subprocess.check_output(['gh','api','repos/' + REPO + '/git/trees/' + revision + '?recursive=1']))
            parts = sorted(item['path'] for item in tree['tree'] if item['type'] == 'blob' and item['path'].startswith('recovery/corpus-parts/corpus.jsonl.gz.part-'))
            assert parts, entry['branch'] + ' has no recoverable corpus'
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                compressed = b''.join(pool.map(lambda path:download(revision + '/' + path), parts))
            data = gzip.decompress(compressed)
    assert hashlib.sha256(data).hexdigest() == manifest['corpus_sha256']
    folder = WORK / 'bridge-exclusions' / entry['branch']
    folder.mkdir(parents=True, exist_ok=True)
    corpus = folder / 'corpus.jsonl'
    corpus.write_bytes(data)
    families = {deal_key(b.hands, True) for b in load(corpus)}
    return families, dict(branch=entry['branch'], revision=revision, manifest=manifest['identity'],
                         corpus_sha256=manifest['corpus_sha256'], families=len(families))

def main():
    assert not RUN.exists(), 'Refusing to overwrite a run'
    old = json.loads((ROOT.parent / 'manifest.json').read_text())
    assert digest({k:v for k,v in old.items() if k != 'identity'}) == old['identity']
    assert source_hash() == old['source_sha256'], 'Published engine source must match exactly'
    bots = {k:deepcopy(old['bots'][k]) for k in ('6-32', '3')}
    for spec in bots.values():
        assert digest({k:v for k,v in spec.items() if k != 'identity'}) == spec['identity']
        for role, expected in spec['artifact_sha256'].items():
            assert sha(ROOT.parent / spec[role]) == expected
    registry = json.loads(download('gh-pages/arena/gen6-sources.json'))
    active = [entry for entry in registry['sources'] if not entry.get('retired')]
    blocked = set()
    sources = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for families, provenance in pool.map(exclusion, active):
            blocked.update(families)
            sources.append(provenance)
    training = WORK / 'bridge-gen6-source/models/cardplay/gen5-2026-11-10/training-families.json.gz'
    with gzip.open(training, 'rt') as stream:
        blocked.update(row['family'] for row in json.load(stream))
    seed = secrets.randbits(63)
    boards = []
    families = set()
    count = 25000
    for board in generate(count + 1000, seed):
        family = deal_key(board.hands, True)
        if family in blocked or family in families:
            continue
        families.add(family)
        boards.append(Board('gen6-self-' + family, board.hands, None, board.dealer,
                            board.vulnerability, auction=(), auction_source='fresh-selfplay-unbid'))
        if len(boards) == count:
            break
    assert len(boards) == count and not families.intersection(blocked)
    RUN.mkdir()
    for folder in ('episodes', 'receipts', 'failures', 'artifacts', 'assets'):
        (RUN / folder).mkdir()
    for spec in bots.values():
        for role in spec['artifact_sha256']:
            path = spec[role]
            (RUN / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT.parent / path, RUN / path)
    save(boards, RUN / 'corpus.jsonl')
    atomic_json(RUN / 'exclusions.json', dict(sources=sources, training_sha256=sha(training),
                                            blocked_families=len(blocked), overlap=0))
    plan = dict(schema='gen6-independent-selfplay-plan-v1', authorized_by='User: start a new Gen 6 fast self-play collection stream',
                target=count, pair_weights={'6-32~6-32':1}, common_bidder='6-32',
                audit=old['audit'], gap_fork=old['gap_fork'], workers=3)
    atomic_json(RUN / 'plan.json', plan)
    m = dict(schema='gen5-arena-manifest-v1', generation=6, variant='6',
             campaign='gen6-fresh-fast-selfplay-20261111-' + str(seed), title='Gen 6 · new fast self-play stream',
             target=count, seed=seed, roster=['6-32','3'], order=['6-32'], bots=bots,
             roster_note='Gen3 is an audit reference only; all scheduled root tables use Gen6 fast at every seat.',
             pair_weights=plan['pair_weights'], pair_schedule=['6-32~6-32'], audit_references={'6-32':'3'},
             common_bidder='6-32', corpus='corpus.jsonl', corpus_sha256=sha(RUN/'corpus.jsonl'),
             source_sha256=source_hash(), runtime_sha256={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'ops').glob('*.py'))},
             audit=old['audit'], ben_audit=old['ben_audit'], gap_fork=old['gap_fork'],
             bidding_conditions=['self'], two_self_rooms=False, created_epoch=time.time(),
             artifact_source_manifest_identity=old['identity'], source_feed_revision=REVISION,
             exclusions='exclusions.json', exclusions_sha256=sha(RUN/'exclusions.json'),
             independent_cohort=True, fresh_corpus=True, preflight_only=False,
             labels={k:old['labels'][k] for k in bots}, plan_sha256=sha(RUN/'plan.json'),
             engine_commit=old['engine_commit'],
             model_note='Unchanged Gen6 fast: 32 samples until trick7, compatible-layout solve ceiling256; Gen7 capture and 50% tie audits retained.',
             interpretation='100% Gen6 fast self-play for training: one root table per fresh family, all four seats use the same frozen actor. IMP comparisons are null. Gen3 is used solely for tie-audit references.')
    m['identity'] = digest(m)
    atomic_json(RUN/'manifest.json',m)
    atomic_json(RUN/'state.json',dict(manifest_identity=m['identity'], completed=0, target=count, by_pair={}, root_games=0, tables=0, failures=0, epoch=time.time()))
    atomic_json(RUN/'heartbeat.json',dict(epoch=time.time(),completed=0,workers=3,ben_workers=0,in_flight=[]))
    verify_generation(RUN,m)
    branch='arena-gen6-fast-selfplay-20261111-'+m['identity'][:8]+'-feed'
    atomic_json(WORK/'bridge-new-stream.json', dict(run=str(RUN),source=str(ROOT),publication=str(WORK/'bridge-gen6-new-publication'),
                                               branch=branch,manifest=m['identity'],seed=seed,target=count))
    print(json.dumps(dict(identity=m['identity'], target=count, excluded_families=len(blocked), branch=branch)))

if __name__ == '__main__':
    main()
