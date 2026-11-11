"""Check real-net capture parity with the CPU-dependent admission decisions held fixed."""
import copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.corpus import load
from bridge_harness.fork_audit import ForkBudget
from bridge_harness.selfplay import atomic_json
from ops import gen5_runtime
from ops.check_gen6_capture_equivalence import original_games
run=ROOT/'runs/fast-only-20261111';m=json.loads((run/'manifest.json').read_text())
boards=load(run/'corpus.jsonl');gen5_runtime.initialize_worker(str(run))
original=ForkBudget.admit;rows=[]
for i in range(2):
    trace=[]
    def record(self,estimate,board_forks=0):
        answer=original(self,estimate,board_forks);trace.append((board_forks,answer));return answer
    ForkBudget.admit=record
    capture=gen5_runtime.play(str(run),m,boards[i].to_dict(),i)
    off=copy.deepcopy(m);off.pop('gap_fork');position=[0]
    def replay(self,estimate,board_forks=0):
        expected,answer=trace[position[0]];position[0]+=1
        assert expected==board_forks
        return answer
    ForkBudget.admit=replay
    control=gen5_runtime.play(str(run),off,boards[i].to_dict(),i)
    assert position[0]==len(trace)
    assert original_games(capture)==original_games(control),f'Changed root/audit play on board {i}'
    rows.append(dict(index=i,gap_forks=capture['gap_fork_count'],admission_checks=len(trace),root_tables=len(capture['unique_tables'])))
    print(json.dumps(rows[-1]),flush=True)
ForkBudget.admit=original
atomic_json(run/'capture-equivalence.json',dict(status='passed',manifest=m['identity'],deals=rows,
    checks=['root and audit cards and scores','auctions','audit events excluding CPU'],
    scope='Real production models and games; audit admission decisions replayed from capture into control for this validation only. Production retains ordinary CPU budgets.',
    natural_timing_check='Strict natural-timing comparison differed only after CPU-dependent audit admission; initial debug root and common admitted nodes matched.'))
