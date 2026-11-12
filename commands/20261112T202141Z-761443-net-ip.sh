# boxctl: timeout=60
# Ending-table copy: this box's private address and route, to see whether the boxes share a network (read only).
echo "host $(hostname) ip $(hostname -I) gw $(ip route | awk '/default/ {print $3; exit}')"
ls -la $HOME/work/endtable/tables 2>/dev/null | tail -n +2 || echo "no ~/work/endtable/tables"
