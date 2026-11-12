# boxctl: timeout=1800
# boxctl: timeout=1800
# g8: install the boxctl agent on Bridgebots6 (box name azure6) through Azure Run Command, reusing azure1's GitHub
# deploy key, exactly as command 09-agents did for Bridgebots2-4. The key is read here on azure1 and sent only to
# Azure; it is never printed and never in the repository.
set -uo pipefail
az login --identity --output none || exit 1
RG=Bridgebots_group; SHA=d5bb39f16ce65d36b899079dbdefee37f04ba852; U=bridgebots; NAME=Bridgebots6; BOX=azure6
az vm show -g $RG -n $NAME --query name -o tsv >/dev/null 2>&1 || { echo "$NAME does not exist"; exit 1; }
SCRIPT=$(mktemp)
{
  echo 'set -e'
  echo "U=$U"
  echo 'H=$(getent passwd "$U" | cut -d: -f6)'
  echo 'install -d -m 700 -o "$U" -g "$U" "$H/.ssh"'
  echo 'cat > "$H/.ssh/boxctl_github" <<"BOXCTLKEY"'; cat "$HOME/.ssh/boxctl_github"; echo 'BOXCTLKEY'
  echo 'cat > "$H/.ssh/boxctl_github.pub" <<"BOXCTLKEY"'; cat "$HOME/.ssh/boxctl_github.pub"; echo 'BOXCTLKEY'
  echo 'chown "$U:$U" "$H/.ssh/boxctl_github" "$H/.ssh/boxctl_github.pub"; chmod 600 "$H/.ssh/boxctl_github"'
  echo "sudo -u \"\$U\" -H bash -c 'cd ~ && curl -fsSL https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/$SHA/ops/boxctl/install.sh -o boxctl-install.sh && bash boxctl-install.sh $SHA $BOX' 2>&1 | grep -v -E 'ssh-ed25519' | tail -4"
  echo 'systemctl is-active boxctl'
} > "$SCRIPT"
echo "== $NAME as box $BOX"
az vm run-command invoke -g $RG -n $NAME --command-id RunShellScript --scripts @"$SCRIPT" --query "value[0].message" -o tsv 2>&1 | grep -v -E "^\s*$" | grep -v -E 'ssh-ed25519|PRIVATE KEY' | tail -10
rm -f "$SCRIPT"
