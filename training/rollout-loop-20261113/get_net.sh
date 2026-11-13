#!/usr/bin/env bash
# Puts a round's net where its bots read it:  get_net.sh ROUND SHA256
# Fetches train-r<ROUND>/policy.npz from the training box's transfer branch (azure5's), checks its sha256, and writes
# models/cardplay/stu-net-r<ROUND>-20261113/policy.npz in this checkout. The nets are not committed to the source branch.
set -euo pipefail
ROUND=$1; WANT=$2; cd "$(dirname "$0")/../.."
D=$(mktemp -d); git -C "$D" init -q
git -C "$D" fetch -q --depth 1 https://github.com/maxschireson/Single-Dummy-Bridge transfer/rollout-loop-azure5-20261113
mkdir -p "models/cardplay/stu-net-r$ROUND-20261113"
git -C "$D" show "FETCH_HEAD:train-r$ROUND/policy.npz" > "models/cardplay/stu-net-r$ROUND-20261113/policy.npz.tmp"; rm -rf "$D"
GOT=$(sha256sum "models/cardplay/stu-net-r$ROUND-20261113/policy.npz.tmp" | cut -c1-64)
[ "$GOT" = "$WANT" ] || { echo "sha256 mismatch: $GOT"; rm -f "models/cardplay/stu-net-r$ROUND-20261113/policy.npz.tmp"; exit 1; }
mv "models/cardplay/stu-net-r$ROUND-20261113/policy.npz.tmp" "models/cardplay/stu-net-r$ROUND-20261113/policy.npz"
echo "round $ROUND's net in place, sha256 ${GOT:0:16}"
