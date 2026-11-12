# boxctl: timeout=60
echo "switch71: $(systemctl is-active switch71)"; tail -40 $HOME/work/lanes/switch71.log 2>/dev/null | cut -c1-420
