# boxctl: timeout=300
# p41: update the scripts (chain.sh must be unchanged) and try the output push once, early, so the push path is known to work.
set -euo pipefail
cd ~/work/p41src
before=$(sha256sum training/policy-v4.1-20261112/chain.sh | cut -c1-16)
git fetch -q --depth 1 origin transfer/gen7-policy-v4.1-20261112 && git reset -q --hard FETCH_HEAD
after=$(sha256sum training/policy-v4.1-20261112/chain.sh | cut -c1-16); [ "$before" = "$after" ] && echo "chain.sh unchanged"
git log -1 --format='p41src %h %s' | cut -c1-120
bash training/policy-v4.1-20261112/push_results.sh 2>&1 | tail -6
tail -2 ~/work/p41/logs/buildA.log | cut -c1-120; date -u +%T
