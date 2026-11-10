"""Single-owner adaptive research queue with fixed deadline and independent confirmation."""
import argparse,datetime,fcntl,json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.selfplay import atomic_json
from bridge_harness.belief_capacity import sha
from scripts.report_belief_lab import report

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();root=a.run.resolve()
    lock=(root/'supervisor.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    plan=json.loads((root/'plan.json').read_text());deadline=datetime.datetime.fromisoformat(plan['deadline_utc']).timestamp()
    train_until=min(plan['created']+plan['fit_budget_hours']*3600,deadline-8*3600)
    env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','TF_CPP_MIN_LOG_LEVEL':'3',
        'BRIDGE_DDS_CACHE':str(root/'dds-cache.sqlite')}
    def status(stage,**kw):atomic_json(root/'status.json',dict(stage=stage,updated=time.time(),deadline=deadline,**kw))
    def run(args,stage,limit=deadline):
        if time.time()>=limit:return False
        with (root/'pipeline.log').open('a',buffering=1) as log:
            log.write(json.dumps(dict(stage=stage,args=args,time=time.time()))+'\n')
            proc=subprocess.Popen([sys.executable,'-u',*args],stdout=log,stderr=log,env=env)
            while True:
                status(stage,command=args)
                try:rc=proc.wait(timeout=10);break
                except subprocess.TimeoutExpired:
                    if time.time()>limit+120:
                        proc.terminate()
                        try:proc.wait(timeout=20)
                        except subprocess.TimeoutExpired:proc.kill();proc.wait()
                        return False
            if rc:
                with (root/'errors.jsonl').open('a') as f:f.write(json.dumps(dict(stage=stage,args=args,exit_code=rc,time=time.time()))+'\n')
                return False
        return True
    def fit(job,limit=train_until):
        config=Path(job['config']);out=config.parent;cfg=json.loads(config.read_text())
        if cfg.get('parent') and not Path(cfg['parent']).exists():return False
        while not (out/'result.json').exists() and time.time()<limit:
            with (out/'writer.lock').open('a+') as l:
                try:fcntl.flock(l,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:
                    status('existing_worker',active=job['name']);time.sleep(10);continue
            if not run(['scripts/train_belief_lab.py','--config',str(config)],'fit:'+job['name'],limit):return False
        if (out/'result.json').exists():
            report(root)
            return run(['scripts/score_belief_joint.py','--model',str(out/'best.npz'),'--data',str(root/'data'),'--out',str(out/'joint.json')],'joint:'+job['name'],limit)
        return False
    if sha(root/'data/dataset.json')!=plan['data_sha256']:raise ValueError('Frozen data changed')
    if not (root/'selection.json').exists():
        screen_until=min(train_until,plan['created']+plan.get('screen_budget_hours',8)*3600)
        for job in plan['jobs']:
            if time.time()>=screen_until:break
            fit(job,screen_until)
        # Reserve the second half of the fit budget for replication if screens run slowly.
        candidates=[]
        for job in plan['jobs']:
            out=Path(job['config']).parent
            if (out/'joint.json').exists():
                r=json.loads((out/'result.json').read_text());j=json.loads((out/'joint.json').read_text())
                if job['name'] not in ('dense_fixed','auction_warm') and r['best_score']<.88:candidates.append((j['exact_two_seat_nll'],job))
        candidates.sort(key=lambda x:x[0])
        finalists=[next(j for j in plan['jobs'] if j['name']=='dense_added')]
        finalists += [j for _,j in candidates if j['name']!='dense_added'][:2]
        replication_path=root/'replication.json'
        if replication_path.exists():replication=json.loads(replication_path.read_text())
        else:
            replication=[]
            for job in finalists:
                cfg=json.loads(Path(job['config']).read_text())
                for delta in (101,202):
                    c=dict(cfg,seed=cfg['seed']+delta);name=job['name']+f'_seed{delta}'
                    # Early dense pretraining is rerun with the replication seed too.
                    if c.get('parent') and '/auction_warm/' in c['parent']:
                        warmname='auction_warm'+f'_seed{delta}';warm=root/'fits'/warmname
                        if not warm.exists():
                            warm.mkdir();wc=json.loads((root/'fits/auction_warm/config.json').read_text());wc['seed']+=delta;atomic_json(warm/'config.json',wc)
                        if not any(x['name']==warmname for x in replication):replication.append(dict(name=warmname,config=str(warm/'config.json')))
                        c['parent']=str(warm/Path(c['parent']).name)
                    out=root/'fits'/name;out.mkdir(exist_ok=True);atomic_json(out/'config.json',c);replication.append(dict(name=name,config=str(out/'config.json')))
            atomic_json(replication_path,replication)
        for job in replication:
            if time.time()>=train_until:break
            fit(job)
        # Calibration is inexpensive and changes the conditional distribution, unlike projection.
        models=[('baseline',Path(plan['baseline']))];seed_summary={}
        for job in finalists:
            members=[]
            for name in (job['name'],job['name']+'_seed101',job['name']+'_seed202'):
                out=root/'fits'/name
                if (out/'joint.json').exists():
                    joint=json.loads((out/'joint.json').read_text());members.append(dict(name=name,nll=joint['exact_two_seat_nll'],model=str(out/'best.npz')))
            if not members:continue
            mean=sum(x['nll'] for x in members)/len(members)
            representative=min(members,key=lambda x:abs(x['nll']-mean))
            seed_summary[job['name']]=dict(members=members,mean_joint_nll=mean,representative=representative['name'],complete_three_seeds=len(members)==3)
            models.append((job['name'],Path(representative['model'])))
        atomic_json(root/'seed-summary.json',seed_summary)
        selections=[]
        for name,model in models:
            if not model.exists():continue
            cal=root/'calibration'/name
            if not run(['scripts/calibrate_belief_lab.py','--model',str(model),'--data',str(root/'data'),'--out',str(cal)],'calibrate:'+name,deadline-6*3600):continue
            result=json.loads((cal/'result.json').read_text())
            for row in result['rows']:
                recipe=Path(row['recipe']);joint=cal/(recipe.stem+'-joint.json')
                if not run(['scripts/score_belief_joint.py','--model',str(recipe),'--data',str(root/'data'),'--out',str(joint)],'joint-calibration:'+name,deadline-6*3600):continue
                if row['metrics']['score']<.88:
                    j=json.loads(joint.read_text());selections.append(dict(name=name,recipe=str(recipe),composite=row['metrics']['score'],joint_nll=j['exact_two_seat_nll'],recipe_sha256=sha(recipe)))
        if not selections:status('needs_review',reason='No completed calibration before confirmation budget');return
        chosen=min(selections,key=lambda x:x['joint_nll'])
        control=root/'fits/dense_added/recipe.json'
        if not control.exists():raise ValueError('Data-only control incomplete')
        selection=dict(chosen=chosen,candidates=selections,data_control=str(control),baseline=plan['baseline'],seed_summary=seed_summary,
            selected_at=time.time(),rule='Use seed closest to recipe mean, not luckiest seed; select lowest exact two-hidden-seat development likelihood among representative models and temperatures, composite guardrail <0.88. Disclose incomplete replications. No confirmation inspected.',
            promoted=False,all_training_stopped=True)
        atomic_json(root/'selection.json',selection)
    selection=json.loads((root/'selection.json').read_text());candidate=selection['chosen']['recipe']
    if not run(['scripts/confirm_belief_predictions.py','--run',str(root)],'reserved-predictions'):return
    for label,ref in [('vs_data_control',selection['data_control']),('vs_current_v5',selection['baseline'])]:
        runroot=root/'confirmation'/label
        if not run(['scripts/play_belief_lab.py','--run',str(runroot),'--candidate',candidate,'--reference',ref,'--data',str(root/'data')],'prepare:'+label):break
        while time.time()<deadline:
            done=len(list((runroot/'episodes').glob('*.json.gz')))
            if done>=2000:break
            seconds=min(900,deadline-time.time())
            if not run(['scripts/run_supplemental_arena.py','--run',str(runroot),'--workers','4','--seconds',str(seconds)],'play:'+label):break
            run(['scripts/report_belief_confirmation.py','--run',str(runroot)],'summarize:'+label)
        run(['scripts/report_belief_confirmation.py','--run',str(runroot)],'summarize:'+label,deadline+120)
    report(root)
    complete=all(len(list((root/'confirmation'/label/'episodes').glob('*.json.gz')))>=2000 for label in ('vs_data_control','vs_current_v5'))
    status('complete' if complete else 'deadline_partial',selection=selection['chosen'],promoted=False)
    if time.time()>=deadline:
        stop=Path('/workspace/scratch/74fefc15be51/bridge-gen4-components/runs/gen4-components-20261109/STOP')
        if stop.exists() and stop.read_text().strip()=='Temporary belief-lab priority through 2026-11-11T04:30:00Z':stop.unlink()

if __name__=='__main__':main()
