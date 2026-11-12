#!/bin/bash
# Push everything this box produced to branch transfer/gen7-policy-v4.1-box-20261112, as one commit that replaces the last:
# every run's weights by epoch (and each run's last epoch calibrated, in the repository's chunked form), the logs, the fetch
# manifests, the fork pairs, the result head, the tree bench's rows and the layout-weight checks. About 100 MB, mostly weights.
# The training set itself (10 GB) is not pushed; the first manifest and the builder reproduce it.
set -uo pipefail
P=$HOME/work/p41; S=$HOME/work/p41src; PY=$HOME/work/venv/bin/python
SCORER=$HOME/work/repo/models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz
W=$HOME/work/p41out; rm -rf $W; mkdir -p $W/logs $W/data && cd $W && git init -q
git config core.sshCommand "ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"
git config user.name "p41 training box (azure5)"; git config user.email "boxctl-azure5@invalid"
declare -A NAME=([w512]=gen7_policy_v4.1 [w768]=gen7_policy_v4.1_w768 [w512e5]=gen7_policy_v4.1_e5 [w768e5]=gen7_policy_v4.1_w768_e5)
for R in $P/runs/w*; do
  run=$(basename $R); [ -e $R/metrics.json ] || continue
  mkdir -p runs/$run; cp $R/metrics.json runs/$run/
  for f in $R/policy_epoch?.npz; do cp $f runs/$run/; done
  last=$(ls $R/policy_epoch?_T.npz 2>/dev/null | sort | tail -1)
  [ -n "$last" ] && [ -n "${NAME[$run]:-}" ] && $PY $S/training/policy-v4.1-20261112/package_net.py $last packaged/${NAME[$run]} ${NAME[$run]}.npz $SCORER $R/metrics.json > /dev/null
done
cp $P/logs/*.log $P/logs/*.out $P/logs/*.err logs/ 2>/dev/null
cp $P/data/fetch*.json $P/data/pairs*.npz data/ 2>/dev/null
for d in $P/runs/result_head* $P/runs/bench; do [ -d $d ] && cp -r $d runs/; done
if [ -d $P/runs/infer ]; then mkdir -p runs/infer; for f in $P/runs/infer/*.json; do [ -e $f ] && gzip -9 -c $f > runs/infer/$(basename $f).gz; done; fi
[ -e runs/bench/rows.json ] && gzip -9 -f runs/bench/rows.json
git -C $S log -1 --format='scripts at %H' > SOURCE.txt; date -u +"pushed %Y-%m-%dT%H:%M:%SZ" >> SOURCE.txt
git add -A && git commit -q -m "Policy 4.1 training box output (azure5): nets by epoch, logs, manifests, fork pairs, bench rows, checks" && \
  git push -q -f git@github.com:maxschireson/Single-Dummy-Bridge.git HEAD:refs/heads/transfer/gen7-policy-v4.1-box-20261112 2>&1 | grep -v "^remote:" | tail -2
du -sh --exclude=.git $W | cut -f1; git log -1 --format='%h %s' | cut -c1-80; ls packaged 2>/dev/null | tr '\n' ' '; echo
