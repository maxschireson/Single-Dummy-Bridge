# boxctl: timeout=100
python3 - <<EOF
import os, time, re
def snap():
    out = {}
    for p in os.listdir("/proc"):
        if not p.isdigit(): continue
        try:
            io = dict(l.split(": ") for l in open(f"/proc/{p}/io").read().splitlines())
            cmd = open(f"/proc/{p}/cmdline","rb").read().replace(b"\0", b" ").decode(errors="replace")[:110]
            out[p] = (int(io["write_bytes"]), int(io["syscw"]), cmd)
        except Exception: pass
    return out
a = snap(); time.sleep(20); b = snap()
rows = []
for p, (wb, sc, cmd) in b.items():
    if p in a: rows.append((wb - a[p][0], sc - a[p][1], p, cmd))
for wb, sc, p, cmd in sorted(rows, reverse=True)[:10]:
    print(f"{wb/1e6:8.1f} MB {sc:7d} writes  {p:>7} {cmd}")
EOF
