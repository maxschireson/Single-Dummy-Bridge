# boxctl: timeout=30
date -u +%T; echo "switch8 $(systemctl is-active switch8)"; grep -v "^   lane\|cohort " $HOME/work/lanes/switch8.log | tail -12 | cut -c1-330; grep "finished at" $HOME/work/lanes/switch8.log | tr "\n" " " | cut -c1-700; echo
