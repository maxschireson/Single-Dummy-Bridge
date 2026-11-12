# boxctl: timeout=120
# Every run folder on this box: cohort, deals, boards played, STOP/WATCHDOG_STOP, exclusions, and the source cohort it took deals from.
W=$HOME/work
"$W/venv/bin/python" - "$W" <<'PY'
import glob, json, os, sys
w = sys.argv[1]
for run in sorted(glob.glob(w + '/runs/*')):
    try: m = json.load(open(run + '/manifest.json'))
    except Exception: continue
    n = len(glob.glob(run + '/receipts/*.json'))
    src = (m.get('source') or m.get('takeover') or {})
    src = src.get('identity', '')[:12] if isinstance(src, dict) else str(src)[:40]
    print(os.path.basename(run), m['identity'][:12], m.get('target'), n, 'STOP' if os.path.exists(run + '/STOP') else '-', 'WD' if os.path.exists(run + '/WATCHDOG_STOP') else '-',
          len(os.listdir(run + '/failures')) if os.path.isdir(run + '/failures') else 'nofail', (m.get('evaluation_exclusions') or {}).get('sha256', '')[:8], src, sep=' | ')
PY
