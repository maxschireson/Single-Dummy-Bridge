# boxctl: timeout=100
ls ~/work/g9/src | head; d=$(ls -d ~/work/g9/src/*/ | head -1); git -C $d remote -v | head -2; git -C $d rev-parse --is-shallow-repository; cd /tmp && timeout 60 git -C $d fetch -q origin arena-gen8-azure3-ben64-1-feed; echo "fetch origin exit $?"
