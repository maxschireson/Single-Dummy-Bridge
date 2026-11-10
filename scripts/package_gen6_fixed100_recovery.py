from pathlib import Path
import zipfile,hashlib,json,datetime,subprocess
ROOT=Path('/workspace/scratch/d59c0a9fe14a/gen6-full-data')
REPO=Path('/workspace/scratch/919dc41e3067/bridge-gen5rz-ben')
DEST=Path('/workspace/scratch/87b7afee6da9/Gen6_Fixed100_Recovery_2026-11-10.zip')
files={}
def add(p,name):
    if p.is_file():files[name]=p.read_bytes()
for p in (ROOT/'whole-game-100').rglob('*'):
    if p.is_file() and p.suffix not in ('.tmp','.lock'):add(p,'whole-game-100/'+str(p.relative_to(ROOT/'whole-game-100')))
for p in (REPO/'bridge_harness').iterdir():
    if p.suffix in ('.py','.so'):add(p,'runtime/'+str(p.relative_to(REPO)))
for p in (REPO/'models').rglob('*'):add(p,'runtime/'+str(p.relative_to(REPO)))
for p in (REPO/'configs').glob('*'):add(p,'runtime/'+str(p.relative_to(REPO)))
for component in ('policy','belief'):add(ROOT/f'{component}-full1513/fit/best.npz',f'{component}-full1513/fit/best.npz')
add(ROOT/'scripts/match_gen6_5rz.py','scripts/match_gen6_5rz.py')
add(Path(__file__).with_name('rebuild_frozen_auctions.py'),'recovery/rebuild_frozen_auctions.py')
add(ROOT/'whole-game-100-recovered.log','whole-game-100-recovered.log')
files['environment-freeze.txt']=subprocess.check_output(['/workspace/scratch/87b7afee6da9/recovery-venv/bin/python','-m','pip','freeze'])
files['RESTORE.txt']=b'''Recovery of fixed100 Gen6 policy+belief versus frozen5RZ match, November10 2026.
Original runtime directories and terminal windows were absent in the current environment at23:10UTC. The original partial room results and wider-attention optimizer checkpoints were not found. Completed policy/belief models recovered from final archives; frozen5RZ runtime recovered from 5RZ_BEN archive. All models, all runtime Python files and DDS binary SHA256 match the original published match manifest. Reconstructed100 auctions byte-match original auctions SHA256775c52ec96934c724c771beaeaffdab1d43c1b997b263bf0cf3b32bc160bac14. Same fixed100 families, seed, samples and rules. No new model selection or training.
Restore runtime/ to /workspace/scratch/919dc41e3067/bridge-gen5rz-ben and all other match directories to /workspace/scratch/d59c0a9fe14a/gen6-full-data. Install NumPy, SciPy and TensorFlow/Keras for inference (recovered environment versions in environment-freeze.txt). Run scripts/match_gen6_5rz.py from a persistent terminal with two one-thread workers. Existing rooms/boards are skipped; check writer.lock before launch. It stops at100 boards, no adaptive extension or promotion.
Models and code remain original bytes; this recovery uses Python3.12 and TensorFlow2.20/Keras3.15.1. Bidding was only needed to recover original auctions; cardplay runtime uses portable NumPy models.
Wider64-versus96 comparison is NOT included or completed by this recovery. Its final checkpoint/result was not saved to the available archives. Do not infer width96 performance from the original64 control or latest96 epoch alone.
'''
files['archive-manifest.json']=json.dumps({'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sha256':{n:hashlib.sha256(b).hexdigest() for n,b in files.items()}},indent=2).encode()
with zipfile.ZipFile(DEST.with_suffix('.tmp'),'w',zipfile.ZIP_DEFLATED) as z:
    for n,b in files.items():z.writestr(n,b)
DEST.with_suffix('.tmp').replace(DEST)
print(json.dumps({'path':str(DEST),'bytes':DEST.stat().st_size,'sha256':hashlib.sha256(DEST.read_bytes()).hexdigest(),'result':json.loads(files.get('whole-game-100/result.json',b'{}'))}))
