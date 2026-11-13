# boxctl: timeout=30
date -u +%T; tail -n 5 $HOME/work/gen8x/setup.log | cut -c1-230; echo "setup8x $(systemctl is-active setup8x)"
