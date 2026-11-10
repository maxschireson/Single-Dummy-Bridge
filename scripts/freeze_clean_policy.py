"""Normalize recovered and exported clean play, preserving provenance and families.

Reject unknown policy hashes as well as v4; exclude parent-era families entirely
from this incremental fit. Original records remain unchanged in their archives.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.bidding_env import deal_key
from bridge_harness.core import Board
from bridge_harness.training import digest
from bridge_harness.selfplay import atomic_json
from scripts.policy_choice_data import family_split

CLEAN = {'8c62c88b0f2041ce78273e072d0b5530598255cc39b482826901ff1660e064f5',
         '02b6885e8f07da473970052d7f9ea9dc2a10fa34505ad60186e4a14d02218c60'}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--export', type=Path, required=True)
    p.add_argument('--run', type=Path, action='append', default=[])
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out/'episodes').mkdir(exist_ok=True)
    (a.out/'rooms').mkdir(exist_ok=True)
    archive = zipfile.ZipFile(a.archive)
    blocked = set()
    for n in archive.namelist():
        if n.endswith('legacy-exclusions.json'):
            blocked.update(json.loads(archive.read(n))['legacy_rotation_groups'])
    assert blocked
    refs = defaultdict(list)
    counts = Counter()
    manifests = {}

    def accept(record, episodes, source, policies):
        if any(h is not None and h not in CLEAN for h in policies):
            counts['excluded_policy_records'] += 1
            return
        if record.get('status', 'ok') != 'ok':
            counts['failed_records'] += 1
            return
        board = Board.from_dict(record['board'])
        family = deal_key(board.hands, True)
        if record.get('family') != family:
            raise ValueError('Family disagrees with cards')
        if any(digest(board.hands[j:]+board.hands[:j]) in blocked for j in range(4)):
            counts['excluded_parent_era_records'] += 1
            return
        split = family_split(family)
        if (record['split'] == 'train') != (split == 'train'):
            raise ValueError('Original train/holdout boundary would change')
        for ep in episodes:
            if ep.get('status') != 'ok' or not ep.get('tables'):
                continue
            if deal_key(Board.from_dict(ep['board']).hands, True) != family:
                raise ValueError('Nested family mismatch')
            room = a.out/'rooms'/f"{counts['rooms']:07}.json.gz"
            if not room.exists():
                with gzip.open(room, 'wt', compresslevel=1) as f:
                    json.dump(ep, f, separators=(',', ':'))
            else:
                if json.load(gzip.open(room, 'rt')) != ep:
                    raise ValueError('Resume room differs')
            refs[family].append(dict(source=source, policies=policies, room=str(room)))
            counts['rooms'] += 1
        counts['accepted_records'] += 1

    def mixed(record, manifest, source):
        if record['manifest_identity'] != manifest['identity']:
            raise ValueError('Manifest identity mismatch')
        identities = {b['identity']: b for b in manifest['bots'].values()}
        active = [identities[v] for v in record['versions'].values()]
        policies = [b['artifact_sha256'].get('policy') for b in active]
        if any(b.get('policy') and not b['artifact_sha256'].get('policy') for b in active):
            raise ValueError('Missing policy identity')
        episodes = list(record['unique_tables'].values()) if 'unique_tables' in record else [record['focal'],record['control']]
        accept(dict(record, board=record.get('board') or episodes[0]['board']), episodes, source, policies)

    for n in archive.namelist():
        if n.endswith('/manifest.json') and '/mixed-fork-25k/' in n and '/auctions/' not in n:
            manifests[n.rsplit('/',1)[0]] = json.loads(archive.read(n))
    cache=a.out/'archive-index.json'
    if cache.exists():
        saved=json.loads(cache.read_text());refs.update(saved['refs']);counts.update(saved['counts'])
    else:
        for number,n in enumerate(archive.namelist()):
            if not n.endswith('.json.gz') or '/episodes/' not in n:
                continue
            prefix = n.split('/episodes/')[0]
            if prefix not in manifests:
                continue
            raw = archive.read(n)
            mixed(json.loads(gzip.decompress(raw)), manifests[prefix],
                  dict(archive=str(a.archive.resolve()), member=n, sha256=hashlib.sha256(raw).hexdigest()))
        atomic_json(cache,dict(refs=refs,counts=counts))
    print(json.dumps(dict(stage='archive', counts=counts, families=len(refs))),flush=True)
    for run in a.run:
        manifest = json.loads((run/'manifest.json').read_text())
        manifests[str(run.resolve())] = manifest
        for path in sorted((run/'episodes').glob('*.json.gz')):
            raw = path.read_bytes()
            mixed(json.loads(gzip.decompress(raw)), manifest,
                  dict(path=str(path.resolve()),sha256=hashlib.sha256(raw).hexdigest()))
    for pr in json.loads((a.export/'provenance.json').read_text()):
        path = a.export/pr['file']
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != pr['sha256']:
            raise ValueError('Export checksum failed')
        ep = json.loads(gzip.decompress(raw))
        policies = [b['policy_sha256'] for b in pr['active_bots'].values()]
        accept(ep, [ep], dict(path=str(path.resolve()),sha256=pr['sha256'],export_provenance=pr), policies)
    manifest = dict(schema='normalized-policy-clean-v1', bots={'clean':{'artifact_sha256':{'policy':next(h for h in CLEAN if h.startswith('8c62'))}}},
        source_manifests=manifests, allowed_policy_sha256=sorted(CLEAN),
        rule='Every declared active play policy must be allowlisted; PIMC-only is allowed; parent-era rotation groups excluded',
        parent_exclusion_groups=len(blocked), counts=dict(counts))
    manifest['identity'] = digest(manifest)
    atomic_json(a.out/'manifest.json',manifest)
    for index,(family, items) in enumerate(sorted(refs.items())):
        record = dict(index=index,family=family,split='train' if family_split(family)=='train' else 'validation',
            candidate='clean',pair='clean',manifest_identity=manifest['identity'],versions={},
            policy_clean=True,provenance=[{k:v for k,v in item.items() if k!='room'} for item in items],
            unique_tables={str(i):json.load(gzip.open(item['room'],'rt')) for i,item in enumerate(items)})
        with gzip.open(a.out/'episodes'/f'{index:06}.json.gz','wt') as f:
            json.dump(record,f,separators=(',',':'))
        for item in items: Path(item['room']).unlink()
    print(json.dumps(dict(stage='complete',counts=counts,families=len(refs),
        splits=dict(Counter(family_split(f) for f in refs)))),flush=True)

if __name__=='__main__': main()
