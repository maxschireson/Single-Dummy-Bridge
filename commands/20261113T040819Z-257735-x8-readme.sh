# boxctl: timeout=60
sed -i "s#x1: 8xr0-ft1 at bb85066, seed 141 (paused at 246 boards, superseded by x3)#x1: 8xr0-ft1 at bb85066 on the same deals (paused at 246 boards; x3 replaces it at 5c77d79, whose random stream differs)#" $HOME/work/x8/publish.sh && grep -c "x3 replaces" $HOME/work/x8/publish.sh && sudo systemctl restart x8-publish && systemctl is-active x8-publish
