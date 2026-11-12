# boxctl: timeout=600
# azure2: record the diagnosed startup failure the way earlier launches did (resolved-failures/ with its resolution),
# then restart the unchanged frozen cohort.
set -euo pipefail
W=$HOME/work; PY=$W/venv/bin/python; RUN=$W/runs/gen7-phase1-$BOXCTL_BOX
[ "$(ls "$RUN/failures")" = "000000.json" ] || { echo "unexpected failure records: $(ls "$RUN/failures")"; exit 1; }
grep -q "database is locked" "$RUN/failures/000000.json" || { echo "not the diagnosed failure"; exit 1; }
[ -z "$(ls "$RUN/episodes")" ] && [ -z "$(ls "$RUN/receipts")" ] || { echo "records exist; not touching"; exit 1; }
systemctl is-active --quiet arena-gen7 && { echo "collector is running; not touching"; exit 1; }
echo "cache journal mode: $("$PY" -c "import sqlite3; db=sqlite3.connect('$RUN/dds-cache.sqlite', timeout=60); print(db.execute('PRAGMA journal_mode').fetchone()[0], '| tables', [r[0] for r in db.execute(\"select name from sqlite_master where type='table'\")])")"
mkdir -p "$RUN/resolved-failures"
mv "$RUN/failures/000000.json" "$RUN/resolved-failures/startup-000000.json"
"$PY" - "$RUN" <<'PYEOF'
import json, sys, time
json.dump(dict(epoch=time.time(), failure='startup-000000.json',
               reason="DDS cache startup race. The eight workers of a new run opened a dds-cache.sqlite that did not exist yet at the same moment, "
                      "and one got sqlite3.OperationalError('database is locked') on PRAGMA journal_mode=WAL while building its first player. "
                      "No board was played: there is no episode or receipt for any index. The cache file now exists in WAL mode, so the race cannot "
                      "recur in this run. Retried with the unchanged frozen manifest and bot identities."),
          open(sys.argv[1] + '/resolved-failures/startup-resolution-000000.json', 'w'), indent=1)
PYEOF
sudo systemctl reset-failed arena-gen7.service
sudo systemctl start arena-gen7.service
sleep 110
echo "collector: $(systemctl is-active arena-gen7); publisher: $(systemctl is-active arena-gen7-publish); failures: $(ls "$RUN/failures" | wc -l); boards $(ls "$RUN/receipts" | wc -l)"
tail -2 "$RUN.collector.log" | cut -c1-140
"$PY" -c "import json; s=json.load(open('$RUN/state.json')); print('state:', s['completed'], 'of', s['target'], s['by_pair'])"
