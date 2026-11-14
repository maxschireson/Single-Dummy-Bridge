# boxctl: timeout=1800
# loop session, on Max's word (14 Nov 19:00 UTC "Go!", after the 18:57 config recap): Bridgebots5 (azure5) is resized in
# place from Standard_F8as_v6 to Standard_F16as_v6 (16 vCPU, 64 GB; same disk, same data). Bridgebots6 was deallocated at
# 19:06 to free the 8 vCPUs. Through this box's managed identity. If the resize fails the box is started again as it was.
# No addresses, keys or ids are printed.
set -uo pipefail
mask() { sed -E 's#[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}#<id>#g'; }
az login --identity --output none 2>&1 | mask | head -2
RG=Bridgebots_group; LOC=eastus; NAME=Bridgebots5; SIZE=Standard_F16as_v6
used() { az vm list-usage -l $LOC --query "[?localName=='Total Regional vCPUs'].currentValue | [0]" -o tsv; }
echo "$(date -u +%T) regional vCPUs in use: $(used) of 48"
echo "== deallocate $NAME"; az vm deallocate -g $RG -n $NAME 2>&1 | mask | tail -2
az vm list -g $RG -d --query "[?name=='$NAME'].{name:name, size:hardwareProfile.vmSize, state:powerState}" -o table 2>&1 | mask | tail -1
echo "== resize to $SIZE"
ok=0
for try in 1 2 3 4 5 6; do
  if az vm resize -g $RG -n $NAME --size $SIZE --output none 2> /tmp/resize.err; then ok=1; break; fi
  echo "$(date -u +%T) try $try: $(mask < /tmp/resize.err | tr '\n' ' ' | cut -c1-300)"; echo "   regional vCPUs in use: $(used)"; sleep 60
done
[ $ok -eq 1 ] && echo "resized" || echo "RESIZE FAILED: starting the box as it was"
echo "== start"; az vm start -g $RG -n $NAME 2>&1 | mask | tail -2
az vm list -g $RG -d --query "[].{name:name, size:hardwareProfile.vmSize, state:powerState}" -o table 2>&1 | mask
az vm list-usage -l $LOC --query "[?localName=='Total Regional vCPUs' || contains(localName,'Fasv6')].{name:localName, used:currentValue, limit:limit}" -o table 2>&1 | mask
date -u +%T
