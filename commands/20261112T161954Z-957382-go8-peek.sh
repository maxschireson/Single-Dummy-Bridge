# boxctl: timeout=30
date -u +%T; echo "go8 $(systemctl is-active go8)"; tail -8 $HOME/work/gen8/go8.log | cut -c1-300
