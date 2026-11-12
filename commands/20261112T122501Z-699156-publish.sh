# boxctl: timeout=100
#!/bin/bash
W=$HOME/work; G=$W/g8p41; P=$W/p41; PY=$W/venv/bin/python; M=$G/models/cardplay
cd $G && git fetch -q --depth=1 origin feature/gen8-p41-20261112 && git show FETCH_HEAD:scripts/gen8_reading_bench.py > scripts/gen8_reading_bench.py && git show FETCH_HEAD:reports/gen8-reading-by-net-2026-11-12/POOLS.md > $P/POOLS.md
du -sh $P/runs/reading; ls $P/runs/reading | sed 's/-.*//' | sort | uniq -c | tr '\n' ' '; echo
cat > $P/publish_pools.sh <<'EOS'
#!/bin/bash
W=$HOME/work; G=$W/g8p41; P=$W/p41; PY=$W/venv/bin/python; M=$G/models/cardplay
cd $G; export OPENBLAS_NUM_THREADS=1 BRIDGE_DDS_CACHE=
$PY scripts/gen8_reading_bench.py cards --out $P/runs/reading --episodes $P/epsB --redo --net any=$M/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz > $P/logs/cards2.out 2>&1
echo "cards with scorer weights exit $? $(date -u +%T)" >> $P/logs/timeline.log
D=$W/p41pools; rm -rf $D; mkdir -p $D && cd $D && git init -q
git config core.sshCommand "ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"
git config user.name "p41 box (azure5)"; git config user.email "boxctl-azure5@invalid"
cp $P/runs/reading/pools-*.npz $P/runs/reading/own-*.npz $P/runs/reading/uns-*.npz $P/runs/reading/scw-*.npz $P/runs/reading/tab-*.json.gz $P/runs/reading/pools-0?.log .
for f in pools-0?.log; do mv $f ${f%.log}.txt; done
cp $P/POOLS.md README.md
git add -A && git commit -q -m "Gen 8 reading bench: the stored layouts and solves of the 530-table run (12 November 2026)

Made by scripts/gen8_reading_bench.py on feature/gen8-p41-20261112; the format is in README.md and the results in
reports/gen8-reading-by-net-2026-11-12 on that branch." && \
  git push -q -f git@github.com:maxschireson/Single-Dummy-Bridge.git HEAD:refs/heads/transfer/gen8-p41-reading-pools-20261112 2>&1 | grep -v "^remote:" | tail -3
echo "pools published exit $? $(date -u +%T) $(du -sh .git | cut -f1) $(ls | wc -l) files" >> $P/logs/timeline.log
EOS
chmod +x $P/publish_pools.sh
sudo systemd-run --unit=g8-publish-pools --uid="$(id -un)" --working-directory="$G" --setenv=HOME="$HOME" -- /bin/bash $P/publish_pools.sh 2>&1 | tail -1
