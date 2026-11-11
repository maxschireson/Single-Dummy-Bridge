// Execute as AsyncFunction('tools','text', contents) from the owning chat.
// GitHub connector is required: this host has read-only Git transport.
const root='/workspace/scratch/f846a051cf69';
const repo='maxschireson/Single-Dummy-Bridge',branch='arena-gen6-fast-selfplay-cloud-feed';
const shellQuote=s=>"'"+s.replaceAll("'","'\\''")+"'";
async function command(cmd,max_output_tokens=2000){const r=await tools.exec_command({cmd,workdir:root,max_output_tokens,yield_time_ms:10000});if(r.session_id)throw Error('Unexpected long export; wait for session '+r.session_id+' then rerun');if(r.exit_code!==0)throw Error(r.output);return r.output;}
// Export may take longer as the archive grows; allow up to 30 seconds here.
const exp=await tools.exec_command({cmd:'arena-venv/bin/python bridge/ops/export_cloud_selfplay.py gen7-selfplay-run publication',workdir:root,max_output_tokens:1000,yield_time_ms:1000});
if(exp.session_id){let r;do{r=await tools.write_stdin({session_id:exp.session_id,chars:'',yield_time_ms:1000,max_output_tokens:1000});}while(r.session_id);if(r.exit_code!==0)throw Error(r.output);}else if(exp.exit_code!==0)throw Error(exp.output);
const read=async url=>{const r=await tools.mcp__codex_apps__github_fetch({url});if(r.isError)throw Error(JSON.stringify(r));return JSON.parse(r.structuredContent.content);};
const head=(await read('https://api.github.com/repos/'+repo+'/git/ref/heads/'+branch)).object.sha;
const tree=await read('https://api.github.com/repos/'+repo+'/git/trees/'+head+'?recursive=1');
if(tree.truncated)throw Error('Remote tree truncated; inspect before publication');
const known=new Set(tree.tree.filter(x=>x.type==='blob').map(x=>x.sha));
const rows=JSON.parse(await command('python -c '+shellQuote("from pathlib import Path; import json,hashlib; rows=[]\nfor p in Path('publication').rglob('*'):\n if not p.is_file() or '.git' in p.parts: continue\n b=p.read_bytes(); rows.append(dict(path=str(p.relative_to('publication')),size=len(b),sha=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\\0'+b).hexdigest()))\nprint(json.dumps(rows))"),100000));
let position=0,uploaded=0;const pending=rows.filter(f=>!known.has(f.sha));
const results=await Promise.allSettled(Array.from({length:4},async()=>{while(position<pending.length){
 const f=pending[position++];let content='';
 for(let offset=0;offset<f.size;offset+=60000){content+=(await command('python -c '+shellQuote('import base64; f=open('+JSON.stringify(root+'/publication/'+f.path)+',"rb"); f.seek('+offset+'); print(base64.b64encode(f.read(60000)).decode())'),70000)).trim();}
 const result=await tools.mcp__codex_apps__github_create_blob({repository_full_name:repo,encoding:'base64',content});
 if(result.isError||result.structuredContent.sha!==f.sha)throw Error('Blob verification failed: '+f.path);
 uploaded++;
}}));
const failures=results.filter(r=>r.status==='rejected');if(failures.length)throw Error(failures.map(r=>String(r.reason)).join('\n'));
const prior=new Map(tree.tree.filter(x=>x.type==='blob').map(x=>[x.path,x.sha]));
const changed=rows.filter(f=>prior.get(f.path)!==f.sha);
let nextTree=head;
for(let offset=0;offset<changed.length;offset+=64){
 const batch=changed.slice(offset,offset+64);
 const t=await tools.mcp__codex_apps__github_create_tree({repository_full_name:repo,base_tree_sha:nextTree,tree_elements:batch.map(f=>({path:f.path,mode:'100644',type:'blob',sha:f.sha}))});
 if(t.isError)throw Error(JSON.stringify(t));nextTree=t.structuredContent.sha;
}
if(!changed.length){text({unchanged:true,head});return;}
const snapshot=JSON.parse(await command('cat publication/arena/data.json',30000));
const c=await tools.mcp__codex_apps__github_create_commit({repository_full_name:repo,parent_sha:head,tree_sha:nextTree,message:'Gen7 cloud self-play: '+snapshot.completed+' boards and full recovery snapshot'});if(c.isError)throw Error(JSON.stringify(c));
const u=await tools.mcp__codex_apps__github_update_ref({repository_full_name:repo,branch_name:branch,expected_sha:head,sha:c.structuredContent.sha});if(u.isError)throw Error(JSON.stringify(u));
text({published:snapshot.completed,uploaded,commit:c.structuredContent.sha,branch});
