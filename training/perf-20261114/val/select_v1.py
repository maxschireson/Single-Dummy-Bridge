#!/usr/bin/env python3
"""V1, the frozen validation set: select arena records no existing net has trained on, in the test split of the family hash.

    select_v1.py --cache DIR --inputs r4c_inputs.json --v2-fetch fetch.json --v2-fetch fetchB.json --out v1_candidates.json

1. v2's records: every episode blob at the branch tips rollout net v2 was built from (its fetch.json / fetchB.json).
2. Round 4's records: the 2,600 arena records sampled into round 4 (inputs.json, by blob name).
3. The arena records now on round 4's feeds (round4_arena.sh FEEDS), with each record's family, split and pair from its
   receipt (fetched with --filter=blob:limit, so receipts come and episodes stay on GitHub).
4. Candidates: records in neither set, whose family is in neither set's families, in the test split (the builder's
   rule: int(family[:8], 16) % 10 == 0), so that a rule "never train on test-split families" keeps V1 clean for good.
"""
from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
from pathlib import Path

REPO = 'https://github.com/maxschireson/Single-Dummy-Bridge'
FEEDS = ('arena-gen9-azure4-feed arena-gen9-azure4-ben64-feed arena-gen9-genx-stu-azure4-feed arena-gen8-19bbdce5-20261112-feed '
         'arena-gen8-independent-feed arena-gen8-candidate-codex-20261112-feed arena-gen8-x3-azure1-feed arena-gen8-azure1-feed '
         'arena-gen8-azure6-feed arena-gen8-m1-azure1-feed arena-gen8-s1-azure1-feed arena-gen8-s3-azure1-feed '
         'arena-gen8-s7-azure1-feed').split()


def split_of(family):
    bucket = int(family[:8], 16) % 10
    return 2 if bucket == 0 else 1 if bucket == 5 else 0


class Cache:
    def __init__(self, path):
        self.path = Path(path)
        if not (self.path / 'HEAD').exists():
            subprocess.run(['git', 'init', '-q', '--bare', str(self.path)], check=True)
            self.git('remote', 'add', 'origin', REPO)
            self.git('config', 'remote.origin.promisor', 'true')
            self.git('config', 'remote.origin.partialclonefilter', 'blob:limit=16k')

    def git(self, *args, check=True, input=None):
        return subprocess.run(['git', '--git-dir', str(self.path), *args], check=check, capture_output=True, text=True, input=input)

    def fetch(self, refs):
        """refs: commit shas or branch names; small blobs come with the trees."""
        for i in range(0, len(refs), 20):
            chunk = refs[i:i + 20]
            r = self.git('fetch', '-q', '--depth', '1', '--filter=blob:limit=16k', 'origin', *chunk, check=False)
            if r.returncode:
                for ref in chunk:           # one at a time, so one missing ref does not lose the rest
                    r1 = self.git('fetch', '-q', '--depth', '1', '--filter=blob:limit=16k', 'origin', ref, check=False)
                    if r1.returncode:
                        print(f'fetch failed: {ref}: {r1.stderr.strip()[:200]}', file=sys.stderr)

    def tip(self, branch):
        r = self.git('ls-remote', 'origin', f'refs/heads/{branch}', check=False)
        return r.stdout.split()[0] if r.stdout.strip() else None

    def records(self, commit):
        """{index: dict(blob, family, split, pair)} at a commit, from recovery/episodes and recovery/receipts."""
        r = self.git('ls-tree', '-r', commit, check=False)
        eps, rec = {}, {}
        for line in r.stdout.splitlines():
            meta, path = line.split('\t', 1)
            blob = meta.split()[2]
            if '/episodes/' in path and path.endswith('.json.gz'):
                eps[Path(path).name[:-8]] = blob
            elif '/receipts/' in path and path.endswith('.json'):
                rec[Path(path).name[:-5]] = blob
        if not rec:
            return {k: dict(blob=b) for k, b in eps.items()}
        blobs = list(rec.values())
        out = self.git('cat-file', '--batch', input='\n'.join(blobs) + '\n', check=False).stdout
        texts, pos = {}, 0
        for b in blobs:                                  # --batch: "<sha> blob <size>\n<content>\n" per object
            nl = out.index('\n', pos)
            head = out[pos:nl].split()
            if len(head) < 3 or head[1] == 'missing':
                pos = nl + 1
                continue
            size = int(head[2])
            texts[b] = out[nl + 1:nl + 1 + size]
            pos = nl + 1 + size + 1
        recs = {}
        for k, b in eps.items():
            d = dict(blob=b)
            t = texts.get(rec.get(k))
            if t:
                try:
                    j = json.loads(t)
                    d.update(family=j.get('family'), pair=j.get('pair'), split_receipt=j.get('split'))
                except ValueError:
                    pass
            recs[k] = d
        return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', default='/home/claude/feeds.git')
    ap.add_argument('--inputs', required=True)
    ap.add_argument('--v2-fetch', action='append', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    c = Cache(a.cache)
    # 1. v2
    v2_tips = {}
    for f in a.v2_fetch:
        for br, info in json.load(open(f))['branches'].items():
            v2_tips.setdefault(info['tip'], br)
    c.fetch(list(v2_tips))
    v2_blobs, v2_fam = set(), set()
    for tip in v2_tips:
        for d in c.records(tip).values():
            v2_blobs.add(d['blob'])
            if d.get('family'):
                v2_fam.add(d['family'])
    print(f'v2: {len(v2_tips)} tips, {len(v2_blobs)} records, {len(v2_fam)} families', flush=True)
    # 3. now
    tips = {f: c.tip(f) for f in FEEDS}
    c.fetch([t for t in tips.values() if t])
    now = []
    for feed, tip in tips.items():
        if not tip:
            print(f'{feed}: no such branch'); continue
        rs = c.records(tip)
        for k, d in rs.items():
            now.append(dict(d, feed=feed, index=k))
        print(f'{feed}: {len(rs)} records at {tip[:10]}', flush=True)
    # 2. round 4's sample
    r4 = {Path(x[0]).name[:-8] for x in json.load(open(a.inputs))['arena']['sample']}
    by_blob = {d['blob']: d for d in now}
    r4_fam = {by_blob[b]['family'] for b in r4 if b in by_blob and by_blob[b].get('family')}
    print(f'round 4 sample: {len(r4)} records, {sum(b in by_blob for b in r4)} found on the feeds, {len(r4_fam)} families')
    excluded = v2_fam | r4_fam
    seen, cand = set(), []
    for d in now:
        if d['blob'] in seen:
            continue
        seen.add(d['blob'])
        fam = d.get('family')
        if not fam or d['blob'] in v2_blobs or d['blob'] in r4 or fam in excluded:
            continue
        d['split'] = split_of(fam)
        cand.append(d)
    test = [d for d in cand if d['split'] == 2]
    pairs = collections.Counter(d.get('pair') for d in test)
    fams = collections.Counter(d['family'] for d in test)
    print(f'untrained records {len(cand)}; in the test split {len(test)} records, {len(fams)} families')
    for p, n in pairs.most_common(30):
        print(f'  {n:5d}  {p}')
    Path(a.out).write_text(json.dumps(dict(v2_tips=len(v2_tips), v2_records=len(v2_blobs), v2_families=len(v2_fam),
                                           feeds=tips, r4_sample=len(r4), r4_families=len(r4_fam),
                                           untrained=len(cand), test=test), indent=1))


if __name__ == '__main__':
    main()
