# boxctl: timeout=1500
# boxctl: timeout=1500
# loop session: two boards of pure Stu against BEN (64) in lane 1 (the arena's idle server and namespace), beside the
# ladder, to test the path. The checkout changes gen8_match.py (an option), the bots' names and adds files; the chain's
# scripts and job file are untouched except chain.sh, which gains an optional argument: the chain is restarted on it
# after its job in hand is stopped (boards kept).
set -euo pipefail
COMMIT=bc4b3af595f0774a9c20500f27fe22158dacb303
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
sudo systemctl stop loop-chain || true
tail -n 1 "$W/runs.log" | cut -c1-140
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-100
sudo systemctl reset-failed loop-chain 2>/dev/null || true
sudo systemd-run --unit=loop-chain --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure3.txt"
systemctl is-active ben-server@1 | tr '\n' ' '; sudo ip netns exec benlane-1 curl -s -m 5 -o /dev/null -w 'ben server http %{http_code}\n' http://127.0.0.1:8089/ || echo "no answer from the server"
rm -rf "$W/runs/pf-ben-1" "$W/runs/pf-ben-1.log"; t0=$(date +%s)
timeout 1200 bash "$T/ben.sh" pf-ben stu0-p~ben64 9000 0 2 1 --episodes && echo "ben.sh exit 0" || echo "ben.sh exit $?"
echo "$(( $(date +%s) - t0 )) s wall"
tail -n 4 "$W/runs/pf-ben-1.log" | cut -c1-300
"$W/venv/bin/python" - <<'PY'
import glob, gzip, json, os
W = os.path.expanduser('~/work/loop/runs/pf-ben-1')
rows = [json.loads(l) for l in open(W + '/results.jsonl')]
for r in rows:
    print({k: r.get(k) for k in ('index', 'common', 'native', 'tables', 'cpu', 'contract')}, {k: (r['search']['candidate'].get('x8') or {}).get(k) for k in ('rollout', 'claim', 'moved')})
for f in sorted(glob.glob(W + '/episodes/*')):
    d = json.load(gzip.open(f, 'rt'))
    for key, e in d['unique_tables'].items():
        acts = e['tables'][0]['actions']
        who = {a['player'] for a in acts}
        secs = {p: round(sum(a.get('seconds', 0) for a in acts if a['player'] == p), 1) for p in who}
        print(key, e['assignments'], 'actions', len(acts), 'seconds by player', secs, 'opponent action keys', sorted(next((a for a in acts if a['player'] == 'opponent'), {}).keys())[:12])
m = json.load(open(W + '/manifest.json'))
print('common_only', m.get('common_only'), '| bots', {k: (v.get('engine'), v.get('url')) for k, v in m['bots'].items()}, '| names', m['bots']['stu0-p']['x8']['names'])
PY
rm -rf "$W/runs/pf-ben-1" "$W/runs/pf-ben-1.log"
systemctl is-active loop-chain loop-publish | tr '\n' ' '; tail -n 2 "$W/runs.log" | cut -c1-140; date -u +%FT%TZ
