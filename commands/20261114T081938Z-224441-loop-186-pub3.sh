# boxctl: timeout=120
# boxctl: timeout=120
W=$HOME/work/loop; D=$W/pub
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
git -C $D status -sb | head -2
git -C $D log --oneline -3 | cut -c1-80
timeout 90 git -C $D push origin HEAD 2>&1 | tail -5
