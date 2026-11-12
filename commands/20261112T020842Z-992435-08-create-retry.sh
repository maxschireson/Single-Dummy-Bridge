# boxctl: timeout=2400
# Create Bridgebots2-4 like azure1 (confirmed by Max 2026-11-12 02:06). Public IPs are not printed: this output is public.
set -uo pipefail
mask() { sed -E 's#[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}#<id>#g'; }
az login --identity --output none || exit 1
RG=Bridgebots_group; LOC=eastus
fam_used=$(az vm list-usage -l $LOC --query "[?contains(localName,'asv6 Family')].currentValue | [0]" -o tsv)
fam_limit=$(az vm list-usage -l $LOC --query "[?contains(localName,'asv6 Family')].limit | [0]" -o tsv)
reg_used=$(az vm list-usage -l $LOC --query "[?localName=='Total Regional vCPUs'].currentValue | [0]" -o tsv)
reg_limit=$(az vm list-usage -l $LOC --query "[?localName=='Total Regional vCPUs'].limit | [0]" -o tsv)
echo "quota: Fasv6 family $fam_used/$fam_limit, total regional $reg_used/$reg_limit"
if [ "$fam_limit" -lt $((fam_used + 24)) ] || [ "$reg_limit" -lt $((reg_used + 24)) ]; then echo "quota too low for 3 more 8-vCPU boxes; nothing created"; exit 1; fi
DISK=$(az vm show -g $RG -n Bridgebots --query "storageProfile.osDisk.name" -o tsv)
SIZE_GB=$(az disk show -g $RG -n "$DISK" --query diskSizeGB -o tsv)
DISK_SKU=$(az disk show -g $RG -n "$DISK" --query sku.name -o tsv)
ADMIN=$(az vm show -g $RG -n Bridgebots --query "osProfile.adminUsername" -o tsv)
SB=$(az vm show -g $RG -n Bridgebots --query "securityProfile.uefiSettings.secureBootEnabled" -o tsv)
VTPM=$(az vm show -g $RG -n Bridgebots --query "securityProfile.uefiSettings.vTpmEnabled" -o tsv)
echo "azure1: OS disk $SIZE_GB GB $DISK_SKU; admin user $ADMIN; secure boot $SB; vTPM $VTPM"
[ -n "$SIZE_GB" ] && [ -n "$DISK_SKU" ] && [ -n "$ADMIN" ] || { echo "could not read azure1 settings; nothing created"; exit 1; }
for i in 2 3 4; do
  NAME=Bridgebots$i
  if az vm show -g $RG -n $NAME --query name -o tsv >/dev/null 2>&1; then echo "== $NAME already exists"; continue; fi
  echo "== creating $NAME"
  az vm create -g $RG -n $NAME -l $LOC --zone 1 --size Standard_F8as_v6 \
    --image Canonical:ubuntu-24_04-lts:server:latest \
    --security-type TrustedLaunch --enable-secure-boot "${SB:-true}" --enable-vtpm "${VTPM:-true}" \
    --admin-username "$ADMIN" --ssh-key-name Bridgebots_key --authentication-type ssh \
    --vnet-name vnet-eastus-1 --subnet snet-eastus-1 --nsg Bridgebots-nsg \
    --public-ip-address "${NAME}-ip" --public-ip-sku Standard --public-ip-address-allocation static \
    --accelerated-networking true \
    --os-disk-name "${NAME}_OsDisk" --os-disk-size-gb "$SIZE_GB" --storage-sku "$DISK_SKU" \
    --nic-delete-option Delete --os-disk-delete-option Delete \
    --tags role=collector created-by=claude-via-azure1 \
    --query "{powerState:powerState, privateIp:privateIpAddress}" -o json > /tmp/create-$NAME.out 2>&1
  rc=$?; echo "exit $rc"
  grep -i -E "error|invalid|unrecognized|argument|conflict|quota|capacity|\"powerState\"|\"privateIp\"" /tmp/create-$NAME.out | grep -v -i "publicIp" | mask | head -8
  [ $rc -eq 0 ] || { echo "stopping after the first failure"; break; }
done
echo "== VMs in $RG"
az vm list -g $RG -d --query "[].{name:name, size:hardwareProfile.vmSize, state:powerState, privateIp:privateIps, zone:zones[0]}" -o table
echo "== quota after"; az vm list-usage -l $LOC --query "[?contains(localName,'asv6 Family') || localName=='Total Regional vCPUs'].{name:localName, used:currentValue, limit:limit}" -o table
