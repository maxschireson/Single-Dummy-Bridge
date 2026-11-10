"""Derive belief root trajectories from a pinned, complete compact arena export.

This is a source adapter, not a training-recipe change. Original raw hashes stay
in provenance; derived gzip files have their own checksums. Confirmation families
are copied as metadata only, with no observations prepared or labels inspected.
"""
import argparse
from collections import Counter
import fcntl
import gzip
import hashlib
import json
from pathlib import Path
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_blob(path, expected):
    raw = path.read_bytes()
    for content in (raw, raw[:-1] if raw.endswith(b'\n') else raw):
        actual = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
        if actual == expected:
            return json.loads(content)
    raise ValueError('Git blob mismatch: ' + str(path))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    if path.suffix == '.gz':
        raw = gzip.compress(raw, mtime=0)
    if path.exists() and path.read_bytes() != raw:
        raise ValueError('Frozen output differs: ' + str(path))
    if not path.exists():
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_bytes(raw)
        tmp.replace(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for key in ('repo', 'compact', 'raw-audit', 'out'):
        ap.add_argument('--' + key, type=Path, required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(a.repo.resolve()))
    import numpy as np
    from bridge_harness.core import Board, auction_contract
    from bridge_harness.bidding_env import deal_key
    from bridge_harness.training import digest
    from bridge_harness.runner import replay
    from bridge_harness.belief_capacity import encode_play
    from scripts.screen_attention_belief import selected_observations, split

    a.out.mkdir(parents=True, exist_ok=True)
    lock = (a.out / 'adapter.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    snapshot = json.loads((a.compact / 'snapshot.json').read_text())
    tree = {e['path']: e for e in snapshot['tree'] if e['type'] == 'blob'}
    manifest = verify_blob(a.compact / 'manifest.json', tree['recovery/manifest.json']['sha'])
    assert digest({k: v for k, v in manifest.items() if k != 'identity'}) == manifest['identity']
    save(a.out / 'manifest.json', manifest)
    raw_receipts = {r['index']: r for r in json.loads((a.raw_audit / 'download-verified-receipts.json').read_text())}
    receipts = []
    sources = []
    counts = Counter()
    families = set()
    indices = set()
    for path in sorted(a.compact.glob('arena/replays/data/*/boards-*.json')):
        relative = str(path.relative_to(a.compact))
        records = verify_blob(path, tree[relative]['sha'])
        counts['verified_compact_blobs'] += 1
        for r in records.values():
            family, index = r['family'], r['index']
            assert family not in families and index not in indices
            families.add(family)
            indices.add(index)
            assert deal_key(Board.from_dict(r['board']).hands, True) == family
            candidate, opponent = r['pair'].split('~')
            for actor in (candidate, opponent):
                bot = manifest['bots'][actor]
                h = bot.get('artifact_sha256', {}).get('policy')
                if h == 'e179a71ed132dcd0f9ca06b486ec087e9f5b26edb4210e99ed2e04c9439b21ed' or (bot.get('policy') and not h):
                    raise ValueError('Excluded or unidentified actor')
            partition = split(family)
            source_split = 'train' if partition == 'train' else 'validation'
            rooms = {}
            if partition != 'test':
                for condition in r['conditions'].values():
                    for t in condition['tables']:
                        assert set(t['assignments']) <= {candidate, opponent}
                        bd = dict(r['board'], auction=t['auction'], contract=t['contract'],
                                  declarer=t['declarer'], opening_lead=None)
                        b = Board.from_dict(bd)
                        assert auction_contract(b.dealer, b.auction) == b.contract
                        actions = [dict(ply=i, seat=c[0], card=c[1:]) for i, c in enumerate(t['plays'])]
                        table = dict(node='root', status='ok', actions=actions,
                                     ns_score=t['ns_score'], declarer_tricks=t['declarer_tricks'] if b.contract else 0)
                        room = dict(status='ok', board=bd, tables=[table], assignments=t['assignments'])
                        replay(room)
                        key = digest([bd, t['assignments'], actions])
                        if key not in rooms:
                            rooms[key] = room
                            counts['replayed_unique_non_test_roots'] += 1
                counts['non_test_families'] += 1
            episode = dict(schema='derived-compact-belief-roots-v1', index=index, family=family,
                           split=source_split, board=r['board'], candidate=candidate, opponent=opponent,
                           manifest_identity=manifest['identity'], unique_tables=rooms,
                           original_episode_sha256=r['episode_sha256'],
                           confirmation_metadata_only=partition == 'test')
            ep = a.out / 'episodes' / f'{index:06d}.json.gz'
            save(ep, episode)
            receipt = dict(index=index, family=family, split=source_split, episode_sha256=sha(ep))
            receipts.append(receipt)
            sources.append(dict(**receipt, partition=partition, original_episode_sha256=r['episode_sha256'],
                                source_path=relative, source_git_blob_sha=tree[relative]['sha']))
            if index in raw_receipts and partition != 'test':
                raw_path = a.raw_audit / 'episodes' / f'{index:06d}.json.gz'
                assert sha(raw_path) == r['episode_sha256'] == raw_receipts[index]['episode_sha256']
                def get(p):
                    return selected_observations(dict(family=family, split=partition,
                        sources=[dict(path=str(p), sha256=sha(p))]))
                derived, original = get(ep), get(raw_path)
                assert len(derived) == len(original)
                for (dk, do, dy), (ok, oo, oy) in zip(derived, original):
                    assert dk == ok and np.array_equal(dy, oy)
                    dx, ds = encode_play(do)
                    ox, os = encode_play(oo)
                    assert np.array_equal(ds, os) and dx.keys() == ox.keys()
                    assert all(np.array_equal(dx[k], ox[k]) for k in dx)
                counts['raw_non_test_episodes_exact_input_match'] += 1
                counts['raw_matched_selected_positions'] += len(derived)
            counts[partition + '_families'] += 1
            if len(indices) % 100 == 0:
                print(json.dumps(dict(stage='compact_belief_audit', completed=len(indices), counts=dict(counts))), flush=True)
    expected = sum(p.startswith('recovery/episodes/') for p in tree)
    assert len(indices) == expected
    save(a.out / 'receipts.json', sorted(receipts, key=lambda r: r['index']))
    save(a.out / 'sources.json', sorted(sources, key=lambda r: r['index']))
    report = dict(schema='gen6-belief-compact-adapter-v1', feed_commit=snapshot['commit'],
                  feed_branch=snapshot['branch'], source_records=len(indices), counts=dict(counts),
                  source_snapshot_sha256=sha(a.compact / 'snapshot.json'),
                  sources_sha256=sha(a.out / 'sources.json'), receipts_sha256=sha(a.out / 'receipts.json'),
                  adapter_sha256=sha(Path(__file__)), test_evaluated=False,
                  note='Root-only adapter for unchanged belief selection. Derived and original compressed hashes are distinct. All non-test roots legally replayed; available raw non-test belief inputs checked exactly. Explicit reservation and historical-data exclusion occur in the refresh runner before labeling.')
    save(a.out / 'audit.json', report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
