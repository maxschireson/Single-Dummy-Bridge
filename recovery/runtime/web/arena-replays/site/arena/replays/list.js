'use strict';
const C=ReplayCommon, {$,el}=C, params=new URLSearchParams(location.search);
let cohorts=[],active=null,records=[],page=0,filtered=[];
const expected={n:Number(params.get('n')),total:Number(params.get('total'))};
let linked=params.has('n'), cutoff=Number(params.get('cutoff'))||Infinity, windowSize=Number(params.get('window'))||0;
$('pair').value=['AB','AC','BC'].includes(params.get('pair'))?params.get('pair'):'all';
$('sort').value=['swing','newest','oldest','gain','loss'].includes(params.get('sort'))?params.get('sort'):'swing';
function urlFor(row){const u=new URL('board.html',location.href);u.searchParams.set('cohort',active.id);u.searchParams.set('board',row.id);u.searchParams.set('pair',row.pair);return u;}
function draw(){
  const pair=$('pair').value;let selected=records.filter(r=>(pair==='all'||r.pair===pair)&&r.completed_epoch<=cutoff).sort((a,b)=>a.index-b.index);
  if(windowSize)selected=selected.slice(-windowSize);
  const total=selected.reduce((s,r)=>s+r.imps,0);
  if(active){
    let message=`${selected.length.toLocaleString()} published paired boards`;
    if(pair!=='all')message+=` · ${C.signed(total)} IMPs for ${C.pairLabel(pair)}`;
    if(linked&&pair!=='all'){
      if(selected.length===expected.n&&total===expected.total)message+=' · Matches the linked dashboard total.';
      else message+=` · The linked snapshot shows ${expected.n} boards / ${C.signed(expected.total)} IMPs. Play-record coverage is incomplete or has changed; these published records are a subset, not a reproduction of that total.`;
    }
    if(cutoff!==Infinity)message+=' Snapshot at '+C.date(cutoff)+'.';
    $('coverage').textContent=message;
  }
  filtered=selected.filter(r=>$('zeros').value==='show'||r.imps!==0);
  const sort=$('sort').value;
  filtered.sort((a,b)=>sort==='newest'?b.completed_epoch-a.completed_epoch:sort==='oldest'?a.completed_epoch-b.completed_epoch:sort==='gain'?b.imps-a.imps:sort==='loss'?a.imps-b.imps:Math.abs(b.imps)-Math.abs(a.imps)||b.completed_epoch-a.completed_epoch);
  const pages=Math.max(1,Math.ceil(filtered.length/50));page=Math.min(page,pages-1);
  $('summary').textContent=`${filtered.length} ${$('zeros').value==='hide'?'nonzero swings':'boards'} shown`+(windowSize?` · Last ${windowSize} per-matchup indices in the linked snapshot`:'');
  $('rows').replaceChildren();
  for(const r of filtered.slice(page*50,(page+1)*50)){
    const tr=el('tr'),board=el('td'),a=el('a',`#${r.index+1}`,'record-link');a.href=urlFor(r);board.append(a);tr.append(board);
    for(const text of [C.pairLabel(r.pair),C.date(r.completed_epoch),r.contract+' by '+r.declarer])tr.append(el('td',text));
    for(const score of r.scores)tr.append(el('td',C.signed(score),'num'));
    const td=el('td',null,'num '+(r.imps>0?'pos':r.imps<0?'neg':''));td.append(el('strong',C.signed(r.imps)));tr.append(td);
    const replay=el('td'),link=el('a','View play →');link.href=urlFor(r);replay.append(link);tr.append(replay);$('rows').append(tr);
  }
  if(!filtered.length){const td=el('td',active?'No published boards match these filters.':'Select an available run to browse its records.');td.colSpan=8;const tr=el('tr');tr.append(td);$('rows').append(tr);}
  $('page').textContent=`Page ${page+1} of ${pages}`;$('prev').disabled=page===0;$('next').disabled=page>=pages-1;
}
async function selectCohort(){
  active=cohorts.find(c=>c.id===$('cohort').value);records=[];
  if(!active){$('coverage').textContent='Play records for this live run have not been published yet. Its aggregate scores are available on the dashboard. Choose the historical run above to explore the 465 archived matches.';draw();return;}
  $('coverage').textContent='Loading paired-board index…';
  try{const data=await C.get(active.indexURL);if(data.cohort!==active.id)throw Error('Cohort identity mismatch');records=data.records;page=0;draw();}
  catch(e){$('coverage').textContent='Could not load play records: '+e.message;records=[];active=null;draw();}
}
async function load(){
  try{cohorts=await C.catalog();const desired=$('cohort').value||params.get('cohort')||cohorts[0].id;$('cohort').replaceChildren();
    if(!cohorts.some(c=>c.id===desired)){const o=el('option','Live run · records pending');o.value=desired;$('cohort').append(o);}
    for(const c of cohorts){const o=el('option',`${c.title} (${c.count})`);o.value=c.id;$('cohort').append(o);}
    $('cohort').value=desired;await selectCohort();
  }catch(e){$('coverage').textContent=e.message;draw();}
}
for(const id of ['pair','sort','zeros'])$(id).addEventListener('change',()=>{page=0;if(id==='pair'){linked=false;windowSize=0;}draw();});
$('cohort').addEventListener('change',()=>{linked=false;cutoff=Infinity;windowSize=0;selectCohort();});
$('refresh').addEventListener('click',load);$('prev').onclick=()=>{page--;draw();};$('next').onclick=()=>{page++;draw();};load();
