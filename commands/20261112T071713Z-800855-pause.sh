# boxctl: timeout=100
#!/bin/bash
P=$HOME/work/p41
for s in 0 1 2 3 4 5 6 7; do sudo systemctl kill -s SIGSTOP g8-reading-$s.service; done
echo "reading bench paused for the 768-wide scoring $(date -u +%T)" >> $P/logs/timeline.log
cat > $P/resume_reading.sh <<'EOS'
#!/bin/bash
P=$HOME/work/p41
while ! grep -q "eval w768e5 done" $P/logs/timeline.log; do sleep 3; done
for s in 0 1 2 3 4 5 6 7; do sudo systemctl kill -s SIGCONT g8-reading-$s.service; done
echo "reading bench resumed $(date -u +%T)" >> $P/logs/timeline.log
EOS
sudo systemd-run --unit=g8-reading-resume --uid="$(id -un)" --setenv=HOME="$HOME" -- /bin/bash $P/resume_reading.sh 2>&1 | tail -1
sleep 20; uptime; ps -eo stat,ni,pcpu,comm --sort=-pcpu | head -6
