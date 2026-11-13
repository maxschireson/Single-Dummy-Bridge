# boxctl: timeout=60
date -u +%T; uptime; for n in 1 6; do echo "== lane $n"; systemctl status arena-ben@$n --no-pager 2>&1 | sed -n 1,6p | cut -c1-200; systemctl status arena-ben-publish@$n --no-pager 2>&1 | sed -n 1,4p | cut -c1-200; systemctl status ben-server@$n --no-pager 2>&1 | sed -n 1,4p | cut -c1-160; tail -n 5 $HOME/work/lanes/$n.collector.log | cut -c1-220; done
echo "== lane-recycle"; tail -n 6 $HOME/work/lanes/recycle.log | cut -c1-200; echo "== laneswitch"; tail -n 3 $HOME/work/lanes/laneswitch.log | cut -c1-200
ls $HOME/work/lanes/ | grep -E "OFF|STOP" ; for n in 1 2; do . $HOME/work/lanes/$n.env; ls $RUN | grep -E "STOP|failures"; ls $RUN/failures | head -3; done
journalctl --since "-45min" --no-pager 2>/dev/null | grep -i -E "arena-ben|Stopped|reboot|systemd\[1\]: (Stopp|Start)" | tail -12 | cut -c1-220
