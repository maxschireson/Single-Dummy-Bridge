# boxctl: timeout=300
# E2 (medium priority), data preparation step 1: snapshot the Gen 6 feeds' episodes onto this box, at the lowest
# CPU and disk priority so the phase 1 collector (high priority) keeps its cores.
set -euo pipefail
W=$HOME/work; mkdir -p "$W/feeds" "$W/e2"
cat > "$W/e2/fetch.sh" <<'SH'
#!/usr/bin/env bash
cd "$HOME/work/feeds" || exit 1
for b in arena-gen6-gen7-capture-feed arena-gen6-codex-v7-capture-feed arena-gen6-fast-selfplay-cloud-feed arena-gen6-extra-selfplay-feed \
         arena-gen6-fast-selfplay-independent-feed arena-gen6-fast-selfplay-20261111-19bbdce5-feed arena-gen6-fast-selfplay-codex-20261111 \
         arena-gen6-fast-selfplay-primary-feed arena-gen6-chatgpt-feed arena-gen6-codex-feed arena-gen6-independent-feed arena-gen6-medium-ben-feed \
         arena-gen6-ben-expansion-feed arena-gen6-codex-ben-followups-feed; do
  if [ ! -d "$b/.git" ]; then
    rm -rf "$b"
    git clone -q --depth 1 --single-branch --branch "$b" https://github.com/maxschireson/Single-Dummy-Bridge "$b" 2>/dev/null || { echo "$(date -u +%T) FAILED $b"; continue; }
  fi
  n=$(ls "$b/recovery/episodes" 2>/dev/null | wc -l)
  echo "$(date -u +%T) $b $(git -C "$b" rev-parse HEAD) episodes=$n size=$(du -sh "$b" | cut -f1)"
done
echo "$(date -u +%T) DONE total=$(du -sh . | cut -f1)"
SH
chmod +x "$W/e2/fetch.sh"
systemctl is-active --quiet e2-fetch && { echo "already running"; exit 0; }
sudo systemd-run --quiet --unit=e2-fetch --uid="$(id -un)" --setenv=HOME="$HOME" --nice=19 --property=IOSchedulingClass=idle \
  --property=StandardOutput=append:"$W/e2/fetch.log" --property=StandardError=append:"$W/e2/fetch.log" -- "$W/e2/fetch.sh"
sleep 20; echo "e2-fetch: $(systemctl is-active e2-fetch)"; cat "$W/e2/fetch.log" 2>/dev/null | tail -3
