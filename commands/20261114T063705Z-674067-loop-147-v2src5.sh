# boxctl: timeout=120
# boxctl: timeout=120
# loop session (read-only): what v2's training set was built from, to tell which arena boards are new.
P=$HOME/work/plan/rnet2w
ls $P | head -20; ls $P/data | head -20
for f in $P/*.md $P/*.json $P/*.txt $P/data/*.json $P/data/*.txt; do [ -e "$f" ] && echo "--- $f" && head -c 1500 "$f" && echo; done 2>/dev/null | head -80
