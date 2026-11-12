# boxctl: timeout=30
date -u +%T; echo "go8 $(systemctl is-active go8); arena-gen8 $(systemctl is-active arena-gen8)"; tail -12 $HOME/work/gen8/go8.log | cut -c1-330
