# boxctl: timeout=2400
# Temporary training box Bridgebots5 (box azure5). Authorized by Max 2026-11-12 03:40 UTC: a fifth
# box for training Gen 7 policy net 4.1, at most 2 hours up, then deleted. Same size and settings as
# azure1-4. This creates it, installs the boxctl agent on it, and arms a timer HERE that deletes it
# 110 minutes after creation. It touches nothing else on azure1. Public IPs and keys are not printed.
set -uo pipefail
mask() { sed -E 's#[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}#<id>#g'; }
az login --identity --output none || exit 1
RG=Bridgebots_group; LOC=eastus; NAME=Bridgebots5; BOX=azure5; SIZE=Standard_F8as_v6; NEED=8
if az vm show -g $RG -n $NAME --query name -o tsv >/dev/null 2>&1; then echo "$NAME already exists; nothing done"; exit 1; fi

# Quota: Max raised it at 03:44 UTC. Wait up to 8 minutes for the new limit to show.
ok=0
for try in $(seq 1 17); do
  fam_used=$(az vm list-usage -l $LOC --query "[?contains(localName,'Fasv6 Family')].currentValue | [0]" -o tsv)
  fam_limit=$(az vm list-usage -l $LOC --query "[?contains(localName,'Fasv6 Family')].limit | [0]" -o tsv)
  reg_used=$(az vm list-usage -l $LOC --query "[?localName=='Total Regional vCPUs'].currentValue | [0]" -o tsv)
  reg_limit=$(az vm list-usage -l $LOC --query "[?localName=='Total Regional vCPUs'].limit | [0]" -o tsv)
  echo "$(date -u +%H:%M:%S) quota in $LOC: Fasv6 family $fam_used/$fam_limit, total regional $reg_used/$reg_limit"
  if [ "${fam_limit:-0}" -ge $((${fam_used:-0} + NEED)) ] && [ "${reg_limit:-0}" -ge $((${reg_used:-0} + NEED)) ]; then ok=1; break; fi
  sleep 30
done
[ $ok -eq 1 ] || { echo "quota still too low for one more $SIZE in $LOC; nothing created"; exit 1; }

DISK=$(az vm show -g $RG -n Bridgebots --query "storageProfile.osDisk.name" -o tsv)
SIZE_GB=$(az disk show -g $RG -n "$DISK" --query diskSizeGB -o tsv)
DISK_SKU=$(az disk show -g $RG -n "$DISK" --query sku.name -o tsv)
[ -n "$SIZE_GB" ] && [ -n "$DISK_SKU" ] || { echo "could not read azure1's disk settings; nothing created"; exit 1; }
echo "like azure1: $SIZE, OS disk $SIZE_GB GB $DISK_SKU, zone 1, same network and security group"

# The reaper first, so that it exists whatever happens after the create call.
cat > "$HOME/azure5-reaper.sh" <<'REAPER'
#!/bin/bash
# Deletes the temporary training box Bridgebots5 and what was created with it. Safe to run twice.
RG=Bridgebots_group; NAME=Bridgebots5
az login --identity --output none || exit 1
{ az vm delete -g $RG -n $NAME --yes --force-deletion true || az vm delete -g $RG -n $NAME --yes; } 2>&1 | grep -v -E "^\s*$" | tail -3
for i in 1 2 3 4 5 6; do az network public-ip delete -g $RG -n ${NAME}-ip 2>/dev/null && break; sleep 10; done
az network nic delete -g $RG -n ${NAME}VMNic 2>/dev/null
az disk delete -g $RG -n ${NAME}_OsDisk --yes 2>/dev/null
az resource delete -g $RG -n shutdown-computevm-$NAME --resource-type Microsoft.DevTestLab/schedules 2>/dev/null
echo "left in $RG with $NAME in the name:"
az resource list -g $RG --query "[?contains(name,'$NAME')].{name:name,type:type}" -o table
echo "(end of list)"
REAPER
chmod +x "$HOME/azure5-reaper.sh"

T0=$(date -u +%s)
echo "== creating $NAME at $(date -u -d @$T0 +%H:%M:%S) UTC"
az vm create -g $RG -n $NAME -l $LOC --zone 1 --size $SIZE \
  --image Canonical:ubuntu-24_04-lts:server:latest \
  --security-type TrustedLaunch --enable-secure-boot true --enable-vtpm true \
  --admin-username bridgebots --ssh-key-name Bridgebots_key --authentication-type ssh \
  --vnet-name vnet-eastus-1 --subnet snet-eastus-1 --nsg Bridgebots-nsg \
  --public-ip-address "${NAME}-ip" --public-ip-sku Standard --public-ip-address-allocation static \
  --accelerated-networking true \
  --os-disk-name "${NAME}_OsDisk" --os-disk-size-gb "$SIZE_GB" --storage-sku "$DISK_SKU" \
  --nic-delete-option Delete --os-disk-delete-option Delete \
  --tags role=training temporary=true created-by=claude-via-azure1 \
  --query "{powerState:powerState, privateIp:privateIpAddress}" -o json > /tmp/create-$NAME.out 2>&1
rc=$?; echo "create exit $rc"
grep -i -E "error|invalid|unrecognized|argument|conflict|quota|capacity|\"powerState\"|\"privateIp\"" /tmp/create-$NAME.out | grep -v -i "publicIp" | mask | head -8

# Dead-man timer on azure1: delete the box 110 minutes after the create call, whatever else happens.
sudo systemctl stop azure5-reaper.timer 2>/dev/null; sudo systemctl reset-failed azure5-reaper.service 2>/dev/null
sudo systemd-run --unit=azure5-reaper --on-active=6600 --uid="$(id -un)" --setenv=HOME="$HOME" /bin/bash "$HOME/azure5-reaper.sh" 2>&1 | tail -2
systemctl list-timers azure5-reaper.timer --no-pager 2>&1 | sed -n '1,3p'
[ $rc -eq 0 ] || { echo "create failed; running the reaper now to remove anything half-made"; sudo systemctl stop azure5-reaper.timer; bash "$HOME/azure5-reaper.sh"; exit 1; }

# Second net, on Azure's side: deallocate at T0 + 115 minutes (best effort; needs the DevTestLab provider).
HHMM=$(date -u -d @$((T0 + 6900)) +%H%M)
if az vm auto-shutdown -g $RG -n $NAME --time $HHMM --output none 2>/tmp/autoshutdown.err; then echo "Azure auto-shutdown set for $HHMM UTC"; else echo "Azure auto-shutdown not set: $(tail -1 /tmp/autoshutdown.err | mask | cut -c1-200)"; fi

# The boxctl agent, reusing azure1's GitHub deploy key (read here, sent only to Azure, never printed).
SHA=d5bb39f16ce65d36b899079dbdefee37f04ba852; U=bridgebots; SCRIPT=$(mktemp)
{
  echo 'set -e'
  echo "U=$U"
  echo 'H=$(getent passwd "$U" | cut -d: -f6)'
  echo 'install -d -m 700 -o "$U" -g "$U" "$H/.ssh"'
  echo 'cat > "$H/.ssh/boxctl_github" <<"BOXCTLKEY"'; cat "$HOME/.ssh/boxctl_github"; echo 'BOXCTLKEY'
  echo 'cat > "$H/.ssh/boxctl_github.pub" <<"BOXCTLKEY"'; cat "$HOME/.ssh/boxctl_github.pub"; echo 'BOXCTLKEY'
  echo 'chown "$U:$U" "$H/.ssh/boxctl_github" "$H/.ssh/boxctl_github.pub"; chmod 600 "$H/.ssh/boxctl_github"'
  echo "sudo -u \"\$U\" -H bash -c 'cd ~ && curl -fsSL https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/$SHA/ops/boxctl/install.sh -o boxctl-install.sh && bash boxctl-install.sh $SHA $BOX' 2>&1 | grep -v -E 'ssh-ed25519' | tail -3"
  echo 'systemctl is-active boxctl'
} > "$SCRIPT"
echo "== agent on $NAME as box $BOX"
az vm run-command invoke -g $RG -n $NAME --command-id RunShellScript --scripts @"$SCRIPT" --query "value[0].message" -o tsv 2>&1 | grep -v -E "^\s*$" | tail -8
rm -f "$SCRIPT"

echo "== VMs in $RG"
az vm list -g $RG -d --query "[].{name:name, size:hardwareProfile.vmSize, state:powerState, zone:zones[0]}" -o table
echo "== quota after"; az vm list-usage -l $LOC --query "[?contains(localName,'Fasv6 Family') || localName=='Total Regional vCPUs'].{name:localName, used:currentValue, limit:limit}" -o table
echo "created_epoch=$T0 created_utc=$(date -u -d @$T0 +%H:%M:%S) reaper_at_utc=$(date -u -d @$((T0 + 6600)) +%H:%M:%S) cap_utc=$(date -u -d @$((T0 + 7200)) +%H:%M:%S)"
