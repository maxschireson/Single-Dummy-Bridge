# boxctl: timeout=120
# boxctl: timeout=120
# g8 (azure4, mine until 15:00 UTC at the latest): record the states of the estimate-using rule bidder on sixteen seeds
# (64,000 deals), to refit its trick estimate on its own auctions. Output: est/states-r4b.npz on the results branch.
set -uo pipefail
G=$HOME/work/g8
mkdir -p "$G/est" "$G/pub/est"
python3 - <<'PY'
import json, os
json.dump(json.loads(r"""{"settings": {"style": "precision", "club_min": 16, "open_min": 11, "open_light": 1, "limited_max": 15, "nt_lo": 14, "nt_hi": 16, "nt_five_major": false, "two_clubs_len": 6, "two_diamonds": true, "weak_lo": 4, "weak_hi": 10, "weak_quality": 1, "preempt_len": 6, "neg_max": 7, "resp_min": 6, "two_over_one": 11, "game": 25, "game_minor": 27, "slam": 32, "grand": 37, "invite_width": 2, "overcall_min1": 7, "overcall_min2": 11, "overcall_max": 17, "overcall_quality": 1, "takeout_min": 12, "nt_overcall_lo": 15, "nt_overcall_hi": 18, "jump_overcalls": true, "balance": 3, "compete": 0, "penalty": 24, "stayman": true, "transfers": true, "estimate": "configs/rule-systems/precision-estimate-e2.json", "est_band": 2, "est_weight": 5, "est_contest": 10, "est_reach": 2, "est_double": 35, "est_sigma": 12, "est_slam_band": 4}}"""), open(os.path.expanduser('~/work/g8/est/r4b.json'), 'w'), indent=1)
PY
cat > "$G/states2.sh" <<'SH'
#!/usr/bin/env bash
G=$HOME/work/g8; D=$G/src-tune; PY=$HOME/work/venv/bin/python; CAP=$HOME/work/capsule-gen7-capture/recovery
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
cd "$D" || exit 1
git fetch -q --depth 1 origin 7334ef18919536cfecee9ea6251de52dd3783e22 && git checkout -q FETCH_HEAD || { echo "could not check out" > "$G/est/states2.log"; exit 1; }
"$PY" scripts/fit_rule_estimator.py dump --source "$CAP" --seeds 401,402,403,404,405,406,407,408,411,412,413,414,415,416,417,418 --deals 4000 \
  --settings "$G/est/r4b.json" --workers 8 --out "$G/est/states-r4b.npz" > "$G/est/states2.log" 2>&1
cp -f "$G/est/states-r4b.npz" "$G/pub/est/"; cp -f "$G/est/tune-est.json" "$G/est/tune-est.log" "$G/pub/est/" 2>/dev/null
echo done >> "$G/est/states2.log"
SH
chmod +x "$G/states2.sh"
sudo systemctl stop g8-states2 2>/dev/null; sudo systemctl reset-failed g8-states2 2>/dev/null
sudo systemd-run --quiet --unit=g8-states2 --uid="$(id -un)" --setenv=HOME="$HOME" --working-directory="$G" -- "$G/states2.sh"
sleep 100; echo "unit: $(systemctl is-active g8-states2)"; tail -3 "$G/est/states2.log" | cut -c1-200
