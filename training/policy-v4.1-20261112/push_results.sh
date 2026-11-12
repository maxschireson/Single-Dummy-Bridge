#!/bin/bash
# Push what this box produced to branch transfer/gen7-policy-v4.1-box-20261112: the nets (every epoch, and the
# calibrated ones in the repository's chunked form), the logs, the fetch manifests, the fork pairs and the result head.
# One commit, replaced on each run. The training set itself (10 GB) is not pushed; the manifests say how to rebuild it.
set -uo pipefail
P=$HOME/work/p41; S=$HOME/work/p41src; PY=$HOME/work/venv/bin/python
SCORER=$HOME/work/repo/models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz
W=$HOME/work/p41out; rm -rf $W; mkdir -p $W/logs $W/data && cd $W && git init -q
git config core.sshCommand "ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"
git config user.name "p41 training box (azure5)"; git config user.email "boxctl-azure5@invalid"
for w in 512 768; do
  R=$P/runs/w$w; [ -d $R ] || continue
  mkdir -p runs/w$w; cp $R/policy_epoch*.npz $R/metrics.json runs/w$w/ 2>/dev/null
  for e in 3 2 1; do
    if [ -e $R/policy_epoch${e}_T.npz ]; then
      name=$([ $w = 512 ] && echo gen7_policy_v4.1 || echo gen7_policy_v4.1_w768)
      [ $e = 3 ] || name=${name}_epoch$e
      [ $e = 3 ] && $PY $S/training/policy-v4.1-20261112/package_net.py $R/policy_epoch${e}_T.npz packaged/$name $name.npz $SCORER $R/metrics.json
    fi
  done
done
cp $P/logs/*.log $P/logs/*.out $P/logs/*.err logs/ 2>/dev/null
cp $P/data/fetch*.json data/ 2>/dev/null
cp $P/data/pairs*.npz data/ 2>/dev/null
for d in $P/runs/result_head*; do [ -d $d ] && cp -r $d runs/; done
git -C $S log -1 --format='scripts at %H' > SOURCE.txt; date -u +"pushed %Y-%m-%dT%H:%M:%SZ" >> SOURCE.txt
git add -A && git commit -q -m "Policy 4.1 training box output (azure5): nets, logs, manifests, fork pairs" && \
  git push -q -f git@github.com:maxschireson/Single-Dummy-Bridge.git HEAD:refs/heads/transfer/gen7-policy-v4.1-box-20261112 2>&1 | grep -v "^remote:" | tail -2
du -sh $W --exclude=.git | cut -f1; git log -1 --format='%h %s'; ls packaged 2>/dev/null
