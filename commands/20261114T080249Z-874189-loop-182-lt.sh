# boxctl: timeout=120
# boxctl: timeout=120
# loop session (scorer with IMP costs and make/set changes, Max 07:51 UTC; first: Max, 07:12 to 07:24 UTC: lost tricks against double dummy for every player, every USBC category): a unit of its
# own (loop-usbclt, Nice 15, 2 workers) scores each USBC session this box has harvested (lost_tricks.py, one small file a
# session into ~/work/loop/pub/usbc-lt/, pushed by the publisher), every ten minutes until the harvest has ended. Returns at once.
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q d413970f8fac21f1ae86266c9a5793fe5de73f8a
ln -sfn "$W/src/bridge_harness/libbridge_dds.so" "$S2/bridge_harness/libbridge_dds.so" 2>/dev/null || true
cat > "$W/usbclt.sh" <<'EOS'
#!/usr/bin/env bash
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python
cd "$S2"; export BRIDGE_DDS_CACHE= OPENBLAS_NUM_THREADS=1
while :; do
  active=$(systemctl is-active loop-usbc loop-usbc25 2>/dev/null | grep -c '^active$')
  nice -n 15 "$PY" training/rollout-loop-20261113/usbc/lost_tricks.py "$W/pub/usbc" "$W/pub/usbc-lt" --workers 2 >> "$W/usbclt.log" 2>&1
  [ "$active" -gt 0 ] || break
  sleep 600
done
echo "$(date -u +%FT%TZ) lost tricks scored for every harvested session" >> "$W/usbclt.log"
EOS
sudo systemctl stop loop-usbclt 2>/dev/null || true; sudo systemctl reset-failed loop-usbclt 2>/dev/null || true
sudo systemd-run --unit=loop-usbclt --uid="$USER" --working-directory="$S2" --setenv=HOME="$HOME" -- bash "$W/usbclt.sh"
sleep 5; systemctl is-active loop-usbclt loop-usbc | tr '\n' ' '; tail -n 3 "$W/usbc.log" | cut -c1-150; ls "$W/pub/usbc" | wc -l; date -u +%FT%TZ
