# boxctl: timeout=120
# loop session (Max, 15:39 UTC: no clear gain from the human boards inside the bot, no human boards; 15:50: "I kinda like
# the idea of being trained only on bots"): R4 vs its control inside the rollout bot is -0.10 +- 0.17 (500 deals), so the
# gate's remaining stu4 blocks (c, d, e) are dropped and azure3 plays the control alone. The running chain reads its job
# file line by line from an open descriptor, so the three lines are commented in place (same length: 'b' -> '#'), and a
# note is appended; nothing else in the file moves.
set -euo pipefail
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113; F=$S/$T/jobs-azure3-ben8.txt
python3 - "$F" <<'PY'
import sys
p = sys.argv[1]
with open(p, 'r+b') as f:
    data = f.read()
    off = 0
    for line in data.split(b'\n'):
        if line.startswith((b'bu4-pst200c ', b'bu4-pst200d ', b'bu4-pst200e ')):
            f.seek(off); f.write(b'#')
        off += len(line) + 1
    f.seek(0, 2)
    if not data.endswith(b'\n'):
        f.write(b'\n')
    f.write(b"# 16:40 UTC: stu4's blocks c to e dropped (Max's rule for the human tables; stu4 vs stu4c inside the bot -0.10 +- 0.17)\n")
PY
grep -n "" "$F" | tail -8
tail -n 1 "$W/runs.log" | cut -c1-140; for r in bu4c-pst200a bu4c-pst200b; do printf '%s: %s | ' $r "$(cat "$W"/runs/$r-[1-8]/results.jsonl 2>/dev/null | wc -l)"; done; echo; date -u +%T
