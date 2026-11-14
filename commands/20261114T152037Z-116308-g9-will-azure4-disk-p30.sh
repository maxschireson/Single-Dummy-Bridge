# boxctl: timeout=300
# boxctl: timeout=300
# will (Gen 9), on Max's word (14 Nov 15:19 UTC, after the 14:00 config recap): azure4's OS disk from performance
# tier P10 to P30 (same 128 GB disk, no downtime). One az call with this box's managed identity; nothing else on
# this box is touched.
set -e
RG=Bridgebots_group; DISK=Bridgebots4_OsDisk
az login --identity --output none
echo "== before"; az disk show -g $RG -n $DISK --query "{name:name, sku:sku.name, sizeGb:diskSizeGB, tier:tier, iops:diskIOPSReadWrite, mbps:diskMBpsReadWrite, bursting:burstingEnabled, state:diskState}" -o json
az disk update -g $RG -n $DISK --set tier=P30 --output none
echo "== after"; az disk show -g $RG -n $DISK --query "{name:name, sku:sku.name, sizeGb:diskSizeGB, tier:tier, iops:diskIOPSReadWrite, mbps:diskMBpsReadWrite, bursting:burstingEnabled, state:diskState}" -o json
