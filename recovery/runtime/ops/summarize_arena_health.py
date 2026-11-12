"""Summarize observed process exits and resources without assuming a root cause."""
import json
from pathlib import Path

def summarize(run,limit=30):
    events=[]
    for p in sorted((Path(run)/'diagnostics').glob('pool-*.jsonl'))[-limit:]:
        for line in p.read_text().splitlines():
            try:events.append(json.loads(line))
            except json.JSONDecodeError:pass
    samples=[e for e in events if e['event']=='resources'];exits=[e for e in events if e['event']=='worker-exit']
    rss=[int(w['VmRSS'].split()[0]) for e in samples for w in e.get('workers',[]) if 'VmRSS' in w]
    oom=[e['resources']['oom_kill'] for e in events if 'oom_kill' in e.get('resources',{})]
    return dict(pool_logs=min(limit,len(list((Path(run)/'diagnostics').glob('pool-*.jsonl')))),
        samples=len(samples),worker_rss_kb_min=min(rss) if rss else None,worker_rss_kb_max=max(rss) if rss else None,
        shared_oom_counter_delta=max(oom)-min(oom) if oom else None,
        worker_exits=[dict(epoch=e['epoch'],pid=e['pid'],exitcode=e['exitcode'],signal=e['signal']) for e in exits],
        interpretation='Shared OOM counter does not identify a victim. Match exit timestamps, signals and resource samples; do not attribute causes from BrokenProcessPool alone.')

if __name__=='__main__':
    import sys
    print(json.dumps(summarize(Path(sys.argv[1])),indent=2))
