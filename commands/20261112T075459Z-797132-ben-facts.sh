# boxctl: timeout=60
# Read-only: facts about the BEN install for the Gen 9 question (sizes, install time, server memory).
W=$HOME/work
du -sh $W/ben $W/ben-venv 2>/dev/null | tr '\n' ' '; echo
echo "install log: first $(head -1 $W/ben-setup/install.log | cut -c1-8), last $(grep -v '^ ' $W/ben-setup/install.log | tail -1 | cut -c1-90)"
grep -E "^[0-9]{2}:[0-9]{2}:[0-9]{2} ==|took|memory" $W/ben-setup/install.log | cut -c1-160 | head -12
for n in 1 2; do pid=$(systemctl show -p MainPID --value ben-server@$n); echo "ben-server@$n (BEN 64 profile): rss $(ps -o rss= -p $pid | awk '{printf "%.1f GB", $1/1048576}'), up $(ps -o etimes= -p $pid | tr -d ' ')s"; done
ls ~/.ssh/ | tr '\n' ' '; echo
