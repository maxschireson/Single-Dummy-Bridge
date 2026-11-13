# boxctl: timeout=60
for u in g9-job-g9-cohort-azure4 g9-job-g9-cohort-ben64-azure4; do echo "== $u"; for p in $(systemctl show -p ControlGroup --value $u | xargs -I{} cat /sys/fs/cgroup{}/cgroup.procs); do ps -o pid=,pcpu=,etimes=,rss=,args= -p $p | cut -c1-170; done; done; top -bn1 | head -5 | tail -3
