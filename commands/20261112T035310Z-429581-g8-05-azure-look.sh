# boxctl: timeout=600
# boxctl: timeout=600
# g8: look only, creates nothing. What exists in the resource group and whether there is quota for one more box of the
# same type (Max pre-authorized a sixth box for Gen 8 experiments, 12 Nov 03:50 UTC). No addresses or ids are printed.
set -uo pipefail
az login --identity --output none || { echo "az login --identity failed"; exit 1; }
RG=Bridgebots_group; LOC=eastus
echo "== VMs in $RG"
az vm list -g $RG -d --query "[].{name:name, size:hardwareProfile.vmSize, state:powerState, zone:zones[0], created:timeCreated}" -o table
echo "== quota"
az vm list-usage -l $LOC --query "[?contains(localName,'asv6 Family') || localName=='Total Regional vCPUs'].{name:localName, used:currentValue, limit:limit}" -o table
echo "== az version"; az version --query '"azure-cli"' -o tsv
echo "== flags"; az vm create --help 2>/dev/null | grep -E -o -- "--(public-ip-address-allocation|nic-delete-option|os-disk-delete-option|public-ip-sku|zone|ssh-key-name)\b" | sort -u | tr '\n' ' '; echo
az vm auto-shutdown --help >/dev/null 2>&1 && echo "auto-shutdown: available" || echo "auto-shutdown: not available"
