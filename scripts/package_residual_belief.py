"""Checked inference chunks and a separate full run/optimizer recovery archive."""
import argparse,json,sys,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.belief_capacity import sha
from bridge_harness.selfplay import atomic_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--models',type=Path,required=True)
    p.add_argument('--archive',type=Path,required=True);a=p.parse_args()
    summary=json.loads((a.run/'summary.json').read_text());manifest=dict(schema='residual-belief-model-parts-v1',files=[],promoted=False)
    for mode,c in summary['cells'].items():
        source=a.run/mode/'best.npz'
        if sha(source)!=c['selected_sha256']:raise ValueError('Selected model changed')
        out=a.models/mode;out.mkdir(parents=True,exist_ok=True);blob=source.read_bytes();parts=[]
        for i,start in enumerate(range(0,len(blob),524288)):
            f=out/f'belief.npz.part{i:03d}';f.write_bytes(blob[start:start+524288]);parts.append(dict(file=str(f.relative_to(a.models)),size_bytes=f.stat().st_size,sha256=sha(f)))
        manifest['files'].append(dict(mode=mode,output=mode+'/belief.npz',sha256=sha(source),size_bytes=len(blob),parts=parts))
    atomic_json(a.models/'manifest.json',manifest)
    (a.models/'restore.py').write_text('''import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent
for entry in json.loads((root/'manifest.json').read_text())['files']:
    data=bytearray()
    for part in entry['parts']:
        chunk=(root/part['file']).read_bytes()
        assert len(chunk)==part['size_bytes'] and hashlib.sha256(chunk).hexdigest()==part['sha256']
        data.extend(chunk)
    assert len(data)==entry['size_bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256']
    path=root/entry['output'];tmp=path.with_suffix('.tmp');tmp.write_bytes(data);tmp.replace(path)
print('All inference models restored and SHA256 verified.')
''')
    (a.models/'README.md').write_text('# Residual belief attention comparison\n\nRun `python restore.py` to reconstruct the selected dense and attention exports. '
        'Hybrid inference uses `bridge_harness.residual_attention_belief.Weights`; legacy loading intentionally rejects hybrid exports. '
        'No arena promotion or reserved test evaluation occurred. See the run report for selection and paired family metrics.\n')
    files={str(f.relative_to(a.run)):f for f in a.run.rglob('*') if f.is_file() and not f.name.endswith('.lock') and 'checkpoints' not in f.parts and f.suffix!='.tmp'}
    for mode in summary['cells']:
        state=json.loads((a.run/mode/'state.json').read_text())
        prefix=Path(state['checkpoint']).resolve()
        checkpoint_files=list(prefix.parent.glob(prefix.name+'.*'))
        if not any(f.suffix=='.index' for f in checkpoint_files) or not any('.data-' in f.name for f in checkpoint_files):
            raise ValueError('Missing final model/Adam checkpoint: '+str(prefix))
        for f in checkpoint_files:files[str(f.relative_to(a.run.resolve()))]=f
    data=Path(summary['experiment']['data'])
    for name in ['dataset.json','manifest.json']:files['frozen-data/'+name]=data/name
    for f in (data/'packed').glob('*.npz'):files['frozen-data/packed/'+f.name]=f
    files['parent.npz']=Path(summary['experiment']['parent'])
    with zipfile.ZipFile(a.archive,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        for name,f in files.items():z.write(f,name)
        z.writestr('FILE_SHA256.json',json.dumps({n:sha(f) for n,f in files.items()},indent=2))
        z.writestr('RECOVERY.json',json.dumps(dict(repo='maxschireson/Single-Dummy-Bridge',branch='research/belief-v5-impactful-cards',
            run=str(a.run.resolve()),historical_data_library_file_id='libfile_fde3_f-99aac6e06a6481918563762b3a1cc949_cf78a91e4b8c81918243c2c17fc9b8b9',
            note='Frozen recent data, parent, selected and final TF/Adam checkpoints, best/last NumPy models, and all per-family epoch evaluations included. Latest checkpoint prefixes are identified by state.json. Historical replay referenced. Code hashes are in experiment.json.'),indent=2))
    with zipfile.ZipFile(a.archive) as z:
        if z.testzip() is not None:raise ValueError('Archive corruption')
    print(json.dumps(dict(archive=str(a.archive),bytes=a.archive.stat().st_size,sha256=sha(a.archive))))

if __name__=='__main__':main()
