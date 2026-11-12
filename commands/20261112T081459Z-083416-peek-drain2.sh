# boxctl: timeout=60
date -u +%H:%M:%S; echo "drain2 $(systemctl is-active drain2)"; tail -8 $HOME/work/gen71/drain2.log | cut -c1-260
