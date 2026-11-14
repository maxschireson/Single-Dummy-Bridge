# boxctl: timeout=900
# loop session, on Max's word (14 Nov 19:00 UTC "Go!", after the 18:57 config recap): Bridgebots6 (azure6) is DEALLOCATED
# (stopped; its disk and data are kept; it can be started again) to free 8 vCPUs for azure5's resize. Through this box's
# managed identity. Nothing else is touched. No addresses, keys or ids are printed.
set -uo pipefail
mask() { sed -E 's#[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}#<id>#g'; }
az login --identity --output none 2>&1 | mask | head -2
RG=Bridgebots_group; LOC=eastus
echo "== retail prices, Linux pay as you go, $LOC (Azure's public price list)"
for s in Standard_F8as_v6 Standard_F16as_v6; do
  curl -s --max-time 30 "https://prices.azure.com/api/retail/prices?\$filter=armRegionName%20eq%20'$LOC'%20and%20armSkuName%20eq%20'$s'%20and%20priceType%20eq%20'Consumption'" | python3 -c "
import json, sys
try:
    items = json.load(sys.stdin).get('Items', [])
except Exception as e:
    print('$s: price list not read'); sys.exit(0)
for i in items:
    if 'Windows' in i.get('productName', '') or 'Spot' in i.get('skuName', '') or 'Low Priority' in i.get('skuName', ''): continue
    print('$s: %.4f USD an hour (%s, %s)' % (i['retailPrice'], i.get('productName'), i.get('unitOfMeasure')))
"
done
echo "== before"; az vm list -g $RG -d --query "[].{name:name, size:hardwareProfile.vmSize, state:powerState}" -o table 2>&1 | mask
az vm deallocate -g $RG -n Bridgebots6 2>&1 | mask | tail -3
echo "== after"; az vm list -g $RG -d --query "[?name=='Bridgebots6'].{name:name, size:hardwareProfile.vmSize, state:powerState}" -o table 2>&1 | mask
az vm list-usage -l $LOC --query "[?localName=='Total Regional vCPUs' || contains(localName,'Fasv6')].{name:localName, used:currentValue, limit:limit}" -o table 2>&1 | mask
date -u +%T
