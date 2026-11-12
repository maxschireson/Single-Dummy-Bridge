# boxctl: timeout=200
# Read-only: the independent collector's promotion gate for 7.1 against 7.0 (ops/check_gen71_gate.py at a588e09), run here over
# every registered Gen 7 feed: boards on families v4.1 was not trained on, one board a family, at least 1,000 boards and a
# 95% interval above zero.
set -uo pipefail
W=$HOME/work; G=$W/gen71/gate; SRC=$W/sdb-gen71x; RUN=$W/runs/gen71-vs70-fresh-azure2
mkdir -p "$G/target/artifacts/validation"
cp "$RUN/manifest.json" "$G/target/manifest.json"
cp "$W/gen71/all-training-families.json" "$G/target/artifacts/validation/all-training-families.json"
printf '{"target": "%s"}\n' "$G/target" > "$G/control.json"
curl -fsS --max-time 60 -o "$G/registry.json" "https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/gh-pages/arena/gen6-sources.json?t=$(date +%s)" || { echo "could not fetch the registry"; exit 1; }
git ls-remote --heads https://github.com/maxschireson/Single-Dummy-Bridge > "$G/heads.txt" 2>/dev/null || { echo "could not list branches"; exit 1; }
cd "$SRC" && TF_CPP_MIN_LOG_LEVEL=3 timeout 150 "$W/venv/bin/python" ops/check_gen71_gate.py --control "$G/control.json" --registry "$G/registry.json" --heads "$G/heads.txt" --out "$G/out.json" >/dev/null 2>"$G/err.txt" || { echo "gate script failed: $(tail -2 "$G/err.txt" | cut -c1-300)"; exit 1; }
"$W/venv/bin/python" - "$G/out.json" <<'PY'
import json, sys
o = json.load(open(sys.argv[1])); g = o['gate']
ci = g.get('ci')
print('GATE ' + json.dumps(dict(n=g['n'], mean=g['mean'], se=g['se'], ci=ci, eligible=g['eligible'], counts=o['counts'], excluded=o['excluded_training_families'],
      sources=[(s['branch'], s['cohort'][:12]) for s in o['sources']], errors=o['errors'])))
print(f"gate for 71s-32~7s-32: {g['n']} boards on families v4.1 was not trained on" + (f", mean {g['mean']:+.3f}, 95% interval {ci[0]:+.3f} to {ci[1]:+.3f}" if ci else '') + f"; eligible {g['eligible']}")
print('boards left out because their family is in the training list:', o['excluded_training_families'])
print('feeds read:', len(o['sources']), [s['branch'] for s in o['sources']])
print('errors:', o['errors'] or 'none')
PY
