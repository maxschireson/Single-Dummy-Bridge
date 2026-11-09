"""Package a completed candidate and its exact training inputs in 512 KiB parts."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def digest(data):return hashlib.sha256(data).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--outcomes',type=Path,required=True)
    p.add_argument('--outcome-manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=json.loads((a.run/'result.json').read_text())
    if not r.get('complete') or r.get('promoted'):raise ValueError('Completed, unpromoted candidate required')
    a.output.mkdir(parents=True,exist_ok=True)
    archive=a.run/'resume.tar.gz'
    # Selected optimizer state plus parent architecture and exact source targets.
    selected=r['models']['outcome']['best_epoch']
    with tarfile.open(archive,'w:gz') as tar:
        for name in ('config.json','partition.json','linear-baseline.npz','outcome-targets.npz',
                     'parent.keras','result.json','verification.json','outcome/state.json','outcome/result.json',
                     'outcome/validation-families.json','control/result.json',
                     'control/validation-families.json'):
            tar.add(a.run/name,arcname=name)
        cp=a.run/'outcome/best-checkpoint'
        # manager checkpoint file names are authoritative, including epoch zero.
        text=(cp/'checkpoint').read_text() if (cp/'checkpoint').exists() else ''
        if text:
            prefix=text.split('model_checkpoint_path: "',1)[1].split('"',1)[0]
        else:
            prefix=max(cp.glob('*.index'),key=lambda x:x.stat().st_mtime).stem
        for f in cp.glob(prefix+'.*'):tar.add(f,arcname='selected-checkpoint/'+f.name)
        tar.add(a.outcomes,arcname='inputs/root-outcomes.jsonl.gz')
        tar.add(a.outcome_manifest,arcname='inputs/manifest.json')
    artifacts={}
    for name,path in [('candidate.keras',a.run/'outcome/best.keras'),('resume.tar.gz',archive)]:
        data=path.read_bytes();parts=[]
        for i,start in enumerate(range(0,len(data),524288)):
            part=data[start:start+524288];filename=f'{name}.part{i:03d}'
            (a.output/filename).write_bytes(part)
            parts.append(dict(path=filename,size=len(part),sha256=digest(part)))
        artifacts[name]=dict(size=len(data),sha256=digest(data),parts=parts)
    meta=dict(schema='actual-outcome-bidding-candidate-v1',promoted=False,arena_deployed=False,
              selected_epoch=selected,artifacts=artifacts,checkpoint_prefix='selected-checkpoint/'+prefix)
    (a.output/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    (a.output/'result.json').write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({k:dict(size=v['size'],parts=len(v['parts'])) for k,v in artifacts.items()}))


if __name__=='__main__':main()
