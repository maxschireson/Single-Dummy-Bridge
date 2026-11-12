# boxctl: timeout=60
echo "go71b: $(systemctl is-active go71b); gen71-trial: $(systemctl is-active gen71-trial)"; tail -12 $HOME/work/gen71/trial.log 2>/dev/null | cut -c1-900; echo ---; tail -34 $HOME/work/gen71/go71b.log 2>/dev/null | cut -c1-520
