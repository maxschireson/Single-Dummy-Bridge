# boxctl: timeout=60
# boxctl: timeout=60
P=$HOME/work/plan; ls -la $P/rnet2/data/ | awk '{print $5, $9}'; df -h $HOME | tail -1; wc -l < $P/runs/match2/results.jsonl
