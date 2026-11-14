# boxctl: timeout=120
# boxctl: timeout=120
# loop session (read-only): the arena's BEN lanes on this box, if any.
set -uo pipefail
cd "$HOME/work"
ls lanes 2>/dev/null | tr '\n' ' ' | cut -c1-300; echo
for n in 1 2 8; do [ -e lanes/$n.env ] && ( . lanes/$n.env; echo "lane $n: port ${BEN_PORT:-} conf ${BEN_CONF:-} sha $(sha256sum "${BEN_CONF:-/dev/null}" 2>/dev/null | cut -c1-16)" ); done
ip netns list 2>/dev/null | tr '\n' ' '; echo
for n in 1 2 3 4 5 6 7 8; do printf '%s ' "$(systemctl is-active ben-server@$n 2>/dev/null || true)"; done; echo
systemctl list-units --all 'ben*' 'benlane*' 'arena*' 2>/dev/null | head -12 | cut -c1-120
git -C ben rev-parse --short HEAD 2>/dev/null; tail -n 4 "$HOME/work/loop/ben/install.log" 2>/dev/null | cut -c1-120; free -g | sed -n 2p
