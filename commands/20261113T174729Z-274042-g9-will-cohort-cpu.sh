# boxctl: timeout=100
vmstat 5 4 | tail -4; top -b -n 2 -d 5 -o %CPU | awk "/^top -/{n++} n==2" | sed -n "7,22p" | cut -c1-120; du -sh ~/work/g9/runs/g9-cohort-azure4/publication/.git ~/work/g9/runs/g9-cohort-azure4/run/episodes 2>/dev/null; ls ~/work/g9/runs/g9-cohort-azure4/run/episodes | wc -l
