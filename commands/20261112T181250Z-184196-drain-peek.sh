# boxctl: timeout=30
date -u +%T; tail -5 $HOME/work/gen8/drain8.log | cut -c1-260; echo "drain8 $(systemctl is-active drain8)"
