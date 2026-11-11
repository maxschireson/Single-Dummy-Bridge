#!/usr/bin/env python3
"""Snapshot frozen arrays and committed model/Adam checkpoints during a size fit."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--source-commit',required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[1];run=a.run.resolve();prefix=run.relative_to(root)
    data={}
    for f in sorted((run/'data').glob('*')):
        if f.is_file() and f.name!='progress.json':data[str(f.relative_to(root))]=f.read_bytes()
    for name in ('small','large'):
        fit=run/name
        if not (fit/'state.json').exists():continue
        state_raw=(fit/'state.json').read_bytes();state=json.loads(state_raw)
        data[str(prefix/name/'state.json')]=state_raw
        for f in [fit/'config.json',fit/f'best-epoch-{state["best_epoch"]}.npz',fit/'initial.npz']:
            if f.exists():data[str(f.relative_to(root))]=f.read_bytes()
        for key in ('checkpoint','selected_checkpoint'):
            base=Path(state[key]);base=base if base.is_absolute() else root/base
            files=sorted(base.parent.glob(base.name+'.*'))
            if len(files)<2:raise ValueError('Committed checkpoint missing')
            for f in files:data[str(f.relative_to(root))]=f.read_bytes()
        if state['complete']:
            for f in (fit/'result.json',fit/'best.npz'):
                if f.exists():data[str(f.relative_to(root))]=f.read_bytes()
    for f in (run/'comparison.json',run/'sources.json',run/'RUN_NOTES.json'):
        if f.exists():data[str(f.relative_to(root))]=f.read_bytes()
    recovery=dict(source_commit=a.source_commit,repository='maxschireson/Single-Dummy-Bridge',
        branch='research/belief-size-comparison',run=str(prefix),
        restore='Extract into the matching Git checkout. Resume the size-specific trainer with the same data/config. Model/Adam checkpoints are exact; do not reset.',
        sha256={name:hashlib.sha256(content).hexdigest() for name,content in data.items()})
    with zipfile.ZipFile(a.out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,content in data.items():z.writestr(name,content)
        z.writestr('RECOVERY.json',json.dumps(recovery,indent=2))
    print(json.dumps(dict(path=str(a.out),bytes=a.out.stat().st_size,files=len(data))))

if __name__=='__main__':main()
