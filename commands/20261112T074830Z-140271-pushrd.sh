# boxctl: timeout=900
#!/bin/bash
P=$HOME/work/p41
cat > $P/pushrd.sh <<'EOS'
#!/bin/bash
P=$HOME/work/p41
W=$HOME/work/p41rd; rm -rf $W; mkdir -p $W && cd $W && git init -q
git config core.sshCommand "ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"
git config user.name "p41 box (azure5)"; git config user.email "boxctl-azure5@invalid"
cp $P/runs/reading_reports/* . 2>/dev/null; cp $P/logs/eval_direct.log . 2>/dev/null; cat $P/runs/reading/pools-0?.log > pools.log 2>/dev/null; cp $P/logs/timeline.log .
git add -A && git commit -q -m "Gen 8 reading bench: reports" && \
  git push -q -f git@github.com:maxschireson/Single-Dummy-Bridge.git HEAD:refs/heads/transfer/gen8-p41-reading-20261112 2>&1 | grep -v "^remote:" | tail -2
echo "reading reports pushed $(date -u +%T)" >> $P/logs/timeline.log
EOS
chmod +x $P/pushrd.sh
while ! grep -q "report t1 done" $P/logs/timeline.log; do sleep 5; done
bash $P/pushrd.sh; tail -3 $P/logs/timeline.log; ls -la $P/runs/reading_reports | awk '{print $5, $9}'
