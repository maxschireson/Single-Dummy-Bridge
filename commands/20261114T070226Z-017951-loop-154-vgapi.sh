# boxctl: timeout=180
# boxctl: timeout=180
# loop session (read-only, a few requests): LoveBridge vugraph's archive API for one 2025 Senior USBC match (631412).
set -uo pipefail
D=$HOME/work/usbc/probe; cd $D
UA="Mozilla/5.0 (research; USBF records for bot evaluation)"
B=https://vugraph.lovebridge.com
get() { curl -sS -L -m 30 -A "$UA" -H "Accept: application/json" -o "$2" -w "%{http_code} %{size_download} %{content_type} $1\n" "$1"; }
get "$B/api/archive/boards/631412" boards.json; head -c 700 boards.json; echo
get "$B/api/archive/board/631412/1" board1.json; head -c 1800 board1.json; echo
get "$B/api/archive/rounds/631412" rounds.json; head -c 400 rounds.json; echo
get "$B/api/archive/miniSessions" ms.json; head -c 400 ms.json; echo
