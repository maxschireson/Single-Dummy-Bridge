#!/usr/bin/env python3
"""Small reproducible progress report; smoke/screen scores never claim strength."""
import json
from pathlib import Path
import sys
import time

out = Path(sys.argv[1])
report = dict(updated=time.strftime('%FT%TZ', time.gmtime()), purpose='development-only; no adoption decision', runs=[])
for p in sorted(out.glob('*-*/summary.json')):
    s=json.loads(p.read_text())
    report['runs'].append(dict(name=p.parent.name, **s))
(out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
lines=['# Stu rollout mechanism screen', '', 'Development-only; these small samples do not establish strength.', '',
       '| Run | Boards | IMP/board ± SE | CPU s/board | Failures |', '| --- | ---: | ---: | ---: | ---: |']
for s in report['runs']:
    c=s.get('common',{})
    lines.append(f"| {s['name']} | {s['boards']} | {c.get('imps_per_board')} ± {c.get('se')} | {s.get('cpu_per_board')} | {s.get('failures',0)} |")
(out/'REPORT.md').write_text('\n'.join(lines)+'\n')
