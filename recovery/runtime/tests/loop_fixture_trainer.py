"""Protocol fixture only. Submits a fixed player; never learns or claims improvement."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.selfplay import atomic_json


def main():
    request = json.loads(Path(sys.argv[1]).read_text())
    parent = json.loads(Path(request['parent_manifest']).read_text())
    spec = parent['spec']
    spec = {k:v for k,v in spec.items() if k not in ('source_sha256','factory_sha256','training')}
    spec['artifacts'] = {k:str(Path(request['parent_manifest']).parent / v['file']) for k,v in spec['artifacts'].items()}
    if '--copy-parent' not in sys.argv:
        spec['factory']='bridge_harness.players:RandomPlayer'
    provenance = {k:request[k] for k in ('dataset_sha256','parent_identity','seed')}
    provenance.update(selection_split='validation',test_access=False,fixture=True)
    atomic_json(request['output'],dict(bot=spec,training=provenance))


if __name__=='__main__': main()
