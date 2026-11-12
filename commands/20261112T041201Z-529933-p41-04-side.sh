# boxctl: timeout=120
# p41: update the scripts (chain.sh is unchanged, so the running chain is not disturbed) and start the side jobs as unit p41-side.
set -euo pipefail
P=$HOME/work/p41; cd ~/work/p41src
before=$(sha256sum training/policy-v4.1-20261112/chain.sh | cut -c1-16)
git fetch -q --depth 1 origin transfer/gen7-policy-v4.1-20261112 && git reset -q --hard FETCH_HEAD
after=$(sha256sum training/policy-v4.1-20261112/chain.sh | cut -c1-16); echo "chain.sh $before -> $after"; [ "$before" = "$after" ]
git log -1 --format='p41src %h %s' | cut -c1-120
sudo systemd-run --unit=p41-side --uid="$(id -un)" --working-directory="$P" --setenv=HOME="$HOME" -- /bin/bash $HOME/work/p41src/training/policy-v4.1-20261112/side.sh 2>&1 | tail -1
cat $P/logs/timeline.log; tail -1 $P/logs/buildA.log | cut -c1-100; date -u +%T
