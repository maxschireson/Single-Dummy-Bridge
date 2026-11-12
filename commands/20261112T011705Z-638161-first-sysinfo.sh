# boxctl: timeout=120
# First look at the box: size and software, nothing secret.
echo "== host"; uname -srm; . /etc/os-release && echo "$PRETTY_NAME"; uptime
echo "== azure size"; for k in vmSize location; do printf '%s: ' $k; curl -s -m 5 -H Metadata:true "http://169.254.169.254/metadata/instance/compute/$k?api-version=2021-02-01&format=text"; echo; done
echo "== cpu"; nproc; lscpu | grep -E '^(Model name|Socket|Core|Thread|NUMA node\(s\)|CPU max MHz|L3 cache)' 
echo "== memory"; free -g
echo "== disks"; df -h -x tmpfs -x devtmpfs -x squashfs -x overlay 2>/dev/null
echo "== software"; python3 --version; git --version; gcc --version 2>/dev/null | head -1 || echo "no gcc"; for c in g++ cmake make docker nvidia-smi; do printf '%-11s %s\n' "$c" "$(command -v $c || echo missing)"; done
echo "== sudo"; sudo -n true && echo "passwordless sudo ok"
