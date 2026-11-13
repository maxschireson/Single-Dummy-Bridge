# boxctl: timeout=120
W=$HOME/work/x8; PY=$HOME/work/venv/bin/python; for z in x4 x5 x6; do echo "== $z"; $PY $W/bin/x8_forks.py $W/runs/$z > /tmp/f_$z.txt 2>&1; sed -n 1,5p /tmp/f_$z.txt; grep -A3 "^  with mix\|^  with blend\|^  with claim\|^  with guarantee" /tmp/f_$z.txt | grep -v "doubled"; done
