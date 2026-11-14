# boxctl: timeout=300
# loop session (Max, 18:53 UTC: "Can you decommission two of the existing boxes in favor of one larger to stay within our 48
# cpu quota?"): READ-ONLY inventory through this box's managed identity. Creates, changes and deletes nothing. No addresses,
# keys or ids are printed (ids masked).
set -uo pipefail
mask() { sed -E 's#[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}#<id>#g'; }
az login --identity --output none 2>&1 | mask | head -2 || { echo "az login --identity failed"; exit 1; }
RG=Bridgebots_group; LOC=eastus
echo "== VMs in $RG"
az vm list -g $RG -d --query "[].{name:name, size:hardwareProfile.vmSize, state:powerState, zone:zones[0], osDiskGB:storageProfile.osDisk.diskSizeGB, disk:storageProfile.osDisk.managedDisk.storageAccountType}" -o table 2>&1 | mask
echo "== vCPU quota in $LOC (used / limit), families with a limit or use"
az vm list-usage -l $LOC --query "[?localName=='Total Regional vCPUs' || contains(localName,'FASv6') || contains(localName,'Fasv6') || contains(localName,'FAMSv6') || contains(localName,'Famsv6') || contains(localName,'FALSv6') || contains(localName,'EASv6') || contains(localName,'Easv6') || contains(localName,'EASv7') || contains(localName,'DASv6') || contains(localName,'Dasv6')].{name:localName, used:currentValue, limit:limit}" -o table 2>&1 | mask
echo "== sizes Bridgebots5 could be resized to without moving (16 cores and more)"
az vm list-vm-resize-options -g $RG -n Bridgebots5 --query "[?numberOfCores>=\`16\` && numberOfCores<=\`32\`].{name:name, cores:numberOfCores, memoryGB:memoryInMB}" -o table 2>&1 | mask | grep -E "name|---|F16|F32|E16|D16|FX" | head -24
echo "== 16-core sizes of the F and E v6 AMD families in $LOC, zone 1"
az vm list-skus -l $LOC --resource-type virtualMachines --query "[?name=='Standard_F16as_v6' || name=='Standard_F16ams_v6' || name=='Standard_E16as_v6' || name=='Standard_F32as_v6'].{name:name, zones:locationInfo[0].zones | join(',', @), restricted:restrictions[0].reasonCode}" -o table 2>&1 | mask
echo "== disks"
az disk list -g $RG --query "[].{name:name, GB:diskSizeGB, sku:sku.name, tier:tier, state:diskState}" -o table 2>&1 | mask
date -u +%T
