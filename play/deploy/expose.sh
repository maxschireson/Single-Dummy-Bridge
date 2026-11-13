#!/usr/bin/env bash
# Open the play server to the internet: run on a box whose Azure CLI is signed in (azure1 as of 13 Nov 2026).
#
#   bash expose.sh VM_NAME DNS_LABEL          e.g. bash expose.sh Bridgebots sid-bridge
#
# Adds one inbound rule to the VM's network security group: TCP 80 and 443 from the internet, to that VM's
# private address only (the group is shared by every box; the others stay SSH-only). Sets a DNS label on the
# VM's public IP, giving <label>.<region>.cloudapp.azure.com, which caddy.sh needs for its certificate.
# Neither change costs money. Prints the host name, never an address.
#
# To undo:  az network nsg rule delete --ids <nsg id>/securityRules/sidplay-web
set -euo pipefail
VM=${1:?vm name}
LABEL=${2:?dns label}
RG=$(az vm list --query "[?name=='$VM'].resourceGroup | [0]" -o tsv)
[ -n "$RG" ] || { echo "no VM named $VM"; exit 1; }
NIC=$(az vm show -g "$RG" -n "$VM" --query "networkProfile.networkInterfaces[0].id" -o tsv)
PRIVATE=$(az network nic show --ids "$NIC" --query "ipConfigurations[0].privateIPAddress" -o tsv)
PIP=$(az network nic show --ids "$NIC" --query "ipConfigurations[0].publicIPAddress.id" -o tsv)
NSG=$(az network nic show --ids "$NIC" --query "networkSecurityGroup.id" -o tsv)
[ -n "$NSG" ] || NSG=$(az network vnet subnet show --ids "$(az network nic show --ids "$NIC" --query 'ipConfigurations[0].subnet.id' -o tsv)" --query networkSecurityGroup.id -o tsv)
NSG_RG=$(echo "$NSG" | cut -d/ -f5)
NSG_NAME=$(basename "$NSG")
az network nsg rule create -g "$NSG_RG" --nsg-name "$NSG_NAME" -n sidplay-web --priority 310 --direction Inbound \
  --access Allow --protocol Tcp --source-address-prefixes Internet --source-port-ranges '*' \
  --destination-address-prefixes "$PRIVATE" --destination-port-ranges 80 443 -o none
az network public-ip update --ids "$PIP" --dns-name "$LABEL" -o none
echo "rule sidplay-web on $NSG_NAME: TCP 80,443 from Internet to $VM only"
echo "fqdn $(az network public-ip show --ids "$PIP" --query dnsSettings.fqdn -o tsv)"
