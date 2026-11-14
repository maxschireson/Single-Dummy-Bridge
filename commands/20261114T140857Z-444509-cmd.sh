# boxctl: timeout=600
# loop session: azure5 after its disk was full for 40 seconds (14:00:07 to 14:00:47 UTC, the first try at round 4): the
# collection the failed command restarted (sg8t1) wrote records while nothing could be written, and round 4's row build
# stopped on one of them. The collection stops; in every collection run of this box, a record written since 13:55 that does
# not read as gzip JSON is removed with its line in results.jsonl (the board is played again when the collection resumes),
# and results lines that do not parse are dropped. Then round 4 again as the unit loop-r4 (round4.sh).
set -euo pipefail
COMMIT=a470efe5aa65432e7357352680bdafa7010fdbb8
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
sudo systemctl stop loop-collect loop-collect-b loop-r4 2>/dev/null || true
pkill -u "$USER" -f "scripts/x8_match.py|round2.sh|gen7_build_dataset.py" 2>/dev/null || true; sleep 3
"$W/venv/bin/python" - "$W" <<'PY'
import glob, gzip, json, os, sys, time
W = sys.argv[1]
for run in sorted(glob.glob(f'{W}/runs/s[pg]*')):
    eps = f'{run}/episodes'
    if not os.path.isdir(eps):
        continue
    bad = set()
    for f in glob.glob(f'{eps}/*.json.gz'):
        if os.path.getmtime(f) < 1794664500:
            continue
        try:
            with gzip.open(f, 'rt') as h:
                d = json.load(h)
            assert isinstance(d, dict) and 'unique_tables' in d
        except Exception as e:
            bad.add(int(os.path.basename(f).split('.')[0]))
            os.remove(f)
    res = f'{run}/results.jsonl'
    kept, dropped = [], 0
    have = {int(f.split('.')[0]) for f in os.listdir(eps) if f.endswith('.json.gz')}
    if os.path.exists(res):
        for line in open(res, errors='replace'):
            try:
                r = json.loads(line)
                ok = r.get('index') in have        # a board without a readable record is played again
            except Exception:
                ok = False
            if ok:
                kept.append(line if line.endswith('\n') else line + '\n')
            else:
                dropped += 1
        if dropped:
            with open(res + '.tmp', 'w') as h:
                h.writelines(kept)
            os.replace(res + '.tmp', res)
    if bad or dropped:
        print(f'{os.path.basename(run)}: {len(bad)} unreadable records removed, {dropped} result lines dropped, {len(kept)} kept')
print('checked')
PY
python3 -c "import time; print(time.strftime('%FT%TZ', time.gmtime(1794664500)))"
df -h --output=avail "$HOME" | tail -1
git -C "$S" fetch -q --depth 12 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
echo "$(date -u +%FT%TZ) the disk was full from 14:00:07 to 14:00:47; records written then are removed (their boards are played again); round 4 again as loop-r4" >> "$W/runs.log"
sudo systemctl reset-failed loop-r4 2>/dev/null || true
sudo systemd-run --unit=loop-r4 --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$S/$T/round4.sh"
sleep 240; systemctl is-active loop-r4 loop-collect loop-publish | tr '\n' ' '; tail -n 4 "$W/r4go.log" | cut -c1-200; tail -n 3 "$W/r4/timeline.log" 2>/dev/null | cut -c1-200; date -u +%FT%TZ
