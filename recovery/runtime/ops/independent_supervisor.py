"""Operational independent-worker collector; frozen scientific code unchanged."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import ops.diagnostic_supervisor as diagnostic
from ops.independent_workers import IndependentWorkers

def main():
    run=Path(sys.argv[sys.argv.index('--run')+1]).resolve()
    IndependentWorkers.run=run
    diagnostic.DiagnosticPool=IndependentWorkers
    import ops.supervise_mixed as supervisor
    command=supervisor.command
    def launch(args,root,timeout):
        args=[str(ROOT/'ops/independent_supervisor.py') if x=='ops/diagnostic_supervisor.py' else x for x in args]
        return command(args,root,timeout)
    supervisor.command=launch
    diagnostic.main()

if __name__=='__main__':main()
