# boxctl: timeout=1800
# Ending-table copy: fetch the 1- to 4-card tables from azure6 (172.16.0.9:8765, private network) into ~/work/endtable/tables,
# at idle I/O and CPU priority, and keep each file only if its SHA-256 equals the built table's (REPORT.md, sections 4 and 5).
set -euo pipefail
D=$HOME/work/endtable/tables
mkdir -p "$D"; cd "$D"
cat > SHA256SUMS <<'SUMS'
be646285f1b1cfc819164d51a20c0f2200f2270bb5acd7b6a7d4e77c3b5e7dd6  k1.et
f5733f22a4c97af868ac1037f55d1b351cb71a9ac2e488ad36b9227c12e94aee  k2.et
cfafa36d8f07976312c0ac2b4912c1f961f4221d1b388c85f781ce3b0c83c74d  k3.et
4f455627f5c12f60ea90fe23ed65c57edc139f77cb8ea58b8bac99d6815f4f02  k4.et
SUMS
for f in k1.et k2.et k3.et k4.et; do
  want=$(awk -v f=$f '$2 == f {print $1}' SHA256SUMS)
  if [ -e "$f" ] && [ "$(nice -n 19 ionice -c3 sha256sum "$f" | cut -c1-64)" = "$want" ]; then echo "$f already present"; continue; fi
  t0=$(date +%s)
  nice -n 19 ionice -c3 curl -sS --fail --connect-timeout 10 -o "$f.part" "http://172.16.0.9:8765/$f"
  got=$(nice -n 19 ionice -c3 sha256sum "$f.part" | cut -c1-64)
  [ "$got" = "$want" ] || { rm -f "$f.part"; echo "$f: hash $got differs; removed"; exit 1; }
  mv "$f.part" "$f"
  echo "$f: $(stat -c %s "$f") bytes in $(( $(date +%s) - t0 )) s, hash ok"
done
ls -la "$D"
