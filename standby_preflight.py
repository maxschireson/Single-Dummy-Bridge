"""Load models and validate the frozen capsule, without running any boards."""
from pathlib import Path
import argparse,os,runpy,sys
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--restored',type=Path,required=True);a=p.parse_args();root=a.restored.resolve();repo=root/'Single-Dummy-Bridge'
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',XDG_CACHE_HOME=str(root/'cache'))
sys.path.insert(0,str(repo));runpy.run_path(str(repo/'worker_preflight.py'),run_name='__main__')
