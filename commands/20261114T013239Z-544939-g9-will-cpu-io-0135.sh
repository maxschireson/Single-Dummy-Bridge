# boxctl: timeout=60
vmstat 5 3; iostat -dx 5 2 2>/dev/null | tail -6; uptime
