# boxctl: timeout=150
#!/bin/bash
set -uo pipefail
P=$HOME/work/p41; S=$HOME/work/p41src
cd $S
git fetch -q --depth 1 origin transfer/gen7-policy-v4.1-20261112 && git show FETCH_HEAD:scripts/gen7_near_tie.py > scripts/gen7_near_tie.py
sudo systemctl reset-failed p41-neartie 2>/dev/null
sudo systemd-run --unit=p41-neartie --uid="$(id -un)" --working-directory="$S" --setenv=HOME="$HOME" --nice=19 -- /bin/bash -c "bash $P/neartie.sh; bash $P/pushnt.sh" 2>&1 | tail -1
cat > $P/pushnt.sh <<'EOS'
#!/bin/bash
P=$HOME/work/p41
W=$HOME/work/p41nt; rm -rf $W; mkdir -p $W && cd $W && git init -q
git config core.sshCommand "ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"
git config user.name "p41 training box (azure5)"; git config user.email "boxctl-azure5@invalid"
cp -r $P/runs/neartie/* . ; cp $P/logs/neartie*.log $P/logs/pairs?.log . 2>/dev/null
git add -A && git commit -q -m "Near-tie selectors on fresh fork pairs: reports and logs" && \
  git push -q -f git@github.com:maxschireson/Single-Dummy-Bridge.git HEAD:refs/heads/transfer/gen7-policy-v4.1-neartie-20261112 2>&1 | grep -v "^remote:" | tail -2
echo "neartie pushed $(date -u +%T)" >> $P/logs/timeline.log
EOS
sleep 45
tail -2 $P/logs/timeline.log; cut -c1-330 $P/logs/w768e5.out | tail -1; tail -c 120 $P/logs/w768e5.err
