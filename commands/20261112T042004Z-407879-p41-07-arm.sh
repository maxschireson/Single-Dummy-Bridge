# boxctl: timeout=120
# p41: update the scripts (chain.sh must be unchanged) and arm the two waiters: p41-after512 and p41-after768.
set -euo pipefail
P=$HOME/work/p41; cd ~/work/p41src
before=$(sha256sum training/policy-v4.1-20261112/chain.sh | cut -c1-16)
git fetch -q --depth 1 origin transfer/gen7-policy-v4.1-20261112 && git reset -q --hard FETCH_HEAD
after=$(sha256sum training/policy-v4.1-20261112/chain.sh | cut -c1-16); [ "$before" = "$after" ] && echo "chain.sh unchanged"
git log -1 --format='p41src %h %s' | cut -c1-120
for n in after512 after768; do
  sudo systemd-run --unit=p41-$n --uid="$(id -un)" --working-directory="$P" --setenv=HOME="$HOME" -- /bin/bash $HOME/work/p41src/training/policy-v4.1-20261112/$n.sh 2>&1 | tail -1
done
systemctl is-active p41-chain p41-side p41-after512 p41-after768 | tr '\n' ' '; echo
grep "shard" $P/logs/buildA.log | tail -1; cat $P/logs/timeline.log | tail -3; date -u +%T
