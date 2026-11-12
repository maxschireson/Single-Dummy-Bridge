/* Add replay links without changing scores, cohort identities, or live polling. */
(() => {
  'use strict';
  function link(pair, stats, cohort, windowSize, cutoff) {
    const u=new URL('replays/index.html',location.href);
    for(const [k,v]of Object.entries({pair,cohort,window:windowSize,cutoff,n:stats.n,total:stats.total,sort:'swing'}))u.searchParams.set(k,v);
    return u.href;
  }
  function attach(cell,href,title){if(!cell||cell.querySelector('a'))return;const a=document.createElement('a');a.href=href;a.title=title;a.style.color='inherit';a.style.textUnderlineOffset='3px';while(cell.firstChild)a.append(cell.firstChild);cell.append(a);}
  function decorate(){
    if(typeof D==='undefined'||!D.views)return;
    const w=document.getElementById('window')?.value||'0',view=D.views[w];if(!view)return;
    [...document.querySelectorAll('#results tr')].forEach((row,i)=>{const p=Object.keys(view.groups)[i],s=view.groups[p];if(!s)return;const url=link(p,s,D.manifest_identity,w,D.generated_epoch);attach(row.children[2],url,'Browse the boards behind these net IMPs');attach(row.children[3],url,'Browse paired play records');});
    [...document.querySelectorAll('#matrix tr')].forEach((row,i)=>{[...'ABC'].forEach((b,j)=>{const a='ABC'[i];if(a===b)return;const p=[a,b].sort().join(''),s=view.groups[p];if(s)attach(row.children[j+1],link(p,s,D.manifest_identity,w,D.generated_epoch),'View the same paired evidence; positive IMPs on the board list favor the first model named');});});
  }
  for(const id of ['results','matrix']){const node=document.getElementById(id);if(node)new MutationObserver(decorate).observe(node,{childList:true,subtree:true});}
  decorate();
  const section=document.createElement('section');section.id='replay-archive';section.innerHTML='<h2>Explore the play</h2><p>Click a net IMP total or a matrix cell to browse the paired boards behind it. Sort by time, biggest swing, gains, or losses, then step through both tables card by card.</p><p id="replay-availability" class="muted">Loading replay availability…</p><p><a href="replays/">Browse published play records →</a></p>';
  const first=document.querySelector('section');if(first)first.after(section);else document.body.append(section);
  Promise.allSettled([fetch(new URL('replays/catalog.json',location.href),{cache:'no-store'}).then(r=>r.json()),fetch('https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/arena-feed/arena/replays/catalog.json',{cache:'no-store'}).then(r=>r.ok?r.json():{cohorts:[]})]).then(async results=>{
    const cohorts=new Map();results.forEach((r,i)=>{if(r.status!=='fulfilled')return;for(const c of r.value.cohorts||[])if(!cohorts.has(c.id)||c.count>cohorts.get(c.id).count)cohorts.set(c.id,{...c,base:i?'https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/arena-feed/arena/replays/':new URL('replays/',location.href).href});});
    const current=typeof D!=='undefined'?cohorts.get(D.manifest_identity):null;
    document.getElementById('replay-availability').textContent=current?`${current.count} play records published for the live run.`:'Live-run card sequences have not been published yet. Archived matches below are ready to replay; live score links will show their coverage explicitly.';
    for(const c of cohorts.values()){
      if(typeof D!=='undefined'&&c.id===D.manifest_identity)continue;
      try{const response=await fetch(new URL(c.index_url,c.base));if(!response.ok)continue;const data=await response.json();const h=document.createElement('h3');h.textContent=c.title;section.append(h);const p=document.createElement('p');
        for(const pair of ['AB','AC','BC']){const rows=data.records.filter(r=>r.pair===pair),stats={n:rows.length,total:rows.reduce((v,r)=>v+r.imps,0)};if(!stats.n)continue;const a=document.createElement('a');a.href=link(pair,stats,c.id,0,Math.max(...rows.map(r=>r.completed_epoch)));a.textContent=`${data.labels[pair[0]]} vs ${data.labels[pair[1]]}: ${stats.total>0?'+':''}${stats.total} IMPs (${stats.n} boards)`;a.style.display='block';a.style.margin='9px 0';p.append(a);}section.append(p);
      }catch(_){}
    }
  }).catch(()=>{document.getElementById('replay-availability').textContent='Replay index temporarily unavailable. Try the board browser link.';});
})();
