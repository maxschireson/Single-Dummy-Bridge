# boxctl: timeout=2400
# boxctl: timeout=2400
# g8: create Bridgebots6 like azure1, for Gen 8 experiments. Max pre-authorized a sixth box of similar spec for up to
# 6 hours of runtime (12 Nov 03:50 UTC). Same recipe as Bridgebots2-4 (command 08-create-retry2). The box is stopped
# (deallocated) six hours after creation by an Azure auto-shutdown schedule and, as a second guard, by a timer on azure1.
# Public addresses and ids are not printed: this output is public.
set -uo pipefail
mask() { sed -E 's#[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}#<id>#g'; }
az login --identity --output none || exit 1
RG=Bridgebots_group; LOC=eastus; NAME=Bridgebots6
fam_used=$(az vm list-usage -l $LOC --query "[?contains(localName,'asv6 Family')].currentValue | [0]" -o tsv)
fam_limit=$(az vm list-usage -l $LOC --query "[?contains(localName,'asv6 Family')].limit | [0]" -o tsv)
reg_used=$(az vm list-usage -l $LOC --query "[?localName=='Total Regional vCPUs'].currentValue | [0]" -o tsv)
reg_limit=$(az vm list-usage -l $LOC --query "[?localName=='Total Regional vCPUs'].limit | [0]" -o tsv)
echo "quota: Fasv6 family $fam_used/$fam_limit, total regional $reg_used/$reg_limit"
count=$(az vm list -g $RG --query "length(@)" -o tsv)
echo "VMs in the group now: $count"
[ "$count" -le 5 ] || { echo "there are already more than five VMs; nothing created"; exit 1; }
if az vm show -g $RG -n $NAME --query name -o tsv >/dev/null 2>&1; then echo "$NAME already exists; nothing created"; exit 1; fi
if [ "$fam_limit" -lt $((fam_used + 8)) ] || [ "$reg_limit" -lt $((reg_used + 8)) ]; then echo "quota too low for one more 8-vCPU box; nothing created"; exit 1; fi
DISK=$(az vm show -g $RG -n Bridgebots --query "storageProfile.osDisk.name" -o tsv)
SIZE_GB=$(az disk show -g $RG -n "$DISK" --query diskSizeGB -o tsv)
DISK_SKU=$(az disk show -g $RG -n "$DISK" --query sku.name -o tsv)
ADMIN=$(az vm show -g $RG -n Bridgebots --query "osProfile.adminUsername" -o tsv | tr "A-Z" "a-z")
SB=$(az vm show -g $RG -n Bridgebots --query "securityProfile.uefiSettings.secureBootEnabled" -o tsv)
VTPM=$(az vm show -g $RG -n Bridgebots --query "securityProfile.uefiSettings.vTpmEnabled" -o tsv)
echo "azure1: OS disk $SIZE_GB GB $DISK_SKU; admin user $ADMIN; secure boot $SB; vTPM $VTPM"
[ -n "$SIZE_GB" ] && [ -n "$DISK_SKU" ] && [ -n "$ADMIN" ] || { echo "could not read azure1 settings; nothing created"; exit 1; }
echo "== creating $NAME at $(date -u +%FT%TZ)"
az vm create -g $RG -n $NAME -l $LOC --zone 1 --size Standard_F8as_v6 \
  --image Canonical:ubuntu-24_04-lts:server:latest \
  --security-type TrustedLaunch --enable-secure-boot "${SB:-true}" --enable-vtpm "${VTPM:-true}" \
  --admin-username "$ADMIN" --ssh-key-name Bridgebots_key --authentication-type ssh \
  --vnet-name vnet-eastus-1 --subnet snet-eastus-1 --nsg Bridgebots-nsg \
  --public-ip-address "${NAME}-ip" --public-ip-sku Standard --public-ip-address-allocation static \
  --accelerated-networking true \
  --os-disk-name "${NAME}_OsDisk" --os-disk-size-gb "$SIZE_GB" --storage-sku "$DISK_SKU" \
  --nic-delete-option Delete --os-disk-delete-option Delete \
  --tags role=gen8-experiments created-by=claude-g8-via-azure1 max-runtime=6h \
  --query "{powerState:powerState}" -o json > /tmp/create-$NAME.out 2>&1
rc=$?; echo "exit $rc"
grep -i -E "error|invalid|unrecognized|argument|conflict|quota|capacity|\"powerState\"" /tmp/create-$NAME.out | grep -v -i "publicIp" | mask | head -8
[ $rc -eq 0 ] || { echo "creation failed; no guard set"; exit 1; }
# guard 1: Azure's own daily auto-shutdown (deallocates), at creation + 6 hours, UTC
STOP=$(date -u -d '+6 hours' +%H%M)
az vm auto-shutdown -g $RG -n $NAME --time "$STOP" --query "{status:status, time:dailyRecurrence.time, zone:timeZoneId}" -o json 2>&1 | mask | tr -d '\n'; echo
# guard 2: a timer on this box that deallocates it 6 hours 5 minutes from now
sudo systemctl stop g8-azure6-deallocate.timer 2>/dev/null; sudo systemctl reset-failed g8-azure6-deallocate.service 2>/dev/null
sudo systemd-run --quiet --unit=g8-azure6-deallocate --on-active=6h5m --uid="$(id -un)" --setenv=HOME="$HOME" \
  -- bash -lc "az login --identity --output none && az vm deallocate -g $RG -n $NAME"
systemctl list-timers g8-azure6-deallocate.timer --no-pager 2>/dev/null | sed -n 2p | cut -c1-110
echo "== VMs in $RG"
az vm list -g $RG -d --query "[].{name:name, size:hardwareProfile.vmSize, state:powerState, zone:zones[0]}" -o table
echo "== quota after"; az vm list-usage -l $LOC --query "[?contains(localName,'asv6 Family') || localName=='Total Regional vCPUs'].{name:localName, used:currentValue, limit:limit}" -o table
