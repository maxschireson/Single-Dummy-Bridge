# boxctl: timeout=60
echo "selfplay-trial: $(systemctl is-active selfplay-trial)"; tail -40 $HOME/work/selfplay/trial.log 2>/dev/null | cut -c1-420
