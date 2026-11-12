# boxctl: timeout=60
# Read-only: progress of the lanes' move to deals v4.1 was not trained on.
date -u +%H:%M:%S; echo "switch71f: $(systemctl is-active switch71f); lane-recycle $(systemctl is-active lane-recycle)"
for n in 1 2 3 4 5 6 7 8; do echo -n "lane $n: collector $(systemctl is-active arena-ben@$n) publisher $(systemctl is-active arena-ben-publish@$n) server $(systemctl is-active ben-server@$n); "; done; echo
tail -30 $HOME/work/lanes/switch71f.log | cut -c1-420
