# boxctl: timeout=120
# boxctl: timeout=120
# sidplay (read-only): g7's Gen 8 units after the Caddy install, and the play server from its public name.
for u in arena-gen8 arena-gen8-publish next8 gen8-recycle sidplay caddy; do
  printf '%-20s %s since %s\n' $u "$(systemctl is-active $u)" "$(systemctl show $u -p ActiveEnterTimestamp --value)"
done
journalctl -u arena-gen8-publish --since "06:00" --no-pager | tail -5
curl -fsS https://play-sid.eastus.cloudapp.azure.com/api/health; echo
curl -sI http://play-sid.eastus.cloudapp.azure.com/ | head -3
