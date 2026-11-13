# boxctl: timeout=300
# boxctl: timeout=300
# sidweb discovery 2 (read-only): the Gen 8 bot spec and its source checkout.
set -u
R=~/work/runs/gen8-s7-azure1
ls $R | head -40
python3 - <<'PY'
import json,os
m=json.load(open(os.path.expanduser('~/work/runs/gen8-s7-azure1/manifest.json')))
print('manifest keys',sorted(m))
for k in ('8s-32','71s-32'):
    s=m['bots'][k]
    print('==',k, json.dumps({a:b for a,b in s.items() if a not in ('gen7','gen6','layout_reduction','artifact_sha256')},indent=1)[:3000])
    print('artifacts', json.dumps(s.get('artifact_sha256'),indent=1))
    for blk in ('gen7','gen8'):
        if blk in s: print(blk, json.dumps(s[blk])[:1500])
print('common_bidder', m.get('common_bidder'), 'source', {k:m.get(k) for k in m if 'source' in k or 'commit' in k})
PY
for f in $R/recovery/environment.json $R/environment.json; do [ -f $f ] && python3 -c "import json,sys;d=json.load(open('$f'));print({k:d[k] for k in d if 'commit' in k or 'source' in k or 'branch' in k})"; done
for d in ~/work/sdb-gen8 ~/work/sdb-g8p ~/work/g8/src ~/work/gen8; do [ -d $d/.git ] && echo "$d: $(git -C $d rev-parse --abbrev-ref HEAD) $(git -C $d rev-parse --short HEAD) $(git -C $d log -1 --format=%cI)"; done
systemctl list-units --type=service --no-pager 2>/dev/null | grep -Ei "arena|gen8|next8|publish" | head
du -sh $R/artifacts 2>/dev/null; ls $R/artifacts 2>/dev/null
