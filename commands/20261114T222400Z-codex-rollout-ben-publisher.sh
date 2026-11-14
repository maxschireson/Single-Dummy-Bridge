# boxctl: timeout=90
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"
cat > "$W/publish-ben-4951fb0.py" <<'PY'
import pathlib,subprocess,json,os,time,shutil,math
w=pathlib.Path.home()/'work/rollout-experiments-20261114';o=w/'ben-4951fb0';d=w/'pub-ben-4951fb0'
br='transfer/stu-rollout-experiments-azure2-20261114'
os.environ['GIT_SSH_COMMAND']='ssh -i '+str(pathlib.Path.home()/'.ssh/boxctl_github')+' -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new'
def git(*args):return subprocess.run(['git','-C',str(d),*args],check=True,stdout=subprocess.DEVNULL)
while subprocess.run(['systemctl','is-active','--quiet','stu-rollout-publish']).returncode==0:time.sleep(10)
subprocess.run(['git','clone','-q','--depth','1','--branch',br,'ssh://git@github.com/maxschireson/Single-Dummy-Bridge.git',str(d)],check=True)
base=json.loads((d/'report.json').read_text())
def stats(x):
    n=len(x)
    return dict(boards=n,imps_per_board=sum(x)/n if n else None,se=math.sqrt(sum((v-sum(x)/n)**2 for v in x)/(n*(n-1))) if n>1 else None)
for iteration in range(300):
    reports=[]
    for p in sorted(o.glob('*/summary.json')):
        try:s=json.loads(p.read_text())
        except json.JSONDecodeError:continue
        s.update(name='ben-'+p.parent.name,validity='integration pilot' if p.parent.name.startswith('pilot') else 'development screen; no promotion')
        reports.append(s)
    report=dict(base,updated=time.strftime('%FT%TZ',time.gmtime()),purpose='development research; BEN pilots and matched strength screen; no adoption decision',runs=base['runs']+reports)
    for p in o.rglob('*'):
        if p.is_file() and p.suffix in ('.json','.jsonl','.log','.txt') and 'episodes' not in p.parts:
            dest=d/'ben-4951fb0'/p.relative_to(o);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    arms={}
    for label in ('flat128','recursive32'):
        rows=[]
        for p in sorted(o.glob('screen-*-'+label+'/results.jsonl')):
            for line in p.read_text().splitlines():
                try:rows.append(json.loads(line))
                except json.JSONDecodeError:pass
        arms[label]={r['family']:r for r in rows}
    common=sorted(set(arms['flat128']) & set(arms['recursive32']))
    paired=dict(updated=report['updated'],families=len(common),recursive_minus_flat=stats([arms['recursive32'][f]['common']-arms['flat128'][f]['common'] for f in common]),arms={label:stats([r['common'] for r in rows.values()]) for label,rows in arms.items()},interpretation='same-family paired difference of IMP margins against BEN64; development only; not direct head-to-head IMP score',planned_families=256)
    (d/'ben-4951fb0/PAIRED.json').write_text(json.dumps(paired,indent=2))
    (d/'report.json').write_text(json.dumps(report,indent=2))
    if (w/'BEN_HANDOFF.json').exists():shutil.copy2(w/'BEN_HANDOFF.json',d/'ben-4951fb0/BEN_HANDOFF.json')
    git('add','-A')
    if subprocess.run(['git','-C',str(d),'diff','--cached','--quiet']).returncode:
        git('-c','user.name=Codex rollout experiments','-c','user.email=codex@openai.com','commit','-q','-m','Publish bounded BEN rollout comparison')
        git('push','-q','origin',br)
    if iteration>0 and subprocess.run(['systemctl','is-active','--quiet','stu-rollout-ben-4951fb0']).returncode:break
    time.sleep(60)
PY
sudo systemd-run --unit=stu-rollout-ben-publish-4951fb0 --uid=bridgebots --property=RuntimeMaxSec=16200 /usr/bin/python3 "$W/publish-ben-4951fb0.py"
cat "$W/ben-4951fb0/STATUS.json"
systemctl show stu-rollout-ben-4951fb0 stu-rollout-ben-publish-4951fb0 -p Id -p ActiveState -p MainPID
