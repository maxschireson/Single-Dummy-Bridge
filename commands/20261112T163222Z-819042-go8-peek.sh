# boxctl: timeout=30
date -u +%T; echo "go8 $(systemctl is-active go8); arena-gen8 $(systemctl is-active arena-gen8)"; sed -n "/== preflight/,\$p" $HOME/work/gen8/go8.log | tail -14 | cut -c1-330; ps -eo pcpu,etimes,args --sort=-pcpu --no-headers | head -3 | cut -c1-140
