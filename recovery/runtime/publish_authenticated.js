const repo="maxschireson/Single-Dummy-Bridge",base="/workspace/scratch/c7932514d17d/gen6-arena";
const unwrap=r=>r.structuredContent;
await tools.exec_command({cmd:".venv/bin/python snapshot_feed.py",workdir:base,max_output_tokens:1000});
const inv=[];
for(let offset=0;;offset+=100){
 const batch=JSON.parse((await tools.exec_command({cmd:"python -c "+quote("import json;print(json.dumps(json.load(open('inventory.json'))["+offset+":"+(offset+100)+"]))"),workdir:base,max_output_tokens:15000})).output);
 inv.push(...batch);if(batch.length<100)break;
}
const ref=JSON.parse((await tools.mcp__codex_apps__github_fetch({url:"https://api.github.com/repos/"+repo+"/git/ref/heads/arena-gen6-chatgpt-feed"})).structuredContent.content);
const head=ref.object.sha;
const remote=JSON.parse((await tools.mcp__codex_apps__github_fetch({url:"https://api.github.com/repos/"+repo+"/git/trees/"+head+"?recursive=1"})).structuredContent.content);
const known=new Set(remote.tree.map(f=>f.sha));
const unique=new Map(inv.filter(f=>!known.has(f.sha)).map(f=>[f.sha,f]));
const pending=[...unique.values()];let uploaded=0;
await Promise.all(Array.from({length:6},async()=>{while(pending.length){const f=pending.pop();
let content="";
for(let offset=0;offset<f.size;offset+=48000){
const r=await tools.exec_command({cmd:"python -c "+quote("import base64;f=open("+JSON.stringify(base+"/publication/"+f.path)+",'rb');f.seek("+offset+");print(base64.b64encode(f.read(48000)).decode())"),max_output_tokens:20000});
content+=r.output.trim();
}
const r=await tools.mcp__codex_apps__github_create_blob({repository_full_name:repo,encoding:"base64",content});
const d=unwrap(r);if(d.sha!==f.sha)throw Error("blob mismatch "+f.path+" "+JSON.stringify(d));known.add(f.sha);uploaded++;if(uploaded%100===0)text({uploaded,remaining:pending.length});
}}));
const t=unwrap(await tools.mcp__codex_apps__github_create_tree({repository_full_name:repo,tree_elements:inv.map(f=>({path:f.path,mode:"100644",type:"blob",sha:f.sha}))}));
const parent=head;
const c=unwrap(await tools.mcp__codex_apps__github_create_commit({repository_full_name:repo,parent_sha:parent,tree_sha:t.sha,message:"Gen6 ChatGPT: verified independent cohort snapshot and complete recovery records"}));
text(await tools.mcp__codex_apps__github_update_ref({repository_full_name:repo,branch_name:"arena-gen6-chatgpt-feed",sha:c.sha,expected_sha:head}));
const check=JSON.parse((await tools.mcp__codex_apps__github_fetch({url:"https://api.github.com/repos/"+repo+"/git/trees/"+c.sha+"?recursive=1"})).structuredContent.content);
const actual=new Map(check.tree.map(f=>[f.path,f.sha]));
for(const f of inv)if(actual.get(f.path)!==f.sha)throw Error("published mismatch "+f.path);
await tools.exec_command({cmd:"python -c "+quote("import json,time;open('runs/gen6-chatgpt-20261111/publisher-status.json','w').write(json.dumps(dict(epoch=time.time(),commit="+JSON.stringify(c.sha)+",files="+inv.length+")))"),workdir:base,max_output_tokens:100});
text({published:c.sha,verified_files:inv.length});
function quote(s){return "'"+s.replaceAll("'","'\\''")+"'";}

