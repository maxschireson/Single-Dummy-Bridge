# boxctl: timeout=600
# p41: the 4.1 training scripts (branch transfer/gen7-policy-v4.1-20261112) and the first fetch: every episode on
# the Gen 6 feeds, the Gen 7 phase 1 feeds and the pre-7 test branches, as of now. Runs as unit p41-fetch1.
set -euo pipefail
cd ~/work
if [ ! -d p41src/.git ]; then git clone -q --depth 1 --branch transfer/gen7-policy-v4.1-20261112 https://github.com/maxschireson/Single-Dummy-Bridge p41src; fi
git -C p41src log -1 --format='p41src %h %s' | cut -c1-120
P=$HOME/work/p41
echo "fetch1 start $(date -u +%T)" >> $P/logs/timeline.log
sudo systemd-run --unit=p41-fetch1 --uid="$(id -un)" --working-directory="$P" --setenv=HOME="$HOME" -- /bin/bash -c "
  $HOME/work/venv/bin/python $HOME/work/p41src/training/policy-v4.1-20261112/fetch_feeds.py --out $P/eps --work $P/git --manifest $P/data/fetch1.json --jobs 8 \
    'arena-gen6-*' 'arena-gen7-phase1-*' 'transfer/pre7-test-azure*-20261112' > $P/logs/fetch1.log 2>&1; echo \"fetch1 exit \$? \$(date -u +%T)\" >> $P/logs/timeline.log" 2>&1 | tail -1
sleep 20; tail -2 $P/logs/fetch1.log; cat $P/logs/timeline.log
