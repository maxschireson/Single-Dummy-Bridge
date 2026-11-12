# boxctl: timeout=120
# p41: publish the names of the fresh episodes on deals the training set does not have (two shards), so the layout-weight check
# can also be run away from this box. A few kilobytes, to branch transfer/gen7-policy-v4.1-lists-20261112.
set -uo pipefail
P=$HOME/work/p41; W=$HOME/work/p41lists; rm -rf $W; mkdir -p $W && cd $W && git init -q
git config core.sshCommand "ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"
git config user.name "p41 training box (azure5)"; git config user.email "boxctl-azure5@invalid"
for s in s0 s1; do ls $P/epsV/$s | sed 's/\.json\.gz$//' > unseen_$s.txt; wc -l < unseen_$s.txt; done
git add -A && git commit -q -m "Policy 4.1: blob ids of the fresh episodes on deals the training set does not have (sets B, C, D), in two shards" && git push -q -f git@github.com:maxschireson/Single-Dummy-Bridge.git HEAD:refs/heads/transfer/gen7-policy-v4.1-lists-20261112 2>&1 | grep -v "^remote:" | tail -1
tail -1 $P/logs/w512e5.err; tail -1 $P/logs/w768e5.err
