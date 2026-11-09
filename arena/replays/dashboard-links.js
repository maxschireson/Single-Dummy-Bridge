/* Preserve the dashboard snapshot and bidding condition in every drill-down. */
(()=>{'use strict';
 function url(pair,s,metric='imps'){const u=new URL('replays/index.html',location.href);const condition=document.getElementById('condition')?.value||'common';for(const[k,v]of Object.entries({cohort:D.manifest_identity,pair,condition,window:document.getElementById('window')?.value||0,cutoff:D.generated_epoch,n:s.n,sort:metric==='count'?'newest':'swing',zeros:metric==='count'?'show':'hide'}))u.searchParams.set(k,v);if(s.total!=null)u.searchParams.set('total',s.total);return u.href;}
 function attach(cell,href,title){if(!cell||cell.querySelector('a'))return;const a=document.createElement('a');a.href=href;a.title=title;a.style.color='inherit';while(cell.firstChild)a.append(cell.firstChild);cell.append(a);}
 function decorate(){if(typeof D==='undefined')return;const own=document.getElementById('condition')?.value==='own',view=(own&&D.own_views?D.own_views:D.views)[document.getElementById('window')?.value||0],order=D.order||[...'ABC'];
 [...document.querySelectorAll('#results tr')].forEach((row,i)=>{const p=Object.keys(view.groups)[i],s=view.groups[p];if(!s)return;attach(row.children[1],url(p,s,'count'),'Replay the hands counted in this matchup');if(s.total!=null){attach(row.children[2],url(p,s),'Browse hands behind the net IMPs');attach(row.children[3],url(p,s),'Browse the paired evidence');}});
 [...document.querySelectorAll('#matrix tr')].forEach((row,i)=>order.forEach((b,j)=>{const a=order[i];if(a===b)return;const p=view.groups[a+b]?a+b:b+a,s=view.groups[p];if(s)attach(row.children[j+1],url(p,s),'Replay the canonical matchup; positive IMPs favor its first model');}));
 }
 for(const id of ['results','matrix']){const n=document.getElementById(id);if(n)new MutationObserver(decorate).observe(n,{childList:true,subtree:true});}decorate();
 if(!document.getElementById('replay-browser-link')){const p=document.createElement('p');p.id='replay-browser-link';const a=document.createElement('a');a.href='replays/';a.textContent='Browse hands and card-by-card replays, including historical runs →';p.append(a);document.querySelector('h1').after(p);}
})();
