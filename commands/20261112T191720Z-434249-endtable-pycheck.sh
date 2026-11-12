# Ending table: can the box's Pythons run the T7 checks (sure.py imports the repository's bridge_harness)?
cd $HOME/work/endtable/src/experiments/sure_tricks
for py in python3 $HOME/work/venv/bin/python; do echo "== $py: $($py --version 2>&1)"; $py -c "import sure, csure; print('imports ok')" 2>&1 | tail -2; done
