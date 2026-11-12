# boxctl: timeout=900
# Azure CLI on azure1, then a read-only look: identity, role, quota, network, disk. Changes nothing in Azure.
# Output is public, so subscription, tenant and principal ids are masked.
mask() { sed -E 's#[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}#<id>#g'; }
if ! command -v az >/dev/null; then
  curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash >/tmp/az-install.log 2>&1 || { echo "Azure CLI install failed:"; tail -5 /tmp/az-install.log; exit 1; }
fi
echo "azure-cli $(az version --query '"azure-cli"' -o tsv 2>/dev/null)"
if ! az login --identity --output none 2>/tmp/az-login.err; then
  echo "== managed identity sign-in failed (identity probably not on yet):"; tail -3 /tmp/az-login.err | mask; exit 0
fi
echo "== signed in with the VM's managed identity"
RG=Bridgebots_group
echo "== resources in $RG"; az resource list -g $RG --query "[].{name:name,type:type,location:location}" -o table 2>&1 | mask
echo "== role assignments on $RG"; az role assignment list -g $RG --include-inherited --query "[].{role:roleDefinitionName,principal:principalName,type:principalType}" -o table 2>&1 | mask
echo "== the VM"; az vm show -g $RG -n Bridgebots --query "{size:hardwareProfile.vmSize, image:storageProfile.imageReference, osDiskGb:storageProfile.osDisk.diskSizeGb, osDiskSku:storageProfile.osDisk.managedDisk.storageAccountType, zones:zones, securityType:securityProfile.securityType, identity:identity.type, priority:priority}" -o json 2>&1 | mask
NIC=$(az vm show -g $RG -n Bridgebots --query "networkProfile.networkInterfaces[0].id" -o tsv 2>/dev/null)
if [ -n "$NIC" ]; then
  echo "== network"; az network nic show --ids "$NIC" --query "{nic:name, accelerated:enableAcceleratedNetworking, nsg:networkSecurityGroup.id, subnet:ipConfigurations[0].subnet.id}" -o json 2>&1 | sed -E 's#/subscriptions/[^"]*/##' | mask
  SUBNET=$(az network nic show --ids "$NIC" --query "ipConfigurations[0].subnet.id" -o tsv)
  az network vnet subnet show --ids "$SUBNET" --query "{subnet:name, prefix:addressPrefix, defaultOutboundAccess:defaultOutboundAccess, natGateway:natGateway.id, nsg:networkSecurityGroup.id}" -o json 2>&1 | sed -E 's#/subscriptions/[^"]*/##' | mask
fi
az network public-ip list -g $RG --query "[].{name:name, sku:sku.name, allocation:publicIPAllocationMethod, zones:zones}" -o table 2>&1 | mask
echo "== vCPU quota in eastus (used / limit)"
az vm list-usage -l eastus --query "[?contains(localName,'Total Regional') || contains(localName,'FASv6') || contains(localName,'Fasv6') || contains(localName,'Spot')].{name:localName, used:currentValue, limit:limit}" -o table 2>&1 | mask
echo "== F8as_v6 availability in eastus"
az vm list-skus -l eastus --size Standard_F8as_v6 --query "[].{name:name, zones:locationInfo[0].zones, restrictions:restrictions[].reasonCode}" -o json 2>&1 | mask
