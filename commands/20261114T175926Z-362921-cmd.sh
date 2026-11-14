# boxctl: timeout=240
# loop session (Max, 17:57 UTC: "If it's by rows we should make sure we have full rows. Do we have enough disk or can we
# reorganize the process?"): a read-only inventory of this box's disk, memory and row files.
set -uo pipefail
W=$HOME/work/loop
df -h / | tail -1; free -g | sed -n 2p; nproc
echo "== ~/work"; du -sh $HOME/work/* 2>/dev/null | sort -h | tail -8
echo "== ~/work/loop"; du -sh $W/* 2>/dev/null | sort -h | tail -16
echo "== plan data"; ls -la $HOME/work/plan/rnet2w/data/ 2>/dev/null | head -12
echo "== runs (largest)"; du -sh $W/runs/* 2>/dev/null | sort -h | tail -12
echo "== arena"; ls $W/r4arena 2>/dev/null | head; for d in eps eps_sample odd; do [ -d $W/r4arena/$d ] && echo "$d: $(ls $W/r4arena/$d | wc -l) files, $(du -sh $W/r4arena/$d | cut -f1)"; done
echo "== in (rows from other boxes)"; du -sh $W/in/* 2>/dev/null | sort -h | tail -8; ls $W/in 2>/dev/null | head -20
python3 - <<'PY'
import numpy as np, os, zipfile
p = os.path.expanduser('~/work/plan/rnet2w/data/train.npz')
if os.path.exists(p):
    z = zipfile.ZipFile(p)
    print('BIG members:', [(i.filename, round(i.file_size / 1e9, 2), round(i.compress_size / 1e9, 2)) for i in z.infolist()])
PY
date -u +%T
