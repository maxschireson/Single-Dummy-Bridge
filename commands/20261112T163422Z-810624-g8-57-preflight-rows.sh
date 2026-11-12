# boxctl: timeout=60
# boxctl: timeout=60
# g8 (azure6): read-only. The deals the two cut-short preflight plays completed and checked (their logs under ~/work/g8).
G=$HOME/work/g8
for f in preflight2.log preflight3.log; do
  [ -e "$G/$f" ] || { echo "$f: not there"; continue; }
  "$HOME/work/venv/bin/python" - "$G/$f" <<'PY'
import json, sys, os, collections
rows = []
for line in open(sys.argv[1], errors='replace'):
    line = line.strip()
    if line.startswith('{') and '"index"' in line:
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
print(os.path.basename(sys.argv[1]), '| deals completed and checked:', len(rows), '| by pair:', dict(collections.Counter(d['pair'] for d in rows)))
for d in rows:
    print(f"   deal {d['index']} {d['pair']}: {round(d['seconds'])}s, tables {d['tables']}, IMPs {d['imps']}, searched {d['decisions']}, unsearched {d['unsearched']}, in a stage {d['in_a_stage']}, consulted {d['consulted']}, moved {d['moved']}, gap forks {d['gap_forks']}")
PY
  grep -v -E "absl|oneDNN|cpu_feature|AVX|^WARNING|^\{|^I0000|^E0000|^W0000|tensorflow|^$" "$G/$f" | tail -5 | cut -c1-300
done
