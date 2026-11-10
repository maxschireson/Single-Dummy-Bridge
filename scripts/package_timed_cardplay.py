"""Snapshot evaluation data and binaries; source code lives in the pinned repo."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
output=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT.parent/'V5_BEN_Time_Matched_ACE_Cardplay_2026-11-10.zip'
source=json.loads((ROOT/'runs/source-reference.json').read_text())
lines=['# V5 / BEN / ACE calibration snapshot — 2026-11-10','',
       'Positive IMPs favor v5. These are evaluation-only deals. Partial scores are provisional.', '',
       '| Test | Paired boards | v5 IMPs | IMP/board ± SE | v5 seconds/pair | Opponent seconds/pair |',
       '|---|---:|---:|---:|---:|---:|']
for name in ['ben16-v5_192-100','ace-v5_192-100']:
    p=ROOT/'runs'/name/'result.json'
    if not p.exists():continue
    m=json.loads(p.read_text());n=m['boards'];opp=m['kind']
    if not n:continue
    lines.append(f"| {name} | {n}/100 | {m['imps']:+d} | {m['imps_per_board']:+.3f} ± {m['se']:.3f} | {m['timing']['v5']['seconds_per_paired_board']:.2f} | {m['timing'][opp]['seconds_per_paired_board']:.2f} |")
lines+=['','BEN uses 16 target samples; v5 uses 192 layouts. ACE uses 1 second per nonforced play, 4 seconds on opening lead, one thread, depth 4, exploration 0.0058, limiter off. Forced moves bypass search.',
    '', 'BEN reuses the original 100 deals and native net-only auctions. ACE uses the frozen v5 bidder at all four seats, with one identical auction per paired board.',
    '', 'The first two ACE pilots are invalid because they selected the first unsorted API candidate. Only the ranked pilot and the full 192-layout ACE run have valid strength results. The adapter ranks ACE contract-success probability first, then trick margin.',
    '', 'Validation passed: 1,040 public-state legal-move reconstructions; native values and the selected move matched independent DDS in 35 fully known test positions. No hidden actual hands enter ACE during matches.',
    '', f"Source: {source['url']} (commit {source['commit']}). This archive contains data, frozen models and runtime binaries; source code is kept in the repository.",
    '', 'Recovery: retrieve the pinned source, then extract this archive at the checkout root. Install runs/python-environment.txt in Python 3.12; install .NET 8 and set DOTNET_ROOT. ACE binaries are in vendor/ace; add that directory to LD_LIBRARY_PATH. The DDS shared library is in bridge_harness.',
    '', 'BEN runtime: https://github.com/lorserker/ben at 9b5f43104aeac713a80b73513f2f2d6daf9f8769. Set BEN_ROOT to that checkout. Restore the model paths listed in runs/ben-models-provenance.json and verify their hashes. .NET 8.0.22 Linux x64 runtime was used: https://dotnetcli.blob.core.windows.net/dotnet/Runtime/8.0.22/dotnet-runtime-8.0.22-linux-x64.tar.gz .',
    '', 'Resume only after confirming the existing writer is stopped. Fresh worker status updates mean a run is active even when another sandbox cannot see its processes. Each run also has a writer lock and frozen-input verification. Never run duplicate writers or change models/effort mid-match.',
    '', 'Commands (from the checkout, with its Python environment and LD_LIBRARY_PATH set):',
    '```bash',
    'python -u scripts/calibrate_cardplay.py run --run runs/ben16-v5_192-100 --workers 4 --port 18400',
    'python -u scripts/calibrate_cardplay.py run --run runs/ace-v5_192-100 --workers 4',
    '```',
    '', 'For status, replace run with summary. Existing manifests retain the frozen settings. Recompute summaries from the immutable episodes after restoring: live snapshot result.json can lag a newly completed episode. Checkpoints include invalid pilot audit data, explicitly marked INVALID.json; never mix those into final scores.',
    '', 'Original 32/32 result: v5 -129 IMPs over 100 boards; v5 4.23 seconds/pair, BEN 32.38 seconds/pair. The rematch changes both effort settings, so changes in margin do not isolate either setting alone.']
report='\n'.join(lines)+'\n'
files=[]
for folder in ['fixtures','models/ace-v5-frozen','runs']:
    files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix not in {'.log','.lock','.tmp'} and '__pycache__' not in p.parts)
files += [ROOT/p for p in ['bridge_harness/libbridge_dds.so','vendor/ace/Ace.dll','vendor/ace/libbcalcdds.so','vendor/ace/LICENSE','vendor/dds/LICENSE']]
entries={str(p.relative_to(ROOT)):p.read_bytes() for p in files}
inventory={name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in entries.items()}
output.parent.mkdir(parents=True,exist_ok=True)
temporary=output.with_suffix('.tmp')
with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    z.writestr('REPORT.md',report)
    z.writestr('SNAPSHOT_FILES.json',json.dumps(inventory,indent=2)+'\n')
    for name,data in entries.items():z.writestr(name,data)
temporary.replace(output)
print(json.dumps({'path':str(output),'bytes':output.stat().st_size,'files':len(files)}))
