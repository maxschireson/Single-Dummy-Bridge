# boxctl: timeout=60
echo "selfplay-trial2: $(systemctl is-active selfplay-trial2)"; tail -45 $HOME/work/selfplay/trial2.log 2>/dev/null | cut -c1-520
