"""Per-actor native solvers; Linux CPU counters include live and reaped children.

Action wall time is the primary end-to-end latency measure. Native CPU snapshots
have /proc clock-tick resolution. Child work is already included in parent action
work and must not be added again when aggregating table decisions.
"""
import atexit
import os
from pathlib import Path
import resource

from bridge_harness import x8_claims


def child_cpu():
    r = resource.getrusage(resource.RUSAGE_CHILDREN)
    return r.ru_utime + r.ru_stime


class AccountedSolver(x8_claims.Solver):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reaped_cpu = 0.

    def _stop(self):
        before = child_cpu()
        super()._stop()
        self.reaped_cpu += child_cpu() - before

    def cpu(self):
        live = 0.
        if self.proc is not None:
            try:
                # Fields after the final ')' start at field 3; utime/stime are 14/15.
                fields = Path(f'/proc/{self.proc.pid}/stat').read_text().rsplit(')', 1)[1].split()
                live = (int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK')
            except FileNotFoundError:
                pass  # _stop reaps a terminated process before the next decision
        return self.reaped_cpu + live


class IsolatedFinder(x8_claims.Finder):
    def close(self):
        super().close()
        atexit.unregister(self.close)


def isolated_finder(binary, each):
    finder = IsolatedFinder(binary, each)
    finder.cards = AccountedSolver(finder.binary, ('--keep',))
    finder.values = AccountedSolver(finder.binary, ('--keep', '--value'))
    return finder


def solver_totals(player):
    out = dict(solver_cpu_seconds=0., solver_wall_seconds=0., solver_calls=0, solver_hits=0, solver_timeouts=0)
    while player is not None:
        for key, value in getattr(player, 'retired_solver_work', {}).items():
            out[key] += value
        if getattr(player, 'owns_finder', False):
            for solver in (player.finder.cards, player.finder.values):
                out['solver_cpu_seconds'] += solver.cpu()
                out['solver_wall_seconds'] += solver.seconds
                out['solver_calls'] += solver.calls
                out['solver_hits'] += solver.hits
                out['solver_timeouts'] += solver.timeouts
        player = getattr(player, 'child', None)
    return out
