#!/usr/bin/env bash
# Rebuilds the Stu dashboard's snapshot from the loop's branches and publishes the page to gh-pages:stu/.
#   bash web/stu/publish.sh [REPO]
# REPO is a git checkout whose origin is the GitHub repository (default: the checkout this script is in). Only files
# under stu/ on gh-pages are written; a push that loses a race is redone on the new tip, up to five times.
# STU_TRAILERS, if set, is appended to the commit message (Co-Authored-By / Claude-Session lines).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=${1:-$(git -C "$HERE" rev-parse --show-toplevel)}
W=$(mktemp -d)
cleanup() { git -C "$REPO" worktree remove --force "$W/pages" >/dev/null 2>&1 || true; rm -rf "$W"; }
trap cleanup EXIT
mkdir -p "$W/out"
node "$HERE/build.cjs" --repo "$REPO" --registry "$HERE/registry.json" --out "$W/out/data.json"
cp "$HERE/index.html" "$HERE/stu-core.js" "$HERE/registry.json" "$W/out/"
git -C "$REPO" fetch -q --depth 3 origin +refs/heads/gh-pages:refs/remotes/origin/gh-pages
git -C "$REPO" worktree add -q --detach "$W/pages" refs/remotes/origin/gh-pages
cd "$W/pages"
for attempt in 1 2 3 4 5; do
  mkdir -p stu && cp "$W/out/"* stu/ && git add stu
  if git diff --cached --quiet; then echo "gh-pages:stu/ already current"; exit 0; fi
  git -c user.name="Stu dashboard" -c user.email=noreply@anthropic.com commit -q \
    -m "Stu dashboard: snapshot $(date -u +%FT%TZ)" ${STU_TRAILERS:+-m "$STU_TRAILERS"}
  if git -c push.negotiate=true push -q origin HEAD:refs/heads/gh-pages 2>"$W/push.err"; then
    echo "published $(git rev-parse --short HEAD) to gh-pages:stu/"; exit 0
  fi
  grep -v -i "negotiat" "$W/push.err" | tail -2 >&2 || true
  sleep $((attempt * 5))
  git -C "$REPO" fetch -q --depth 3 origin +refs/heads/gh-pages:refs/remotes/origin/gh-pages
  git reset -q --hard refs/remotes/origin/gh-pages
done
echo "could not push to gh-pages after five attempts" >&2; exit 1
