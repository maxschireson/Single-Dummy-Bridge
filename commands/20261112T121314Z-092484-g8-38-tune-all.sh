# boxctl: timeout=120
# boxctl: timeout=120
# g8 (azure6): one pass of the tuner over every setting of the rule bidder with the estimate, on 12,000 fresh deals (seed 503) and
# report on 8,000 more (seed 502). Starts when the table job has finished. Output: est/tune-all.json and .log.
set -uo pipefail
G=$HOME/work/g8
mkdir -p "$G/est" "$G/pub/est"
python3 - <<'PY'
import json, os
s = json.loads('''{"settings": {"style": "precision", "club_min": 16, "open_min": 11, "open_light": 1, "limited_max": 15, "nt_lo": 14, "nt_hi": 16, "nt_five_major": false, "two_clubs_len": 6, "two_diamonds": true, "weak_lo": 5, "weak_hi": 10, "weak_quality": 2, "preempt_len": 7, "neg_max": 7, "resp_min": 6, "two_over_one": 11, "game": 25, "game_minor": 28, "slam": 32, "grand": 37, "invite_width": 2, "overcall_min1": 7, "overcall_min2": 11, "overcall_max": 17, "overcall_quality": 1, "takeout_min": 12, "nt_overcall_lo": 15, "nt_overcall_hi": 18, "jump_overcalls": true, "balance": 3, "compete": 0, "penalty": 25, "stayman": true, "transfers": true, "estimate": "configs/rule-systems/precision-estimate-e2.json", "est_band": 2, "est_weight": 5, "est_contest": 10, "est_reach": 2, "est_double": 35, "est_sigma": 12}}''')
json.dump(s, open(os.path.expanduser('~/work/g8/est/r4-start.json'), 'w'), indent=1)
PY
cat > "$G/tune-all.sh" <<'SH'
#!/usr/bin/env bash
G=$HOME/work/g8; D=$G/src-tune; PY=$HOME/work/venv/bin/python; CAP=$HOME/work/capsule-gen7-capture/recovery
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
[ -d "$D/.git" ] || { git init -q "$D"; git -C "$D" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; }
cd "$D" || exit 1
git fetch -q --depth 1 origin 15dbb0ec75843093c7938fb2eca3faa79d723809 && git checkout -q FETCH_HEAD || { echo "could not check out" > "$G/est/tune-all.log"; exit 1; }
"$PY" -u scripts/tune_rule_bidder.py tune --source "$CAP" --seed 503 --deals 12000 --test-seed 502 --test-deals 8000 --cache "$G/ddcache" \
  --workers 8 --settings "$G/est/r4-start.json" --passes 1 --keep 2 --out "$G/est/tune-all.json" > "$G/est/tune-all.log" 2>&1
cp -f "$G/est/tune-all.json" "$G/est/tune-all.log" "$G/pub/est/" 2>/dev/null
SH
chmod +x "$G/tune-all.sh"
sudo systemctl stop g8-tune-all 2>/dev/null; sudo systemctl reset-failed g8-tune-all 2>/dev/null
sudo systemd-run --quiet --unit=g8-tune-all --uid="$(id -un)" --setenv=HOME="$HOME" --working-directory="$G" -- "$G/tune-all.sh"
sleep 5; echo "tune unit: $(systemctl is-active g8-tune-all); "; sleep 40; tail -2 "$G/est/tune-all.log" | cut -c1-200
