'use strict';
const C=ReplayCommon,B=BridgeReplay,{$,el}=C,params=new URLSearchParams(location.search);
let fullRecord=null,record=null,cohort=null,positions=[0,0],timers=[null,null],difference=null;
const symbol={S:'♠',H:'♥',D:'♦',C:'♣'},seatNames={N:'North',E:'East',S:'South',W:'West'};
function stop(index){if(timers[index])clearInterval(timers[index]);timers[index]=null;if($('play'+index))$('play'+index).textContent='Play';}
function setPly(index,value){
  positions[index]=Math.max(0,Math.min(record.tables[index].plays.length,Math.floor(Number(value)||0)));
  if(positions[index]===record.tables[index].plays.length)stop(index);
  renderTable(index);renderControls(index);highlightHistory();
  const u=new URL(location.href);u.searchParams.delete('ply');
  positions.forEach((ply,i)=>u.searchParams.set('ply'+(i+1),ply));history.replaceState(null,'',u);
}
function setupTable(index){
  const root=$('table'+index),t=record.tables[index],board=B.tableBoard(record.board,t);
  root.replaceChildren();root.tabIndex=0;root.setAttribute('aria-label','Table '+(index+1)+' replay');
  root.append(el('h2',`Table ${index+1} · N/S ${C.labels[t.assignments[0]]}`));
  root.append(el('p',board.contract?`${board.contract} by ${seatNames[board.declarer]}`:'Passed out — no play','table-contract'));
  root.append(el('p',`E/W ${C.labels[t.assignments[1]]}`,'subtitle'));
  const transport=el('div',null,'transport'),row=el('div',null,'row');
  const actions={start:['|←','Start of board',()=>0],previous:['← Card','Previous card',()=>positions[index]-1],
    play:['Play','Play or pause',null],next:['Card →','Next card',()=>positions[index]+1],
    trick:['Trick →','Next trick',()=>Math.min(52,(Math.floor(positions[index]/4)+1)*4)],end:['→|','End of board',()=>52],
    difference:['First different play','First different play',()=>difference+1]};
  for(const [id,[label,accessible,fn]] of Object.entries(actions)){
    const button=el('button',label,id==='play'?'primary':'');button.id=id+index;
    button.setAttribute('aria-label',`Table ${index+1}: ${accessible}`);
    button.onclick=()=>{if(fn){stop(index);setPly(index,fn());return;}
      if(timers[index]){stop(index);return;}if(positions[index]===record.tables[index].plays.length)setPly(index,0);
      button.textContent='Pause';timers[index]=setInterval(()=>setPly(index,positions[index]+1),850);
    };row.append(button);
  }
  transport.append(row);const slider=el('input');slider.id='position'+index;slider.type='range';slider.min=0;slider.max=t.plays.length;slider.step=1;slider.value=0;
  slider.setAttribute('aria-label',`Table ${index+1}: Card position`);slider.oninput=e=>{stop(index);setPly(index,e.target.value);};transport.append(slider);
  const label=el('div',null,'position-label');label.id='position-label'+index;label.setAttribute('aria-live','polite');transport.append(label);root.append(transport);
  const deal=el('div');deal.id='deal'+index;root.append(deal);
  const details=el('details',null,'details');details.open=!!fullRecord.different_bidding;details.append(el('summary','Auction'));details.append(auction(board));root.append(details);
  root.onkeydown=e=>{
    if(['INPUT','SELECT'].includes(e.target.tagName))return;
    if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();stop(index);setPly(index,positions[index]+(e.key==='ArrowRight'?1:-1));}
    if(e.code==='Space'&&e.target.tagName!=='BUTTON'){e.preventDefault();$('play'+index).click();}
  };
}
function renderControls(index){const ply=positions[index];$('position'+index).value=ply;
  $('position-label'+index).textContent=`Card ${ply} of ${record.tables[index].plays.length} · ${Math.floor(ply/4)} completed tricks`;
  for(const k of ['start','previous'])$(k+index).disabled=ply===0;
  for(const k of ['next','trick','end'])$(k+index).disabled=ply===record.tables[index].plays.length;
  $('difference'+index).disabled=difference===null||!record.tables[index].plays.length;$('play'+index).disabled=!record.tables[index].plays.length;
}
function renderTable(index){
  const t=record.tables[index],ply=positions[index],board=B.tableBoard(record.board,t),state=B.replay(board,t,ply),root=$('deal'+index);root.replaceChildren();
  const layout=el('div',null,'layout'),original=B.initialHands(board),dummy=B.seats[(B.seats.indexOf(board.declarer)+2)%4];
  for(let i=0;i<4;i++){
    const seat=B.seats[i],hand=el('div',null,'hand '+seat.toLowerCase()+(seat===state.next?' next':''));
    hand.append(el('div',seatNames[seat]+(seat===board.declarer?' · declarer':board.declarer&&seat===dummy?' · dummy':''),'seat-name'));
    for(const suit of B.suits){const row=el('div',null,'suit '+('HD'.includes(suit)?'red':'black'));row.append(el('span',symbol[suit]));const ranks=el('span',null,'ranks');
      const cards=original[i].filter(c=>c[0]===suit);if(!cards.length)ranks.append(el('span','—'));
      for(const card of cards){const rank=el('span',card[1]==='T'?'10':card[1],state.hands[i].includes(card)?'':'played');rank.title=state.hands[i].includes(card)?'In hand':'Already played';ranks.append(rank);}
      row.append(ranks);hand.append(row);
    }layout.append(hand);
  }
  const center=el('div',null,'center');center.append(el('span',ply?'Trick '+Math.ceil(ply/4):'Lead','center-label'));
  for(const p of state.shown)center.append(el('span',C.formatCard(p.card),'card-'+p.seat.toLowerCase()+' '+('HD'.includes(p.card[0])?'red':'black')));
  layout.append(center);root.append(layout);
  const score=el('div',null,'scoreline');score.append(el('span',`Tricks: N/S ${state.tricks[0]} · E/W ${state.tricks[1]}`));
  const last=state.last?`${state.last[0]} played ${C.formatCard(state.last.slice(1))}`:'Opening lead';
  score.append(el('span',ply===52?'Complete':state.finishedTrick?`${state.next} won the trick`:last));root.append(score);
  root.append(el('p',`Recorded result: ${t.declarer_tricks} declarer tricks · N/S ${C.signed(t.ns_score)}`,'muted'));
  $('table'+index).classList.toggle('different',difference!==null&&ply>difference);
}
function renderHistory(){
  const table=el('table',null,'tricks'),head=el('tr');for(const s of ['Trick','Table 1','Winner','Table 2','Winner'])head.append(el('th',s));
  const th=el('thead');th.append(head);table.append(th);const tbody=el('tbody'),states=record.tables.map(t=>B.replay(record.board,t,t.plays.length));
  for(let i=0;i<Math.max(...states.map(s=>s.history.length));i++){
    const tr=el('tr');tr.append(el('td',i+1));
    states.forEach((state,index)=>{
      if(!state.history[i]){tr.append(el('td','Passed out'),el('td','—'));return;}
      const cell=el('td'),jump=el('button',state.history[i].plays.map(p=>p.seat+' '+C.formatCard(p.card)).join('  '));
      jump.setAttribute('aria-label',`Table ${index+1}: end of trick ${i+1}`);jump.onclick=()=>{stop(index);setPly(index,(i+1)*4);};cell.append(jump);
      const winner=el('td',state.history[i].winner);for(const c of [cell,winner]){c.dataset.table=index;c.dataset.trick=i;tr.append(c);}
    });tbody.append(tr);
  }table.append(tbody);$('history').replaceChildren(table);
}
function highlightHistory(){for(const cell of $('history').querySelectorAll('[data-table]')){
  const ply=positions[Number(cell.dataset.table)],trick=Number(cell.dataset.trick);
  cell.classList.toggle('active',ply>trick*4&&ply<=(trick+1)*4);
}}
function auction(board){const table=el('table',null,'auction'),head=el('tr');for(const seat of B.seats)head.append(el('th',seatNames[seat]));const thead=el('thead');thead.append(head);table.append(thead);const body=el('tbody'),offset=B.seats.indexOf(board.dealer),calls=[...Array(offset).fill(''),...(board.auction||[])];
  for(let i=0;i<calls.length;i+=4){const row=el('tr');for(let j=0;j<4;j++)row.append(el('td',calls[i+j]||''));body.append(row);}table.append(body);return table;
}
function activate(initial=false){
  for(let i=0;i<2;i++)stop(i);
  const key=$('condition').value,condition=fullRecord.conditions?.[key];
  record={...fullRecord,tables:condition?.tables||fullRecord.tables,imps:condition?condition.imps:fullRecord.imps};
  if(params.get('flip')==='1'){record={...record,pair:C.pairMembers(record.pair).reverse().join('~'),imps:record.imps==null?null:-record.imps,tables:[...record.tables].reverse()};}
  difference=B.firstDifference(record.tables[0].plays,record.tables[1].plays);
  $('title').textContent=`Board ${record.index+1} · ${C.pairLabel(record.pair)}`;document.title=$('title').textContent+' · Replay';
  $('meta').textContent=`Dealer ${record.board.dealer} · Vulnerability ${record.board.vulnerability} · ${C.date(record.completed_epoch)}`;
  $('result').textContent=record.imps==null?'Self-play: training trajectories; no head-to-head IMP estimate':`${C.signed(record.imps)} IMPs for ${C.labels[C.pairMembers(record.pair)[0]]} · ${C.signed(record.tables[0].ns_score)} − (${C.signed(record.tables[1].ns_score)}) points`;
  $('bidding-result').textContent=params.get('metric')==='bidding'?'DD bidder change for '+C.labels[params.get('model')]+': '+C.signed(fullRecord.dd_bidding_imps?.[params.get('model')])+' IMPs (separate from actual play above).':'';
  $('result').className=record.imps>0?'pos':record.imps<0?'neg':'';
  $('condition-note').textContent=key==='own'?(condition?.different?'Different historical bidding: these are the actual additional games.':'Identical auctions: the common games are reused; no extra games counted.'):fullRecord.conditions?.own?'Play comparison under the same v4 auction.':'Historical play under its frozen shared auction.';
  $('provenance').textContent=`${cohort.title} · Original board ID ${record.board.id} · Source index ${record.index} · Record SHA256 ${record.episode_sha256}`;
  const back=new URL('index.html',location.href);back.searchParams.set('cohort',cohort.id);back.searchParams.set('pair',record.pair);back.searchParams.set('condition',key);if(params.get('metric')==='bidding'){back.searchParams.set('metric','bidding');back.searchParams.set('model',params.get('model'));}if(params.has('report')){back.searchParams.delete('cohort');back.searchParams.set('report',params.get('report'));if(params.has('snapshots'))back.searchParams.set('snapshots',params.get('snapshots'));const pair=C.pairMembers(record.pair).map(k=>({P:'4p',Q:'4b'}[k]||k));back.searchParams.set('pair',pair.join(pair.every(k=>k.length===1)?'':'~'));}$('back').href=back;
  $('difference-status').textContent=difference===null?'Both tables played the same cards in the same order.':`First different play: card ${difference+1} · differences are observational, not causal attribution.`;
  setupTable(0);setupTable(1);renderHistory();$('loading').classList.add('hidden');$('viewer').classList.remove('hidden');
  positions=initial?positions.map((_,i)=>Math.max(0,Math.min(record.tables[i].plays.length,Math.floor(Number(params.get('ply'+(i+1))??params.get('ply'))||0)))):[0,0];
  const u=new URL(location.href);u.searchParams.set('condition',key);history.replaceState(null,'',u);
  positions.forEach((ply,i)=>setPly(i,ply));
}
async function load(){try{
  const catalog=await C.catalog();cohort=catalog.find(c=>c.id===params.get('cohort'));if(!cohort)throw Error('This run’s play records have not been published yet.');
  const index=await C.get(cohort.indexURL);Object.assign(C.labels,index.labels);const row=index.records.find(r=>r.id===params.get('board'));if(!row)throw Error('This board is not yet available in the play index.');
  const data=await C.get(new URL(row.shard,cohort.indexURL));fullRecord=data[row.id];if(!fullRecord||fullRecord.episode_sha256!==row.episode_sha256)throw Error('Play record does not match its index.');
  for(const condition of Object.values(fullRecord.conditions||{common:{tables:fullRecord.tables}}))for(const [i,table] of condition.tables.entries()){if(table.assignments.some(x=>typeof x!=='string')){const pair=C.pairMembers(fullRecord.pair);table.assignments=i===0?pair:[...pair].reverse();}const board=B.tableBoard(fullRecord.board,table),s=B.replay(board,table,table.plays.length);if(board.contract&&s.tricks[B.seats.indexOf(board.declarer)%2]!==table.declarer_tricks)throw Error('Recorded trick count mismatch');}
  $('condition').replaceChildren();for(const key of Object.keys(fullRecord.conditions||{common:{}})){const option=el('option',key==='common'?(fullRecord.conditions?.own?'Common v4 bidder':'Frozen shared auction'):'Historical bidders'+(fullRecord.different_bidding?' — different auctions':' — reused games'));option.value=key;$('condition').append(option);}
  $('condition').value=fullRecord.conditions?.[params.get('condition')]?params.get('condition'):'common';$('condition').onchange=()=>activate(false);activate(true);
}catch(e){$('loading').textContent=e.message;$('loading').classList.add('notice');$('title').textContent='Play record unavailable';}}
load();

