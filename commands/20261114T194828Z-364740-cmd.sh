# boxctl: timeout=200
# loop session: READ-ONLY. VMs and vCPU quota after Max's quota raise (19:47 UTC). Creates, changes and deletes nothing.
set -uo pipefail
mask() { sed -E 's#[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}#<id>#g'; }
az login --identity --output none 2>&1 | mask | head -2
az vm list -g Bridgebots_group -d --query "[].{name:name, size:hardwareProfile.vmSize, state:powerState}" -o table 2>&1 | mask
az vm list-usage -l eastus --query "[?localName=='Total Regional vCPUs' || contains(localName,'Fasv6') || contains(localName,'Famsv6')].{name:localName, used:currentValue, limit:limit}" -o table 2>&1 | mask
