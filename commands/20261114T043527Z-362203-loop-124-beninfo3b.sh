# boxctl: timeout=120
# boxctl: timeout=120
# loop session (read-only): what BEN needs beyond its checkout and its Python packages on azure3.
set -uo pipefail
cd "$HOME/work"
echo "--- system packages"; dpkg -l 2>/dev/null | grep -i -E "mono-|dotnet|libboost-thread|libgomp|libdds" | awk '{print $2, $3}' | head -20; which dotnet mono 2>/dev/null
echo "--- ignored or untracked in ben"; git -C ben status --short --ignored 2>/dev/null | head -20; cat ben/.gitattributes 2>/dev/null | head -5
echo "--- conf pimc and dds"; . lanes/1.env; sed -n '/^\[pimc\]/,/^\[sampling\]/p' "$BEN_CONF" | grep -v '^#' | grep -v '^$' | head -40; sed -n '/^\[dds\]/,$p' "$BEN_CONF" | grep -v '^#' | grep -v '^$' | head -12
echo "--- server start log"; grep -v -E "^\s*$" "$HOME/work/loop/ben/ben200-1.log" 2>/dev/null | head -60 | cut -c1-180
echo "--- conf sha"; sha256sum "$BEN_CONF" "$HOME/work/loop/ben/ben-200-1.conf" | cut -c1-80; diff "$BEN_CONF" "$HOME/work/loop/ben/ben-200-1.conf" | head; for n in 1 2 8; do . lanes/$n.env; sha256sum "$BEN_CONF" | cut -c1-16; done
echo "--- ben bin"; ls ben/bin | head -30; python3 --version
