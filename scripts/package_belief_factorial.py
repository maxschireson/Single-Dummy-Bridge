"""Publishable 512 KiB inference parts plus a separate optimizer/data bundle."""
import argparse,hashlib,json,sys,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.screen_attention_belief import save_json
from bridge_harness.belief_capacity import sha

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    p.add_argument('--models',type=Path,required=True);p.add_argument('--archive',type=Path,required=True)
    a=p.parse_args();summary=json.loads((a.run/'summary.json').read_text());a.models.mkdir(parents=True,exist_ok=True)
    manifest=dict(schema='dense-belief-factorial-artifacts-v1',files=[],test_evaluated=False,promoted=False)
    for cell in summary['cells']:
        source=a.run/cell/'best.npz';parts=[];blob=source.read_bytes();out=a.models/cell;out.mkdir(parents=True,exist_ok=True)
        for i,start in enumerate(range(0,len(blob),524288)):
            p=out/f'belief.npz.part{i:03d}';p.write_bytes(blob[start:start+524288]);parts.append(dict(file=str(p.relative_to(a.models)),size_bytes=p.stat().st_size,sha256=sha(p)))
        if sha(source)!=summary['cells'][cell]['selected_sha256']:raise ValueError('Selected model changed')
        manifest['files'].append(dict(cell=cell,output=cell+'/belief.npz',size_bytes=len(blob),sha256=sha(source),parts=parts))
    save_json(a.models/'manifest.json',manifest)
    # Model inference files and source code are already published in GitHub.
    # Keep optimizer states, exact per-family evaluations and replay metadata here.
    files={}
    for p in a.run.rglob('*'):
        if not p.is_file() or p.name in ('best.npz','last.npz','pipeline.lock','writer.lock') or p.suffix=='.tmp':continue
        if 'checkpoints' in p.parts:continue  # Selected optimizer checkpoint is sufficient to resume the chosen candidate.
        files[str(p)]=p
    data=Path(summary['experiment']['data'])
    for name in ('dataset.json','manifest.json'):
        files[str(data/name).lstrip('/')]=data/name
    for p in (data/'packed').glob('*.npz'):files[str(p).lstrip('/')]=p
    hashes={name:sha(p) for name,p in files.items()}
    with zipfile.ZipFile(a.archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        for name,p in sorted(files.items()):z.write(p,name)
        z.writestr('FILE_SHA256.json',json.dumps(hashes,indent=2))
        z.writestr('RECOVERY.json',json.dumps(dict(repo='maxschireson/Single-Dummy-Bridge',branch='research/belief-v5-impactful-cards',
            run=str(a.run.resolve()),historical_replay_library_file_id='libfile_fde3_f-99aac6e06a6481918563762b3a1cc949_cf78a91e4b8c81918243c2c17fc9b8b9',
            earlier_source_recovery_library_file_id='libfile_fde3_f-0d9324f7cff88191a5d1e60c4a4e59bd_cf78a91e4b8c81918243c2c17fc9b8b9',
            inference_models=str(a.models),note='All four selected model and optimizer checkpoints are stored in selected-checkpoint directories. Paths in manifests are original local paths. Recent packed data is included; historical replay is referenced. No test evaluation or arena promotion.'),indent=2))
    with zipfile.ZipFile(a.archive) as z:
        if z.testzip() is not None:raise ValueError('Archive corruption')
    print(json.dumps(dict(archive=str(a.archive),bytes=a.archive.stat().st_size,sha256=sha(a.archive),model_files=len(manifest['files']),checkpoint_files=len(files))))

if __name__=='__main__':main()
