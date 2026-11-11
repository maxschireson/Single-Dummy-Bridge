// Execute as AsyncFunction('tools','text', source). Full, verified producer snapshot.
const repo='maxschireson/Single-Dummy-Bridge',branch='arena-gen6-extra-selfplay-feed';
const base='/workspace/scratch/43350986bc04/gen6-selfplay';
const quote=s=>"'"+s.replaceAll("'","'\\''")+"'";
const unwrap=r=>{if(r.isError)throw Error(JSON.stringify(r));return r.structuredContent;};
const shell=async(cmd,max_output_tokens=2000)=>{
 let r=await tools.exec_command({cmd,workdir:base,max_output_tokens});
 while(r.session_id)r=await tools.write_stdin({session_id:r.session_id,chars:'',yield_time_ms:1000,max_output_tokens});
 if(r.exit_code!==0)throw Error(r.output);return r.output;
};
text(await shell('.venv/bin/python snapshot_feed.py'));
const inv=[];
for(let offset=0;;offset+=100){
 const batch=JSON.parse(await shell('python -c '+quote('import json;print(json.dumps(json.load(open("inventory.json"))['+offset+':'+(offset+100)+']))'),15000));
 inv.push(...batch);if(batch.length<100)break;
}
const ref=JSON.parse(unwrap(await tools.mcp__codex_apps__github_fetch({url:'https://api.github.com/repos/'+repo+'/git/ref/heads/'+branch})).content);
const head=ref.object.sha;
const remote=JSON.parse(unwrap(await tools.mcp__codex_apps__github_fetch({url:'https://api.github.com/repos/'+repo+'/git/trees/'+head+'?recursive=1'})).content);
const known=new Set(remote.tree.map(f=>f.sha));
// Reuse existing immutable blobs without uploading shared model/runtime bytes again.
const source=JSON.parse(unwrap(await tools.mcp__codex_apps__github_fetch({url:'https://api.github.com/repos/'+repo+'/git/trees/arena-gen6-fast-selfplay-independent-feed?recursive=1'})).content);
for(const f of source.tree)known.add(f.sha);
const pending=[...new Map(inv.filter(f=>!known.has(f.sha)).map(f=>[f.sha,f])).values()];
text({files:inv.length,new_blobs:pending.length});
let uploaded=0;
await Promise.all(Array.from({length:4},async()=>{
 while(pending.length){
  const f=pending.pop();let content='';
  for(let off=0;off<f.size;off+=48000){
   const py='import base64;f=open('+JSON.stringify(base+'/publication/'+f.path)+',"rb");f.seek('+off+');print(base64.b64encode(f.read(48000)).decode())';
   content+=(await shell('python -c '+quote(py),20000)).trim();
  }
  const blob=unwrap(await tools.mcp__codex_apps__github_create_blob({repository_full_name:repo,encoding:'base64',content}));
  if(blob.sha!==f.sha)throw Error('Blob hash mismatch: '+f.path);
  uploaded++;if(uploaded%30===0)text({uploaded,remaining:pending.length});
 }
}));
let tree;
for(let off=0;off<inv.length;off+=80){
 tree=unwrap(await tools.mcp__codex_apps__github_create_tree({repository_full_name:repo,...(tree?{base_tree_sha:tree.sha}:{}),
  tree_elements:inv.slice(off,off+80).map(f=>({path:f.path,mode:'100644',type:'blob',sha:f.sha}))}));
}
const commit=unwrap(await tools.mcp__codex_apps__github_create_commit({repository_full_name:repo,parent_sha:head,tree_sha:tree.sha,message:'Additional Gen6 fast self-play: arena and complete Gen7 training recovery snapshot'}));
unwrap(await tools.mcp__codex_apps__github_update_ref({repository_full_name:repo,branch_name:branch,sha:commit.sha,expected_sha:head}));
const check=JSON.parse(unwrap(await tools.mcp__codex_apps__github_fetch({url:'https://api.github.com/repos/'+repo+'/git/trees/'+commit.sha+'?recursive=1'})).content);
const actual=new Map(check.tree.map(f=>[f.path,f.sha]));
for(const f of inv)if(actual.get(f.path)!==f.sha)throw Error('Published hash mismatch: '+f.path);
const status={commit:commit.sha,files:inv.length,branch};
await shell('python -c '+quote('import json,time;d='+JSON.stringify(status)+';d["epoch"]=time.time();open("runs/fast-only-20261111/publisher-status.json","w").write(json.dumps(d))'));
text({published:commit.sha,verified_files:inv.length});
