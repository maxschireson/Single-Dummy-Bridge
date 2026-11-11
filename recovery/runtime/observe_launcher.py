import pathlib,subprocess,psutil,time,json,os
base=pathlib.Path(__file__).resolve().parent;r=base/'runs/gen6-chatgpt-ben-recycled-20261111';d=r/'diagnostics';p=subprocess.Popen([str(base/'.venv/bin/python'),'launch_local.py'],cwd=base)
f=d/f'launcher-resources-{int(time.time())}.jsonl';known=set()
while True:
 rows=[]
 try:
  procs=[psutil.Process(p.pid)]+psutil.Process(p.pid).children(recursive=True)
  for q in procs:
   try:rows.append(dict(pid=q.pid,ppid=q.ppid(),rss=q.memory_info().rss,cpu=q.cpu_times().user+q.cpu_times().system,cmd=q.cmdline()[:3]))
   except psutil.Error:pass
 except psutil.Error:pass
 current={x['pid'] for x in rows};events=dict(epoch=time.time(),launcher_exit=p.poll(),processes=rows,disappeared=sorted(known-current),available=psutil.virtual_memory().available)
 with f.open('a') as out:out.write(json.dumps(events)+'\n')
 known=current
 if p.poll() is not None:break
 time.sleep(5)
print(json.dumps(dict(launcher_exit=p.returncode,resource_log=str(f))),flush=True)

raise SystemExit(p.returncode)
