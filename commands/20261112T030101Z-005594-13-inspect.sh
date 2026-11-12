# boxctl: timeout=300
# Inspect the failed board on this box. Changes nothing.
RUN=$HOME/work/runs/gen7-phase1-$BOXCTL_BOX
echo "collector: $(systemctl is-active arena-gen7) ($(systemctl show arena-gen7 -p NRestarts --value) restarts); publisher: $(systemctl is-active arena-gen7-publish)"
echo "== failures"; ls -la "$RUN/failures"
for f in "$RUN"/failures/*.json; do echo "--- $f"; cut -c1-1500 "$f"; echo; done
echo "== receipts: $(ls "$RUN/receipts" | wc -l); episodes: $(ls "$RUN/episodes" | wc -l)"
echo "== collector log: first error"
grep -n -m1 -B2 -A45 -E "Traceback" "$RUN.collector.log" | grep -v -E "absl|oneDNN|cpu_feature|AVX|^[0-9]+-WARNING" | cut -c1-260 | head -80
echo "== log size and distinct errors"; wc -l "$RUN.collector.log"; grep -E "^[A-Za-z]+Error|^[A-Za-z.]+Exception|Error:" "$RUN.collector.log" | sort | uniq -c | head -10
free -g | head -2; df -h / | tail -1
