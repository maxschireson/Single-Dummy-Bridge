# boxctl: timeout=60
# Read-only: progress of the move to deals v4.1 was not trained on.
date -u +%H:%M:%S; echo "go71c: $(systemctl is-active go71c); collector $(systemctl is-active arena-gen71); publisher $(systemctl is-active arena-gen71-publish)"
tail -22 $HOME/work/gen71/go71c.log | cut -c1-560
