# boxctl: timeout=400
# boxctl: timeout=300
# plan session: read-only look at GPU quota and sizes in eastus (Max approved a GPU box for at most 4 hours, 13 Nov 00:25 UTC).
# Only `az ... list/show`; creates nothing. Ids are not printed.
set -uo pipefail
mask() { sed -E 's#[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}#<id>#g'; }
az login --identity --output none || exit 1
az vm list-usage -l eastus --query "[?contains(localName,'NC') || contains(localName,'NV') || contains(localName,'ND') || localName=='Total Regional vCPUs' || contains(localName,'asv6')].{name:localName, used:currentValue, limit:limit}" -o table 2>&1 | mask
echo "== T4 and A10 sizes offered in eastus (zones, restrictions)"
az vm list-skus -l eastus --resource-type virtualMachines --query "[?contains(name,'T4_v3') || contains(name,'A10_v5')].{name:name, zones:join(',',locationInfo[0].zones), restricted:length(restrictions)}" -o table 2>&1 | head -20
echo "== can this identity reach the quota API?"
az extension add -n quota --only-show-errors >/dev/null 2>&1; az quota show --resource-name standardNCASv3_T4Family --scope "/subscriptions/$(az account show --query id -o tsv)/providers/Microsoft.Compute/locations/eastus" --query "{limit:properties.limit.value, name:name}" -o json 2>&1 | mask | head -8
az vm list -g Bridgebots_group -d --query "[].{name:name, size:hardwareProfile.vmSize, state:powerState}" -o table
