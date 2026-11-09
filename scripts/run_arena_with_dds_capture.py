"""Observe expensive native DDS calls without changing frozen arena code/results.

This is a replay corpus, not an internal search-tree trace. Batch order and all
native misses are preserved because related-world proof reuse affects cost.
"""
import ctypes as C
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import run_supplemental_arena as frozen

ORIGINAL_INITIALIZE = frozen.initialize
ORIGINAL_PLAY = frozen.play
CONTEXT = {}
RECORDER = None


def packed(deal):
    return dict(trump=deal.trump, leader=deal.first,
                trick_suits=list(deal.suits), trick_ranks=list(deal.ranks),
                hands=[[int(x) for x in hand] for hand in deal.hands])


def unpacked(item):
    from bridge_harness.dds import Deal
    d = Deal(trump=item['trump'], first=item['leader'])
    for i in range(3):
        d.suits[i], d.ranks[i] = item['trick_suits'][i], item['trick_ranks'][i]
    for h in range(4):
        for s in range(4):
            d.hands[h][s] = item['hands'][h][s]
    return d


class Recorder:
    def __init__(self, run):
        self.run = Path(run)
        self.manifest = json.loads((self.run/'manifest.json').read_text())
        self.directory = self.run/'dds-expensive'
        self.directory.mkdir(exist_ok=True)
        self.min_nodes = int(os.environ.get('DDS_CAPTURE_MIN_NODES', '100000'))
        self.min_seconds = float(os.environ.get('DDS_CAPTURE_MIN_SECONDS', '0.1'))
        if self.min_nodes < 0 or self.min_seconds < 0:
            raise ValueError('Negative capture threshold')
        self.builds = {}

    def save(self, solver, deals, results, elapsed, cpu, kind, fixed=(), retain=False):
        nodes = [int(result[1]) for result in results]
        if max(nodes, default=0) < self.min_nodes and elapsed < self.min_seconds:
            return
        library = Path(solver.lib._name).resolve()
        if str(library) not in self.builds:
            self.builds[str(library)] = hashlib.sha256(library.read_bytes()).hexdigest()
        positions = [packed(d) for d in deals]
        record = dict(schema='dds-expensive-replay-v1', created_epoch=time.time(),
                      manifest_identity=self.manifest['identity'], context=dict(CONTEXT),
                      solver_sha256=self.builds[str(library)], call_kind=kind,
                      solver_options=getattr(solver,'capture_options',None),
                      target=-1, solutions=3, scalar_mode=1 if kind=='scalar' else None,
                      fixed_seats=list(fixed), retain=bool(retain),
                      elapsed_seconds=elapsed, cpu_seconds=cpu,
                      min_nodes=self.min_nodes, min_seconds=self.min_seconds,
                      selection='any_native_world_nodes_or_whole_call_wall_time',
                      positions=positions, results=[dict(scores=v, nodes=int(n)) for v,n in results],
                      ordered_positions_sha256=hashlib.sha256(json.dumps(positions,sort_keys=True).encode()).hexdigest(),
                      semantics='Perfect-information sampled-world labels; not single-dummy value targets or proof traces.')
        raw=json.dumps(record,separators=(',',':')).encode()
        name=str(time.time_ns())+'-'+str(os.getpid())+'-'+uuid.uuid4().hex
        temporary=self.directory/(name+'.tmp')
        with temporary.open('wb') as f:
            f.write(gzip.compress(raw,compresslevel=3));f.flush();os.fsync(f.fileno())
        temporary.replace(self.directory/(name+'.json.gz'))


def install(run):
    global RECORDER
    from bridge_harness.dds import DDS
    if getattr(DDS, '_expensive_capture_installed', False):
        return
    RECORDER=Recorder(run)
    batch=DDS._solve_batch_native
    scalar=DDS.solve
    constructor=DDS.__init__

    def capture_init(self,path=None,tt_kind=2,cache_path=None):
        constructor(self,path=path,tt_kind=tt_kind,cache_path=cache_path)
        self.capture_options=dict(tt_kind=tt_kind,context_parameters=[tt_kind,16,64],
                                  cache_enabled=self.cache is not None)

    def capture_batch(self,deals,fixed_seats,retain):
        start=time.perf_counter();cpu=time.process_time()
        result=batch(self,deals,fixed_seats,retain)
        elapsed=time.perf_counter()-start;cpu=time.process_time()-cpu
        RECORDER.save(self,deals,result,elapsed,cpu,'batch',fixed_seats,retain)
        return result

    def capture_scalar(self,hands,trump,leader,trick):
        start=time.perf_counter();cpu=time.process_time();before=self.native_solves
        result=scalar(self,hands,trump,leader,trick)
        elapsed=time.perf_counter()-start;cpu=time.process_time()-cpu
        if self.native_solves>before:  # Cache hits are not expensive native searches.
            RECORDER.save(self,[self._deal(hands,trump,leader,trick)],[result],elapsed,cpu,'scalar')
        return result

    DDS._solve_batch_native=capture_batch
    DDS.solve=capture_scalar
    DDS.__init__=capture_init
    DDS._expensive_capture_installed=True


def initialize(root):
    install(root)
    ORIGINAL_INITIALIZE(root)


def play(job):
    from bridge_harness.core import Board
    from bridge_harness.bidding_env import deal_key
    index, board=job
    CONTEXT.clear()
    CONTEXT.update(index=index,family=deal_key(Board.from_dict(board).hands,True),
                   board_id=board.get('id'))
    return ORIGINAL_PLAY(job)


if __name__=='__main__':
    frozen.initialize=initialize
    frozen.play=play
    # Respect the supplemental run's existing cancellation plan and endpoint.
    run=Path(sys.argv[sys.argv.index('--run')+1])
    if (run/'collection-plan.json').exists():
        from scripts import run_filtered_arena
        run_filtered_arena.main()
    else:
        frozen.main()
