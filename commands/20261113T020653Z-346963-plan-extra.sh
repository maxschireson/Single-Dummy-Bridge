# boxctl: timeout=300
# boxctl: timeout=300
# plan session: which of v1's episodes (fetched at 00:00) are no longer at any feed tip (v2's fetch at 01:15), and why:
# for each, its branch and path at 00:00 and what that path holds now.
set -uo pipefail
P=$HOME/work/plan
cd $P
python3 - <<'PY'
import subprocess, os, collections, re, json
P = os.path.expanduser('~/work/plan')
EP = re.compile(r'(^|/)episodes/[^/]+\.json\.gz$')
def tree(git_dir):
    refs = subprocess.run(['git', '--git-dir', git_dir, 'for-each-ref', '--format=%(refname) %(objectname)', 'refs/feeds/'], capture_output=True, text=True).stdout.split('\n')
    out = {}
    for line in refs:
        if not line.strip(): continue
        ref, tip = line.split()
        for l in subprocess.run(['git', '--git-dir', git_dir, 'ls-tree', '-r', tip], capture_output=True, text=True).stdout.splitlines():
            meta, path = l.split('\t', 1)
            if EP.search(path):
                out.setdefault(meta.split()[2], []).append((ref[len('refs/feeds/'):], path))
    return out
old = tree(P + '/rnet1/git/base.git')
new = tree(P + '/rnet2/git/base.git')
v1 = {f.split('.')[0] for f in os.listdir(P + '/rnet1/eps')}
v2 = {f.split('.')[0] for f in os.listdir(P + '/rnet2/eps')}
extra = sorted(b for b in v1 if b not in new)
print('v1 blobs', len(v1), 'at tips at 00:00', sum(b in old for b in v1), '; v2 new blobs', len(v2), '; v1 blobs not at any tip at 01:15:', len(extra))
newpath = {(br, p): b for b, locs in new.items() for br, p in locs}
why = collections.Counter(); bybranch = collections.Counter()
for b in extra:
    for br, p in old.get(b, [('?', '?')])[:1]:
        bybranch[br] += 1
        now = newpath.get((br, p))
        why['path now holds another blob' if now else ('branch gone' if not any(k[0] == br for k in newpath) else 'path gone from branch')] += 1
print('why:', dict(why))
print('by branch at 00:00:', bybranch.most_common(12))
open(P + '/rnet2/extra_blobs.txt', 'w').write('\n'.join(extra) + '\n')
json.dump({b: old.get(b, []) for b in extra}, open(P + '/rnet2/extra_where.json', 'w'))
PY
