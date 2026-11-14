# boxctl: timeout=1200
# loop session (Max, 18:53 and 19:00 UTC: two of the 8-core boxes in favour of one larger within the 48-vCPU quota; "Go!"):
# this box is to be stopped (deallocated; its disk and everything on it are kept) so that azure5 can grow to 16 cores.
# Here: the collection stops, the boards past the last published row block are built once more as cut files, and the
# publisher pushes. Nothing is deleted.
set -euo pipefail
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
tail -n 1 "$W/runs.log" | cut -c1-140
for r in sp3tb sp4tb; do printf '%s: %s records | ' $r "$(ls "$W/runs/$r/episodes" 2>/dev/null | wc -l)"; done; echo
sudo systemctl stop loop-collect loop-collect-b loop-rows 2>/dev/null || true; sleep 3
pkill -u "$USER" -f scripts/x8_match.py 2>/dev/null || true; sleep 2
echo "$(date -u +%FT%TZ) the collection stops: this box is deallocated so that azure5 can grow to 16 cores (Max, 19:00 UTC: Go). Its disk is kept." >> "$W/runs.log"
cd "$S"; bash $T/rows_cut.sh sp3sc sp3tb sp4tb 2>&1 | cut -c1-220
sudo systemctl restart loop-publish; sleep 75
git -C "$W/pub" log -1 --format='publisher last commit %ci'; echo "unpushed files: $(git -C "$W/pub" status --short | wc -l)"
ls -la "$W/pub/rows-cut" | tail -n 5 | cut -c1-120; ls "$W/pub/rows" | wc -l; df -h / | tail -1; date -u +%FT%TZ
