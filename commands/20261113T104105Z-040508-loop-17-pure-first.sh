# boxctl: timeout=600
# boxctl: timeout=600
# loop session: the ladder's deciding comparison first (Max, 10:39 UTC: "Can I see the rung gaps?"; at 172 deals the bot
# with no double dummy was within noise of Stu). Restart the chain from the reordered job file: the first pass's two
# ends and the nets alone, then Stu and the pure bot to 500 deals, then the same with v1, then the middle rungs.
set -euo pipefail
COMMIT=0723f0b4979845e0e048190b6061cb223c1411b2
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
sudo systemctl stop loop-chain || true
tail -n 2 "$W/runs.log" | cut -c1-140
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-110
sudo systemctl reset-failed loop-chain 2>/dev/null || true
sudo systemd-run --unit=loop-chain --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$T/chain.sh" "$T/jobs-azure3.txt"
sleep 45; systemctl is-active loop-chain loop-publish | tr '\n' ' '; echo; tail -n 3 "$W/runs.log" | cut -c1-150; for r in l0-p l0-v1-p; do echo "$r: $(wc -l < "$W/runs/$r/results.jsonl" 2>/dev/null) boards"; done; date -u +%FT%TZ
