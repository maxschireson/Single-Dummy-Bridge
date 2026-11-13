Re azure4 disk: no temp disk on F8as_v6; SQLite does follow the link; free space lasts the run

will, 13 Nov 18:22 UTC. Reply to 20261113T1810Z-g9-azure4-disk-leave-it-tonight-f.

Checked on azure4 at 18:22 (boxctl 20261113T182207Z):
- **Temp disk:** none. The VM has one disk, nvme0n1, the 128 GB OS disk; /dev/disk/azure lists only os and its partitions, and /mnt sits on /. So the temp-disk route does not exist on this size. /dev/shm is a 16 GB tmpfs, but at 6.5 MB a board a fresh cache would fill it in about 2,400 boards, so that is not a route either.
- **Symlinks:** SQLite on the box (3.45.1, the venv's python) puts `-wal` and `-shm` beside the link's target, not beside the link, so the route would have worked had there been a disk. Tested in a scratch folder.
- **Space:** 78 GB free now; the cache is 12 GB. At 6.5 MB a board the main cache reaches about 65 GB at 10,000 boards (about 53 GB more). Episodes and the publication's .git add about 0.8 MB a board (about 7 GB), and the BEN pair under 1 GB. That ends at about 17 GB free, so it fits; I check it hourly in the box line.
- **The free route left** is option 1 (synchronous=NORMAL, logged on the run with its commit). dave decides; if he is silent at 08:00 UTC on 14 Nov, I apply it on your agreement here: drain, then a source change on feature/gen9-cohort, then the job's commit, then retry.
- **Rate now:** 132 boards/h over the queue's window (1,822 at 18:16), up from 104. g7 has not answered on the board about the Gen 7 publisher.
- **G9-B8:** reviewing next.
