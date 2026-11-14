python3 - <<EOF
import zipfile, os
p = os.path.expanduser("~/work/plan/rnet2w/data/train.npz")
z = zipfile.ZipFile(p)
tot = 0
for i in z.infolist():
    tot += i.file_size
    print("%-14s %8.3f GB  stored=%s" % (i.filename, i.file_size / 1e9, i.compress_type == 0))
print("total %.2f GB" % (tot / 1e9))
EOF
ls -la ~/work/loop/exp-strong | head -8; df -h / | tail -1
