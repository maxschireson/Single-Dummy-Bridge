"""Attribute current DDS workload costs using an isolated instrumented adapter."""
import argparse
from collections import Counter
import ctypes as C
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import ops.benchmark_live_dds as benchmark
import bridge_harness.dds_cache as caching
from bridge_harness.dds import DDS,Deal,Future
from bridge_harness.improvement import read
from bridge_harness.loop_registry import sha
from bridge_harness.selfplay import atomic_json


def build(out):
    source=(ROOT/'native/pimc_batch.cpp').read_text()
    source=source.replace('#include <algorithm>','#include <algorithm>\n#include <ctime>\nstatic double profile_cpu() { timespec t; clock_gettime(CLOCK_THREAD_CPUTIME_ID, &t); return t.tv_sec + 1e-9*t.tv_nsec; }')
    source=source.replace('bridge_dds_all_moves_batch','bridge_dds_profile_batch').replace('char* error, int error_size)','char* error, int error_size, double* timings)')
    source=source.replace('        validate(deals, count, fixed);','        double mark = profile_cpu();\n        validate(deals, count, fixed);\n        timings[0] += profile_cpu()-mark;')
    source=source.replace('        context.reset_for_solve();','        mark = profile_cpu();\n        context.reset_for_solve();\n        timings[1] += profile_cpu()-mark;')
    source=source.replace('            if (!retain && i) context.reset_for_solve();','            if (!retain && i) { mark = profile_cpu(); context.reset_for_solve(); timings[1] += profile_cpu()-mark; }')
    source=source.replace('            const int code = solve_board','            mark = profile_cpu();\n            const int code = solve_board')
    source=source.replace('            if (code != RETURN_NO_FAULT)','            timings[2] += profile_cpu()-mark;\n            if (code != RETURN_NO_FAULT)')
    path=out/'profile_batch.cpp';path.write_text(source)
    library=out/'libprofile_batch.so'
    subprocess.run(['c++','-std=c++20','-O3','-fPIC','-shared','-pthread','-I',str(ROOT/'vendor/dds/library/src'),str(path),str(ROOT/'bridge_harness/libbridge_dds.so'),'-o',str(library)],check=True)
    return library


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--trace-root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'cold-production.sqlite').exists():raise ValueError('Refusing a warm profile cache')
    library=build(out);native=C.CDLL(str(library)).bridge_dds_profile_batch
    native.argtypes=[C.c_void_p,C.POINTER(Deal),C.c_int,C.c_uint,C.c_int,C.POINTER(Future),C.c_char_p,C.c_int,C.POINTER(C.c_double)]
    native.restype=C.c_int;stats=Counter()
    def timed(name,fn):
        def call(*args,**kwargs):
            start=time.process_time()
            try:return fn(*args,**kwargs)
            finally:stats[name]+=time.process_time()-start
        return call
    class ProfileDDS(DDS):
        _deal=staticmethod(timed('python_deal_packing',DDS._deal))
        def _solve_batch_native(self,deals,fixed_seats,retain):
            output=(Future*len(deals))();error=C.create_string_buffer(512);times=(C.c_double*3)()
            status=native(self.ctx,deals,len(deals),sum(1<<s for s in set(fixed_seats)),int(retain),output,error,len(error),times)
            if status!=1:raise RuntimeError(error.value.decode())
            for k,v in zip(('native_validation','native_reset','native_search'),times):stats[k]+=v
            self.native_solves+=len(deals)
            return [(self._scores(f),f.nodes) for f in output]
    benchmark.DDS=ProfileDDS
    caching.validate_positions=timed('python_cache_validation',caching.validate_positions)
    caching.position_key=timed('python_cache_key',caching.position_key)
    caching.PositionCache.get_many=timed('cache_lookup',caching.PositionCache.get_many)
    caching.PositionCache.put_many=timed('cache_write',caching.PositionCache.put_many)
    reference={r['index']:r for r in read(a.trace_root/'result.json')['measurements'] if r['mode']=='production_cache'}
    rows=[]
    for board in read(a.trace_root/'trace.json.gz'):
        row=benchmark.measure(board,'production_cache',None,out)
        if row['all_move_output_sha256']!=reference[board['index']]['all_move_output_sha256']:
            raise ValueError('Instrumented replay changed values')
        rows.append(row);atomic_json(out/'progress.json',dict(boards=len(rows),phases=stats))
        print(board['index'],row['cpu_seconds'],flush=True)
    total=sum(r['cpu_seconds'] for r in rows);stats['other_python_and_instrumentation']=total-sum(stats.values())
    atomic_json(out/'result.json',dict(boards=len(rows),total_cpu=total,phases=stats,
        phase_shares={k:v/total for k,v in stats.items()},output_agreement=True,
        adapter_sha256=sha(ROOT/'native/pimc_batch.cpp'),profile_library_sha256=sha(library),
        note='Nested timers excluded from phase sums. Native thread CPU and Python process CPU; single benchmark thread. Instrumentation adds small overhead; use uninstrumented replay for speedup.'))
    print(dict(total_cpu=total,phases=stats),flush=True)


if __name__=='__main__':main()
