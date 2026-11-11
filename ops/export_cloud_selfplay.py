"""Build a connector-published, fully resumable snapshot of this fast-only run."""
from pathlib import Path
import gzip
import json
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from ops.export_gen5 import export
from ops.publish_gen5 import snapshot_runtime

def snapshot(run,out):
    export(run,out)
    b=out/'recovery';b.mkdir(exist_ok=True)
    for n in ('manifest.json','state.json','heartbeat.json','preflight.json','preflight-equivalence.json','launch.json','runtime-requirements.txt'):
        if (run/n).exists():shutil.copy2(run/n,b/n)
    for d in ('artifacts','assets','episodes','receipts'):
        shutil.copytree(run/d,b/d,dirs_exist_ok=True)
    for d in ('failure-history','diagnostics'):
        if (run/d).exists():shutil.copytree(run/d,b/d,dirs_exist_ok=True)
    snapshot_runtime(run,b)
    for n in ('prepare_gen7_selfplay_cloud.py','export_cloud_selfplay.py','supervise_cloud_selfplay.py','publish_cloud_capture.js','cloud_observed.py','diagnostic_supervisor.py'):
        shutil.copy2(ROOT/'ops'/n,b/'runtime/ops'/n)
    p=b/'corpus-parts'
    if not p.exists():
        p.mkdir();raw=gzip.compress((run/'corpus.jsonl').read_bytes(),mtime=0)
        for i in range(0,len(raw),96000):(p/f'corpus.jsonl.gz.part-{i//96000:03}').write_bytes(raw[i:i+96000])
    (b/'restore_corpus.py').write_text('from pathlib import Path\nimport gzip,hashlib,json\nr=Path(__file__).resolve().parent\nb=gzip.decompress(b"".join(p.read_bytes() for p in sorted((r/"corpus-parts").glob("*.part-*"))))\nassert hashlib.sha256(b).hexdigest()==json.loads((r/"manifest.json").read_text())["corpus_sha256"]\n(r/"corpus.jsonl").write_bytes(b)\nprint("Corpus restored and SHA256 verified")\n')
    (out/'README.md').write_text('# Gen7 capture: Gen6 fast self-play only\n\nIndependent 25,000-family cohort, three workers, 50% tie audits, gap forks (2/band, CPU share 1.5). No BEN or medium matches.\n\nRecovery: run `python recovery/restore_corpus.py`, install `recovery/runtime-requirements.txt`, and use the frozen `recovery/runtime` with `ops/gen5_runtime.py --run <absolute recovery path> --workers 3`. Verify manifest, model and runtime hashes before starting; never resume concurrently with the owning producer. Gen3 is an audit selector only.\n\nRaw compressed episodes and receipts are in recovery. Dashboard snapshots are under arena. Self-play has null IMP comparisons.\n')

if __name__=='__main__':snapshot(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve())
