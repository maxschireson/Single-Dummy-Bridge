# boxctl: timeout=180
# boxctl: timeout=180
# loop session (read-only): azure3's BEN lane config and a manifest of its BEN install, for setting BEN up on other boxes.
set -uo pipefail
cd "$HOME/work"; . lanes/1.env
echo "CONF-BEGIN"; gzip -9c "$BEN_CONF" | base64 -w 76; echo "CONF-END"
echo "ENV-BEGIN"; cat lanes/1.env; echo "ENV-END"
echo "FREEZE-SHA $(ben-venv/bin/pip freeze 2>/dev/null | sort | sha256sum | cut -c1-64)"
echo "FREEZE-BEGIN"; ben-venv/bin/pip freeze 2>/dev/null | sort; echo "FREEZE-END"
cd ben; echo "HEAD $(git rev-parse HEAD)"
echo "TREE-SHA $(git ls-files -z src bin models/TF2models | xargs -0 nice -n 10 sha256sum | sha256sum | cut -c1-64) files $(git ls-files src bin models/TF2models | wc -l)"
echo "MODELS-BEGIN"; grep -o -E "models/[A-Za-z0-9_./-]+\.keras" "$BEN_CONF" | sort -u | xargs nice -n 10 sha256sum; sha256sum bin/libdds.so; echo "MODELS-END"
du -sh --exclude=.git . 2>/dev/null | cut -f1; cat .gitattributes 2>/dev/null | head -3; ls -la models/TF2models | head -5
