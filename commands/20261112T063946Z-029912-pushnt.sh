# boxctl: timeout=120
#!/bin/bash
set -uo pipefail
P=$HOME/work/p41
W=$HOME/work/p41nt; rm -rf $W; mkdir -p $W && cd $W && git init -q
git config core.sshCommand "ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"
git config user.name "p41 training box (azure5)"; git config user.email "boxctl-azure5@invalid"
cp $P/runs/neartie/* . ; cp $P/logs/neartie*.log $P/logs/pairsE.log . 2>/dev/null
git add -A && git commit -q -m "Near-tie selectors on fresh fork pairs: report and log" && \
  git push -q -f git@github.com:maxschireson/Single-Dummy-Bridge.git HEAD:refs/heads/transfer/gen7-policy-v4.1-neartie-20261112 2>&1 | grep -v "^remote:" | tail -2
ls -la; tail -3 $P/logs/timeline.log; tail -c 200 $P/logs/w768e5.err
