"""Check whether an interrupted generation permits subsequent continuation."""
import os,sys,json,tempfile,subprocess
from pathlib import Path
from adapter import OUT,commit,accepted
source=OUT/'journal'
fixtures={row[0]['index']:row for row in accepted(source)[0]}
raw=fixtures[1082][1];post=fixtures[1082][2]
if len(sys.argv)>1:
 commit(Path(sys.argv[1]),1082,post_rng=post,raw=raw);sys.exit(0)
with tempfile.TemporaryDirectory(prefix='rng-live-resume-') as tmp:
 j=Path(tmp);commit(j,1932,raw=fixtures[1932][1]);before=(j/'CURRENT').read_bytes()
 child=subprocess.run([sys.executable,__file__,str(j)],env=dict(os.environ,RNG_DIAGNOSTIC_CUT='episode'))
 assert child.returncode==-9 and (j/'CURRENT').read_bytes()==before and len(accepted(j)[0])==1
 try:commit(j,1082,post_rng=post,raw=raw)
 except FileExistsError as exc:
  result={'status':'blocked','cause':'Unaccepted generation directory collides with next sequence-derived generation name','interrupted_exitcode':-9,'accepted_marker_unchanged':True,'accepted_count':1,'next_commit_error':type(exc).__name__,'production_commits':0,'next_step':'Use collision-safe generation identity or explicit verified orphan handling, then test crash/restart/continuation at every commit boundary.'}
 else:raise AssertionError('Expected orphan collision was not reproduced')
(OUT/'resume-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
