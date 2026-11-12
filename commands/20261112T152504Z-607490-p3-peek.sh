# boxctl: timeout=30
date -u +%T; echo "prepnext3 $(systemctl is-active prepnext3)"; tail -14 $HOME/work/lanes/prepnext3.log | cut -c1-330
