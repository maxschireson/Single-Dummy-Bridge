// Run inside functions.exec; tools is supplied by that environment.
// Polls the local job and publishes complete snapshots to its own GitHub branch.
const repo='maxschireson/Single-Dummy-Bridge';
const workdir='/workspace/scratch/79c1d8b49652/bridge-gen4-local';
const run='runs/gen4-supplement-20261109';
const py='/workspace/scratch/bf0fa8ac2d09/.venv/bin/python';
function result(r){if(r.isError)throw Error(JSON.stringify(r));return r.structuredContent;}
async function shell(cmd,max_output_tokens=2000){const r=await tools.exec_command({cmd,workdir,max_output_tokens,yield_time_ms:1000});let out=r.output;let session=r.session_id;
  if(session){while(session){const next=await tools.write_stdin({session_id:session,chars:'',yield_time_ms:1000,max_output_tokens});out+=next.output;session=next.session_id;if(next.exit_code)throw Error(out);}}
  else if(r.exit_code)throw Error(out);return out;}
let lastCount=-1,consecutiveFailures=0;
for(let iteration=0;iteration<1440;iteration++){
 try{
  const exported=JSON.parse(await shell('OPENBLAS_NUM_THREADS=1 '+py+' scripts/export_supplemental_feed.py --run '+run+' --out publication'));
  const names=JSON.parse(await shell("python - <<'PY'\nimport json,hashlib\nfrom pathlib import Path\nr=Path('publication');print(json.dumps([{'path':str(p.relative_to(r)),'sha':hashlib.sha1(b'blob '+str(len(p.read_bytes())).encode()+b'\\0'+p.read_bytes()).hexdigest()} for p in sorted(r.rglob('*.json'))]))\nPY"));
  const head=JSON.parse(result(await tools.mcp__codex_apps__github_fetch({url:'https://api.github.com/repos/'+repo+'/git/ref/heads/arena-local-feed'})).content).object.sha;
  const previous=JSON.parse(result(await tools.mcp__codex_apps__github_fetch({url:'https://api.github.com/repos/'+repo+'/git/trees/'+head+'?recursive=1'})).content);
  const old=new Map(previous.tree.map(x=>[x.path,x.sha]));const elements=[];
  for(const file of names){if(old.get(file.path)===file.sha)continue;
   if(!/^[a-zA-Z0-9_./-]+$/.test(file.path))throw Error('Unexpected export path');
   const content=await shell('cat publication/'+file.path,200000);
   const blob=result(await tools.mcp__codex_apps__github_create_blob({repository_full_name:repo,content,encoding:'utf-8'}));
   elements.push({path:file.path,mode:'100644',type:'blob',sha:blob.sha});
  }
  if(elements.length){
   const tree=result(await tools.mcp__codex_apps__github_create_tree({repository_full_name:repo,base_tree_sha:previous.sha,tree_elements:elements}));
   const commit=result(await tools.mcp__codex_apps__github_create_commit({repository_full_name:repo,tree_sha:tree.sha,parent_sha:head,message:'Update ChatGPT Gen 4 feed: '+exported.completed+' completed boards'}));
   result(await tools.mcp__codex_apps__github_update_ref({repository_full_name:repo,branch_name:'arena-local-feed',sha:commit.sha,expected_sha:head}));
   await shell("python - <<'PY'\nimport json,time\nfrom pathlib import Path\nPath('"+run+"/publisher-status.json').write_text(json.dumps({'epoch':time.time(),'completed':"+exported.completed+",'commit':'"+commit.sha+"','interval_seconds':60}))\nPY");
  }
  consecutiveFailures=0;
  if(iteration===0)notify({publisher:'running',completed:exported.completed,interval_seconds:60});
  lastCount=exported.completed;
  if(exported.collection_complete||lastCount>=exported.target){notify({publisher:'finished',completed:lastCount});break;}
 }catch(error){consecutiveFailures++;notify({publisher:'retrying',error:String(error),consecutiveFailures});if(consecutiveFailures>=3)throw error;}
 await new Promise(resolve=>setTimeout(resolve,60000));
}
