# boxctl: timeout=120
# p41: update the scripts (running ones must be unchanged) and arm the last step as unit p41-final.
set -euo pipefail
P=$HOME/work/p41; cd ~/work/p41src; D=training/policy-v4.1-20261112
before=$(cat $D/chain.sh $D/after512.sh $D/after768.sh $D/side.sh $D/evalnet.sh | sha256sum | cut -c1-16)
git fetch -q --depth 1 origin transfer/gen7-policy-v4.1-20261112 && git reset -q --hard FETCH_HEAD
after=$(cat $D/chain.sh $D/after512.sh $D/after768.sh $D/side.sh $D/evalnet.sh | sha256sum | cut -c1-16); [ "$before" = "$after" ] && echo "running scripts unchanged"
git log -1 --format='p41src %h %s' | cut -c1-120
sudo systemd-run --unit=p41-final --uid="$(id -un)" --working-directory="$P" --setenv=HOME="$HOME" -- /bin/bash $HOME/work/p41src/$D/final_eval.sh 2>&1 | tail -1
systemctl is-active p41-chain p41-w768 p41-after512 p41-after768 p41-final | tr '\n' ' '; echo
tail -2 $P/logs/timeline.log; tail -1 $P/logs/w512.err; tail -1 $P/logs/w768.err; date -u +%T
