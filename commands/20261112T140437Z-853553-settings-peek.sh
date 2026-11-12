# boxctl: timeout=30
date -u +%T; echo "settings1 $(systemctl is-active settings1); match-m1 $(systemctl is-active match-m1); match-m3 $(systemctl is-active match-m3)"; tail -12 $HOME/work/settings/settings1.log | cut -c1-260
