# boxctl: timeout=30
date -u +%T; tail -n 14 $HOME/work/lanes/prepf.log | cut -c1-230; echo "prepf $(systemctl is-active prepf)"
