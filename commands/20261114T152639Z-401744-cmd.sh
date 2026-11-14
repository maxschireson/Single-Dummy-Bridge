# boxctl: timeout=300
# loop session: round 4's control net to azure3 for its turns in the gate (get_net.sh 4c).
set -euo pipefail
SHA4C=e4b689c87db2f56b98221a491757dbf348ddaea066e016f06a9331fc671197f2
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
cd "$S"; git log -1 --format='source %h'; bash $T/get_net.sh 4c "$SHA4C"
tail -n 3 "$W/runs.log" | cut -c1-170; for r in bu4-pst200a bu4-pst200b bu4c-pst200a; do printf '%s: %s boards | ' $r "$(cat "$W"/runs/$r-[1-8]/results.jsonl 2>/dev/null | wc -l)"; done; echo; date -u +%FT%TZ
