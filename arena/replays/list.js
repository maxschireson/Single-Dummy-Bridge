'use strict';
const C=ReplayCommon,{$,el}=C,params=new URLSearchParams(location.search);
let cohorts=[],active=null,records=[],page=0,filtered=[],reportInputs=[];
const R=ArenaReporting,reportScope=params.get('report');let reportSnapshots=params.has('snapshots')?JSON.parse(params.get('snapshots')):null;
let reportRevisions=params.has('revisions')?JSON.parse(params.get('revisions')):null;
const biddingMetric=params.get('metric')==='bidding',model=params.get('model');
const expected={n:Number(params.get('n')),total:params.has('total')?Number(params.get('total')):null};
let linked=params.has('n'),cutoff=Number(params.get('cutoff'))||Infinity,windowSize=Number(params.get('window'))||0;
$('condition').value=params.get('condition')==='own'?'own':'common';
$('zeros').value=params.get('zeros')==='show'?'show':'hide';
$('sort').value=['swing','newest','oldest','gain','loss'].includes(params.get('sort'))?params.get('sort'):'swing';
function urlFor(row,condition=$('condition').value){const u=new URL('board.html?v=gen6-ben-followups-1',location.href);for(const [k,v]of Object.entries({cohort:row._cohort||active.id,board:row.id,pair:row._pair||row.pair,condition,...(biddingMetric?{metric:'bidding',model}:{})}))u.searchParams.set(k,v);if(row._revision)u.searchParams.set('revision',row._revision);if(active.report){if(reportRevisions)u.searchParams.set('revisions',JSON.stringify(reportRevisions));u.searchParams.set('flip',row._flip?'1':'0');u.searchParams.set('report',active.report);if(reportSnapshots)u.searchParams.set('snapshots',JSON.stringify(reportSnapshots));}return u;}
function draw(){
 const pair=$('pair').value,own=$('condition').value==='own';if(active?.report)records=R.rowsFor(reportInputs,active.report,own?'own':'common',reportSnapshots).rows;let selected=records.filter(r=>(pair==='all'||r.pair===pair)&&r.completed_epoch<=cutoff&&(!biddingMetric||Object.hasOwn(r.dd_bidding_imps||{},model))).sort(active?.report?R.byTime:(a,b)=>a.index-b.index);
 if(windowSize)selected=selected.slice(-windowSize);
 if(!active?.report)selected=selected.map(r=>({...r,imps:biddingMetric?r.dd_bidding_imps[model]:own?r.own_imps??r.imps:r.imps,scores:own?r.own_scores||r.scores:r.scores,contracts:own?r.own_contracts||r.contracts:r.contracts}));
 const total=selected.reduce((s,r)=>s+(r.imps??0),0);
 if(active){let message=`${selected.length.toLocaleString()} published hand sets · ${biddingMetric?'DD bidding delta for '+C.labels[model]:own?'native bidder condition':'common auction condition'}`;
  if(!biddingMetric&&pair!=='all'&&C.pairMembers(pair)[0]!==C.pairMembers(pair)[1])message+=` · ${C.signed(total)} IMPs for ${C.pairLabel(pair)}`;
  if(linked){const same=selected.length===expected.n&&(expected.total===null||total===expected.total);message+=same?' · Matches the linked dashboard snapshot.':` · Linked snapshot: ${expected.n} hands${expected.total===null?'':' / '+C.signed(expected.total)+' IMPs'}. Replay coverage is incomplete or has changed; no other evidence is substituted.`;}
  if(active.report)message+=' · '+new Set(selected.map(r=>r._cohort)).size+' contributing runs; repeated family/matchup observations counted once.';if(biddingMetric)message+=' · DD auction changes are separate from played-game IMPs.';if(cutoff!==Infinity)message+=' Snapshot at '+C.date(cutoff)+'.';$('coverage').textContent=message;
 }
 filtered=selected.filter(r=>$('zeros').value==='show'||(r.imps!=null&&r.imps!==0));const sort=$('sort').value;
 filtered.sort((a,b)=>sort==='newest'?b.completed_epoch-a.completed_epoch:sort==='oldest'?a.completed_epoch-b.completed_epoch:sort==='gain'?(b.imps??0)-(a.imps??0):sort==='loss'?(a.imps??0)-(b.imps??0):Math.abs(b.imps??0)-Math.abs(a.imps??0)||b.completed_epoch-a.completed_epoch);
 const pages=Math.max(1,Math.ceil(filtered.length/50));page=Math.min(page,pages-1);$('summary').textContent=`${filtered.length} ${$('zeros').value==='hide'?'nonzero swings':'hands (including self-play and ties)'} shown`+(windowSize?` · Last ${windowSize} ${active?.report?'completed boards':'indices'} in this matchup`:'');$('rows').replaceChildren();
 for(const r of filtered.slice(page*50,(page+1)*50)){
  const tr=el('tr'),board=el('td'),a=el('a',`#${r.index+1}`,'record-link');a.href=urlFor(r);a.title=r._title||active.title;board.append(a);if(r._title)board.append(el('div',r._title,'muted'));tr.append(board);
  const contracts=(r.contracts||[]).map(c=>c.contract?c.contract+' by '+c.declarer:'Passed out').filter((x,i,a)=>a.indexOf(x)===i).join(' / ');
  for(const t of [C.pairLabel(r.pair),C.date(r.completed_epoch),contracts])tr.append(el('td',t));
  for(const score of r.scores)tr.append(el('td',C.signed(score),'num'));
  const td=el('td',null,'num '+(r.imps>0?'pos':r.imps<0?'neg':''));td.append(el('strong',r.imps==null?'Self-play':C.signed(r.imps)));tr.append(td);
  const cell=el('td');if(r.different_bidding){for(const condition of ['common','own']){const link=el('a',condition==='common'?'Common auction replay →':'Native auction replay →');link.href=urlFor(r,condition);link.style.display='block';cell.append(link);}}
  else{const link=el('a','View play →');link.href=urlFor(r);cell.append(link);}tr.append(cell);$('rows').append(tr);
 }
 if(!filtered.length){const td=el('td',active?'No published hands match these filters.':'Choose an available run.');td.colSpan=8;const tr=el('tr');tr.append(td);$('rows').append(tr);}
 for(const n of document.querySelectorAll('th:nth-child(5),th:nth-child(6),#rows td:nth-child(5),#rows td:nth-child(6)'))n.style.display=biddingMetric?'none':'';document.querySelector('thead th:nth-child(7)').textContent=biddingMetric?'DD bidder IMP delta':'IMPs';$('page').textContent=`Page ${page+1} of ${pages}`;$('prev').disabled=page===0;$('next').disabled=page>=pages-1;
}
async function selectReport(scope){
 active={id:'report:'+scope,title:R.names[scope],report:scope};records=[];$('coverage').textContent='Loading combined play records…';
 try{reportInputs=await Promise.all((reportSnapshots?R.sources.filter(s=>Object.hasOwn(reportSnapshots,s.cohort)):R.pickSources(scope)).map(s=>R.loadLiveSource(s,{indexOnly:true,cutoff:reportSnapshots?.[s.cohort],revision:reportRevisions?.[s.cohort]})));
 records=R.rowsFor(reportInputs,scope,'common',reportSnapshots).rows;const desired=params.get('pair');$('pair').replaceChildren();const all=el('option','All matchups');all.value='all';$('pair').append(all);for(const pair of Object.keys(R.view(records).groups)){const o=el('option',C.pairLabel(pair));o.value=pair;$('pair').append(o);}$('pair').value=[...$('pair').options].some(o=>o.value===desired)?desired:'all';$('condition').hidden=false;$('condition').options[0].textContent='Common bidder for each cohort';page=0;draw();
 }catch(e){active=null;records=[];$('coverage').textContent='Could not load the complete combined report: '+e.message;draw();}
}
async function selectCohort(){if($('cohort').value.startsWith('report:'))return selectReport($('cohort').value.slice(7));active=cohorts.find(c=>c.id===$('cohort').value);records=[];if(!active){$('coverage').textContent='Replay records for this exact cohort are not published yet.';draw();return;}
 try{const data=await C.get(active.indexURL);if(data.cohort!==active.id)throw Error('Cohort identity mismatch');Object.assign(C.labels,data.labels);records=data.records;
 const desired=params.get('pair');$('pair').replaceChildren();const all=el('option','All matchups');all.value='all';$('pair').append(all);for(const p of (data.pairs||[...new Set(records.map(r=>r.pair))]).sort()){const o=el('option',C.pairLabel(p));o.value=p;$('pair').append(o);}$('pair').value=[...$('pair').options].some(o=>o.value===desired)?desired:'all';
 const v4=(Object.hasOwn(data.labels,'4')||Object.hasOwn(data.labels,'5')||Object.hasOwn(data.labels,'5R32'))&&data.supports_own_bidding!==false;$('condition').hidden=!v4;$('condition').options[0].textContent=v4?'Common bidder for each cohort':'Frozen shared auction';if(!v4)$('condition').value='common';page=0;draw();
 }catch(e){$('coverage').textContent='Could not load records: '+e.message;records=[];active=null;draw();}}
async function load(){try{cohorts=await C.catalog();const desired=$('cohort').value||(reportScope?'report:'+reportScope:params.get('cohort'))||'report:all';$('cohort').replaceChildren();for(const [scope,name]of Object.entries(R.names)){const o=el('option',name+' · main + components');o.value='report:'+scope;$('cohort').append(o);}if(!desired.startsWith('report:')&&!cohorts.some(c=>c.id===desired)){const o=el('option','Requested run · records pending');o.value=desired;$('cohort').append(o);}for(const c of cohorts){const o=el('option',`${c.title} (${c.count})`);o.value=c.id;$('cohort').append(o);}$('cohort').value=desired;await selectCohort();}catch(e){$('coverage').textContent=e.message;draw();}}
for(const id of ['pair','sort','zeros','condition'])$(id).addEventListener('change',()=>{page=0;if(id==='pair'||id==='condition'){linked=false;windowSize=0;}draw();});
$('cohort').addEventListener('change',()=>{linked=false;cutoff=Infinity;windowSize=0;reportSnapshots=null;reportRevisions=null;selectCohort();});$('refresh').onclick=load;$('prev').onclick=()=>{page--;draw();};$('next').onclick=()=>{page++;draw();};load();

