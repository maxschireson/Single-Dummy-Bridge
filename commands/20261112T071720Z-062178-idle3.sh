# boxctl: timeout=90
# Read-only: system CPU split over 30 s, the eight lane collectors' and BEN servers' CPU and states, solver cache sizes.
set -uo pipefail
date -u +%H:%M:%S; tick=$(getconf CLK_TCK)
cpu() { awk '{print $14+$15}' /proc/$1/stat 2>/dev/null || echo 0; }
declare -A a; declare -A st; P=""
for n in 1 2 3 4 5 6 7 8; do
  c=$(systemctl show -p MainPID --value arena-ben@$n); w=$(ps -o pid= --ppid $c --sort=-rss | head -1 | tr -d ' '); s=$(systemctl show -p MainPID --value ben-server@$n)
  P="$P w$n:$w s$n:$s"
done
for x in $P; do p=${x#*:}; a[$p]=$(cpu $p); done
vm0=$(head -1 /proc/stat); t0=$(date +%s.%N)
for i in $(seq 1 60); do for x in $P; do p=${x#*:}; st[$p]+=$(awk '{print $3}' /proc/$p/stat 2>/dev/null); done; sleep 0.5; done
vm1=$(head -1 /proc/stat); el=$(echo "$(date +%s.%N) - $t0" | bc)
tw=0; ts=0
for x in $P; do k=${x%%:*}; p=${x#*:}; v=$(echo "scale=0; 100*($(cpu $p) - ${a[$p]})/$tick/$el" | bc); s=${st[$p]}
  case $k in w*) tw=$((tw+v));; s*) ts=$((ts+v));; esac
  echo -n "$k ${v}% R$(echo -n $s | tr -cd R | wc -c)/D$(echo -n $s | tr -cd D | wc -c); "; done; echo
echo "lane collectors' workers: ${tw}%, BEN servers: ${ts}%"
echo "$vm0" "$vm1" | awk '{u=$13-$2; n=$14-$3; s=$15-$4; i=$16-$5; w=$17-$6; t=u+n+s+i+w+($18-$7)+($19-$8); printf "system cpu: user %.0f%%, sys %.0f%%, idle %.0f%%, iowait %.1f%%\n", 100*(u+n)/t, 100*s/t, 100*i/t, 100*w/t}'
du -m $HOME/work/runs/gen71fresh-*/dds-cache.sqlite* 2>/dev/null | awk '{s+=$1} END {print "lane caches: " s " MB"}'
