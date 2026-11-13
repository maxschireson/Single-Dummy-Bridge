# boxctl: timeout=120
cd ~/work/sidnet/e1 && wc -c split.txt split.json && echo BEGIN_TXT && cat split.txt && echo END_TXT && echo BEGIN_JSON && python3 -c "import json; print(json.dumps(json.load(open(\"split.json\")), separators=(\",\", \":\")))" && echo END_JSON
