# boxctl: timeout=30
date -u +%T; echo "go71e $(systemctl is-active go71e); mixswitch $(systemctl is-active mixswitch)"; tail -6 $HOME/work/gen71/go71e.log | cut -c1-300
