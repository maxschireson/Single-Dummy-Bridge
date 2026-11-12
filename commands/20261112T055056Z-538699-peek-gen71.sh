# boxctl: timeout=60
echo "gen71-trial: $(systemctl is-active gen71-trial)"; tail -40 $HOME/work/gen71/trial.log 2>/dev/null | cut -c1-560
