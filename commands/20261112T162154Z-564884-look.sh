# boxctl: timeout=60
# Read-only: azure6's state before the operator starts the Gen 8 arena there (g8's preflight, units, capsule, venv).
date -u +%T; echo "load $(cut -d' ' -f1-3 /proc/loadavg); memory available $(free -m | awk 'NR==2{print $7}') MB; disk free $(df -h $HOME | tail -1 | awk '{print $4}')"
echo "units: $(systemctl list-units --all --no-legend --plain 'g8-*' 'arena-*' 'go8*' 2>/dev/null | awk '{print $1 "=" $3 "/" $4}' | tr '\n' ' ')"
echo "top: $(ps -eo pcpu,etimes,args --sort=-pcpu --no-headers | head -3 | cut -c1-120 | tr '\n' '|')"
ls -d $HOME/work/* 2>/dev/null | sed "s|$HOME/work/||" | tr '\n' ' '; echo
C=$HOME/work/capsule-gen7-capture/recovery; [ -e $C/manifest.json ] && echo "capsule $(python3 -c "import json; print(json.load(open('$C/manifest.json'))['identity'][:12])") STOP $([ -e $C/STOP ] && echo y) WATCHDOG_STOP $([ -e $C/WATCHDOG_STOP ] && echo y) receipts $(ls $C/receipts 2>/dev/null | wc -l)"
[ -x $HOME/work/venv/bin/python ] && echo "venv: $($HOME/work/venv/bin/python -c 'import tensorflow, numpy; print(tensorflow.__version__, numpy.__version__)' 2>/dev/null)"
cat /etc/needrestart/conf.d/50-list-only.conf 2>/dev/null; nproc
