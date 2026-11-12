# boxctl: timeout=30
tail -3 $HOME/work/gen71/share71.log | cut -c1-200; echo "share71 $(systemctl is-active share71); $(cat $HOME/work/gen71/workers.env); g8 matches: $(pgrep -fc scripts/gen8_match.py)"
