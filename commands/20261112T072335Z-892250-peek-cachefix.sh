# boxctl: timeout=60
date -u +%H:%M:%S; echo "cachefix $(systemctl is-active cachefix); collector $(systemctl is-active arena-gen71)"; tail -12 $HOME/work/gen71/cachefix.log | cut -c1-300
