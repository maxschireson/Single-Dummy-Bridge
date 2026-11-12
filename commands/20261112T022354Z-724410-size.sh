# boxctl: timeout=120
R=$HOME/work/runs/g7s-vs-g6f-01
echo "episodes: $(ls $R/episodes | wc -l) files, $(du -sh $R/episodes | cut -f1)"; du -sh $R/receipts $R/corpus.jsonl $R/artifacts $R/dds-cache.sqlite $R/manifest.json 2>/dev/null
ls -l $R/episodes | awk 'NR>1 {s+=$5; n++} END {printf "mean episode %.0f KB\n", s/n/1024}'
