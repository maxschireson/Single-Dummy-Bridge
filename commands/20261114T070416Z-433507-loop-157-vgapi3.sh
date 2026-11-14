# boxctl: timeout=180
# boxctl: timeout=180
# loop session (read-only): a match's tables, and how the script reads one table's play (watch, score-card).
set -uo pipefail
D=$HOME/work/usbc/probe; cd $D
UA="Mozilla/5.0 (research; USBF records for bot evaluation)"; B=https://vugraph.lovebridge.com
M=usbc_397454_2_1
python3 -c "import json; u=[m for m in json.load(open('usbf_ms.json')) if m['miniSessionId']=='$M'][0]; print({k:u[k] for k in ('firstRound','numberOfRounds','firstBoard','boardsPerRound','segmentId','session','miniSession')})"
for r in 0 1 2 3 4; do curl -sS -m 30 -A "$UA" "$B/api/archive/tables/$M/$r" -o tb$r.json -w "%{http_code} %{size_download} tables/$r\n"; done
head -c 900 tb*.json | head -c 2500; echo
grep -o -E ".{200}/api/archive/watch/.{250}" vg.js | head -3
grep -o -E ".{150}/api/archive/(team-bidding-histories|score-card-bidding-histories)/.{150}" vg.js | head -2
