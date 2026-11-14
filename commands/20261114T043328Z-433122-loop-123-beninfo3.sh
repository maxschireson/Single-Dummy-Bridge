# boxctl: timeout=120
# boxctl: timeout=120
# loop session (read-only): how BEN is installed on azure3, to see what a second BEN box would take (Max, 04:30 UTC:
# "We should run more Ben compare deals").
set -uo pipefail
cd "$HOME/work"
echo "--- lanes"; ls lanes | head -12; cat lanes/1.env 2>/dev/null
echo "--- ben checkout"; git -C ben log -1 --format='%H %cd %s' --date=short 2>/dev/null | cut -c1-140; git -C ben remote -v 2>/dev/null | head -2; git -C ben status --short 2>/dev/null | head -8
echo "--- sizes"; du -sh ben ben-venv 2>/dev/null; du -sh ben/models 2>/dev/null
echo "--- unit"; systemctl cat ben-server@1 2>/dev/null | grep -v '^#' | head -30
echo "--- venv"; ben-venv/bin/python --version; ben-venv/bin/pip freeze 2>/dev/null | grep -i -E "tensorflow|numpy|keras|onnx|torch|endplay|dds|scikit|protobuf|grpc|colorama|websockets|flask|bottle" | head -20; ben-venv/bin/pip freeze 2>/dev/null | wc -l
echo "--- conf"; . lanes/1.env; echo "$BEN_CONF"; grep -n -E "^\[|sample_hands_play|min_sample|model|\.keras|\.onnx|\.h5|lead|search_threshold|use_biddingquality|claim|double_dummy" "$BEN_CONF" | head -60
echo "--- netns"; ip netns list 2>/dev/null | head -3; nproc; free -g | sed -n 2p
