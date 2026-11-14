# boxctl: timeout=120
# boxctl: timeout=120
# loop session (Max, 05:30 UTC on 14 November: the test box measures BEN through the release): azure3's loop-switch is replaced.
# Once its BEN session ends (runs.log: "jobs-azure3-ben5.txt has ended") it moves the source to fb1dbbe and plays a second BEN
# session, jobs-azure3-ben6.txt (the one-net Stu R3 on deals 1,536 to 2,559), whose end starts the rest of the test queue and
# then Gen 8 records (jobs-azure3.txt). It changes the source only while nothing runs from it. Returns at once.
set -euo pipefail
W=$HOME/work/loop
cat > "$W/switch.sh" <<'EOS'
#!/usr/bin/env bash
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113; COMMIT=fb1dbbefd4409b63be9428e3258e4168c25ab530
while ! grep -q "jobs-azure3-ben5.txt has ended" "$W/runs.log"; do sleep 30; done
sleep 15
sudo systemctl stop loop-next loop-rungs loop-rungs2 loop-rungs3 loop-chain loop-collect-b 2>/dev/null
pkill -u "$USER" -f scripts/x8_match.py 2>/dev/null; sleep 5
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" checkout -q $COMMIT
echo "$(date -u +%FT%TZ) azure3, the test box (Max, 05:24 and 05:30 UTC): BEN through the release (jobs-azure3-ben6.txt), then the test queue and Gen 8 records (jobs-azure3.txt), source ${COMMIT:0:7}" >> "$W/runs.log"
bash "$S/$T/ben_session.sh" jobs-azure3-ben6.txt azure3
EOS
sudo systemctl stop loop-switch 2>/dev/null || true; sudo systemctl reset-failed loop-switch 2>/dev/null || true
sudo systemd-run --unit=loop-switch --uid="$USER" --working-directory="$W" --setenv=HOME="$HOME" -- bash "$W/switch.sh"
sleep 3; echo "switch: $(systemctl is-active loop-switch || true) | bensession: $(systemctl is-active loop-bensession || true)"; grep -c "COMMIT=fb1dbbefd4409b63be9428e3258e4168c25ab530" "$W/switch.sh"; tail -n 1 "$W/runs.log" | cut -c1-140; date -u +%FT%TZ
