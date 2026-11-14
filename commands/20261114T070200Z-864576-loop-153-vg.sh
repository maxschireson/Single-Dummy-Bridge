# boxctl: timeout=180
# boxctl: timeout=180
# loop session (read-only): the endpoints LoveBridge's vugraph app reads, from its script.
set -uo pipefail
D=$HOME/work/usbc/probe; cd $D
UA="Mozilla/5.0 (research; USBF records for bot evaluation)"
curl -sS -L -m 60 -A "$UA" -o vg.js "https://vugraph.lovebridge.com/assets/index-CWxikVER.js" -w "%{http_code} %{size_download}\n"
grep -o -E "\"[^\"]{0,40}(api|/rest|/v[0-9]/|ws:|wss:|https://[a-z0-9.-]+)[^\"]{0,100}\"" vg.js | sort -u | head -60
echo ----; grep -o -E "\`[^\`]{0,30}(api|/rest)[^\`]{0,120}\`" vg.js | sort -u | head -40
echo ----; grep -o -E "(baseURL|baseUrl|BASE_URL|apiUrl|API_URL)[^,;]{0,120}" vg.js | sort -u | head -20
