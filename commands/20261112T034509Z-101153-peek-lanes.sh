# boxctl: timeout=60
echo "ben-lanes: $(systemctl is-active ben-lanes)"; cat $HOME/work/lanes/orchestrate.log 2>/dev/null | cut -c1-260 | tail -40
