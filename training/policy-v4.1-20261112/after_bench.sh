#!/bin/bash
# When the tree bench ends: push its rows (and which bots played each deal) to branch transfer/gen7-policy-v4.1-bench-20261112,
# on their own, so that they are safe whatever else is running. Summaries are made from the rows afterwards.
set -uo pipefail
P=$HOME/work/p41
while ! grep -q "bench exit" $P/logs/timeline.log; do sleep 3; done
W=$HOME/work/p41bench; rm -rf $W; mkdir -p $W && cd $W && git init -q
git config core.sshCommand "ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"
git config user.name "p41 training box (azure5)"; git config user.email "boxctl-azure5@invalid"
cp $P/runs/bench/* . 2>/dev/null; cp $P/logs/bench.log . 2>/dev/null; cp $P/logs/timeline.log . 2>/dev/null
gzip -9 rows.json 2>/dev/null
git add -A && git commit -q -m "Policy 4.1: tree bench rows on fresh fork pairs (v4's tree and 4.1's tree on the same pairs)" && \
  git push -q -f git@github.com:maxschireson/Single-Dummy-Bridge.git HEAD:refs/heads/transfer/gen7-policy-v4.1-bench-20261112 2>&1 | grep -v "^remote:" | tail -2
echo "bench pushed $(date -u +%T)" >> $P/logs/timeline.log
