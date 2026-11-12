# boxctl: timeout=30
date -u +%T; echo "go8 $(systemctl is-active go8); arena-gen8 $(systemctl is-active arena-gen8)"; sed -n "/== preflight/,\$p" $HOME/work/gen8/go8.log | tail -12 | cut -c1-360
