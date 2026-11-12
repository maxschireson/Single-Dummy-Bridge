# boxctl: timeout=60
sudo systemctl stop endtable-serve; systemctl is-active endtable-serve || true; ss -ltn | grep -c 8765 || true
