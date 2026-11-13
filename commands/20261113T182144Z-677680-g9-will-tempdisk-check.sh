# boxctl: timeout=100
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT | head -12; df -h / /mnt 2>&1 | tail -2; ls /dev/disk/azure 2>/dev/null; ls -la /dev/disk/azure/ 2>/dev/null | head -5; mount | grep -E " /mnt | /resource " ; T=$(mktemp -d /dev/shm/g9sqlt.XXXX); L=$(mktemp -d /tmp/g9sqll.XXXX); ln -s $T/real.sqlite $L/link.sqlite; ~/work/venv/bin/python -c "
import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute(\"PRAGMA journal_mode=WAL\"); c.execute(\"create table t(x)\"); c.execute(\"insert into t values (1)\"); c.commit(); print(\"sqlite\", sqlite3.sqlite_version)
import os; print(\"beside target:\", sorted(os.listdir(sys.argv[2]))); print(\"beside link:\", sorted(os.listdir(sys.argv[3])))
" $L/link.sqlite $T $L; rm -rf $T $L; df -h ~ | tail -1; du -sh ~/work/g9/runs/g9-cohort-azure4/run/dds-cache.sqlite
