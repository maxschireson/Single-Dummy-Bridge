# boxctl: timeout=60
# Read-only: is the capture capsule on this box, and how far along are the lanes' second pools.
W=$HOME/work
for d in $W/capsule-gen7-capture/recovery $W/capsule*/recovery $W/capsule*; do [ -e "$d/manifest.json" ] && echo "capsule: $d identity $(python3 -c "import json; print(json.load(open('$d/manifest.json'))['identity'][:12])") STOP $([ -e $d/STOP ] && echo y) WATCHDOG_STOP $([ -e $d/WATCHDOG_STOP ] && echo y)"; done
ls -d $W/*/ | sed "s|$W/||" | tr '\n' ' '; echo
for n in 1 2 3 4 5 6 7 8; do R=$(. $W/lanes/$n.env; echo $RUN); echo -n "lane $n: $(basename $R) $(ls $R/receipts | wc -l)/$(python3 -c "import json; print(json.load(open('$R/manifest.json'))['target'])"); "; done; echo
