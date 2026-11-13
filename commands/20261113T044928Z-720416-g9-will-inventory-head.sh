# boxctl: timeout=120
head -c 2200 /home/bridgebots/.boxctl/logs/20261113T044841Z-155465-g9-will-cohort-inventory.log; echo; for d in /home/bridgebots/work/capsule-gen7-capture/recovery /home/bridgebots/work/feeds/arena-gen6-gen7-capture-feed/recovery; do echo "== $d"; ls $d | head -20; done; ls /home/bridgebots/work; ls /home/bridgebots/work/feeds | head -40
