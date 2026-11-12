# boxctl: timeout=300
# boxctl: timeout=300
# g8: turn the solver cache off for the Gen 8 queue on this box too (see 12-nocache on azure4: +20% boards an hour),
# then queue the multi-system match: the system-aware bot against the same engine without it, 2,880 deals bid
# beforehand at nine kinds of table (house, Precision and two over one in every pairing).
set -uo pipefail
G=$HOME/work/g8
grep -q '^export BRIDGE_DDS_CACHE=' "$G/queue.sh" || sed -i '0,/^cd "\$G\/src"/s//export BRIDGE_DDS_CACHE=\ncd "$G\/src"/' "$G/queue.sh"
grep -c 'BRIDGE_DDS_CACHE' "$G/queue.sh"
cat >> "$G/queue.txt" <<'Q'
@source 9f13a09304bc5bf9e45321da1515195847620f86
e4-8y-v-8p 8y-32~8p-32 0 2880 91 --book configs/gen8-books/mix91-2880.json.gz
Q
sudo systemctl restart g8-queue
sleep 100
tail -3 "$G/queue.log" | cut -c1-170
tail -2 "$G/runs/e4-8y-v-8p.log" 2>/dev/null | cut -c1-200
uptime | sed 's/.*load/load/'
