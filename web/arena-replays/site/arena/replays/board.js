'use strict';
const C=ReplayCommon,B=BridgeReplay,{$,el}=C,params=new URLSearchParams(location.search);
let record=null,cohort=null,ply=0,timer=null,difference=null;
const symbol={S:'♠',H:'♥',D:'♦',C:'♣'},seatNames={N:'North',E:'East',S:'South',W:'West'};
function stop(){if(timer)clearInterval(timer);timer=null;$('play').textContent='Play';}
function setPly(value){ply=Math.max(0,Math.min(52,Number(value)||0));if(ply===52)stop();render();const u=new URL(location.href);u.searchParams.set('ply',ply);history.replaceState(null,'',u);}
function renderTable(index){
  const t=record.tables[index],state=B.replay(record.board,t,ply),root=$('table'+index);root.replaceChildren();
  root.append(el('h2',`Table ${index+1} · N/S ${C.labels[t.assignments[0]]}`));root.append(el('p',`E/W ${C.labels[t.assignments[1]]}`,'subtitle'));
  const layout=el('div',null,'layout'),original=B.initialHands(record.board),dummy=B.seats[(B.seats.indexOf(record.board.declarer)+2)%4];
  for(let i=0;i<4;i++){
    const seat=B.seats[i],hand=el('div',null,'hand '+seat.toLowerCase()+(seat===state.next?' next':''));
    hand.append(el('div',seatNames[seat]+(seat===record.board.declarer?' · declarer':seat===dummy?' · dummy':''),'seat-name'));
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
  root.classList.toggle('different',difference!==null&&ply>difference);
}
function renderHistory(){const table=el('table',null,'tricks'),head=el('tr');for(const s of ['Trick','Table 1','Winner','Table 2','Winner'])head.append(el('th',s));const th=el('thead');th.append(head);table.append(th);const tbody=el('tbody');
  const states=record.tables.map(t=>B.replay(record.board,t,52));
  for(let i=0;i<13;i++){const tr=el('tr',null,ply>i*4&&ply<=(i+1)*4?'active':'');const cell=el('td'),jump=el('button',i+1);jump.onclick=()=>{stop();setPly((i+1)*4);};cell.append(jump);tr.append(cell);
    for(const s of states){tr.append(el('td',s.history[i].plays.map(p=>p.seat+' '+C.formatCard(p.card)).join('  ')));tr.append(el('td',s.history[i].winner));}tbody.append(tr);
  }table.append(tbody);$('history').replaceChildren(table);
}
function render(){if(!record)return;renderTable(0);renderTable(1);$('position').value=ply;$('position-label').textContent=`Card ${ply} of 52 · ${Math.floor(ply/4)} completed tricks`;
  for(const k of ['start','previous'])$(k).disabled=ply===0;for(const k of ['next','trick','end'])$(k).disabled=ply===52;
  $('difference').disabled=difference===null;
  $('difference-status').textContent=difference===null?'Both tables played the same cards in the same order.':`First different play: card ${difference+1} (trick ${Math.floor(difference/4)+1}) · Table 1 ${record.tables[0].plays[difference][0]} ${C.formatCard(record.tables[0].plays[difference].slice(1))} / Table 2 ${record.tables[1].plays[difference][0]} ${C.formatCard(record.tables[1].plays[difference].slice(1))}`;
  renderHistory();
}
function auction(){const table=el('table',null,'auction'),head=el('tr');for(const seat of B.seats)head.append(el('th',seatNames[seat]));const thead=el('thead');thead.append(head);table.append(thead);const body=el('tbody'),offset=B.seats.indexOf(record.board.dealer),calls=[...Array(offset).fill(''),...record.board.auction];
  for(let i=0;i<calls.length;i+=4){const row=el('tr');for(let j=0;j<4;j++)row.append(el('td',calls[i+j]||''));body.append(row);}table.append(body);$('auction').replaceChildren(table);
}
async function load(){try{
  const catalog=await C.catalog();cohort=catalog.find(c=>c.id===params.get('cohort'));if(!cohort)throw Error('This run’s play records have not been published yet.');
  const index=await C.get(cohort.indexURL),row=index.records.find(r=>r.id===params.get('board'));if(!row)throw Error('This board is not yet available in the play index.');
  const data=await C.get(new URL(row.shard,cohort.indexURL));record=data[row.id];if(!record||record.episode_sha256!==row.episode_sha256)throw Error('Play record does not match its index.');
  // Validate every card, every lead and follow-suit, and both final trick counts.
  for(const table of record.tables){const s=B.replay(record.board,table,52);if(s.tricks[B.seats.indexOf(record.board.declarer)%2]!==table.declarer_tricks)throw Error('Recorded trick count mismatch');}
  difference=B.firstDifference(record.tables[0].plays,record.tables[1].plays);
  $('title').textContent=`Board ${record.index+1} · ${C.pairLabel(record.pair)}`;document.title=$('title').textContent+' · Replay';
  $('meta').textContent=`${record.board.contract} by ${record.board.declarer} · Dealer ${record.board.dealer} · Vulnerability ${record.board.vulnerability} · ${C.date(record.completed_epoch)}`;
  $('result').textContent=`${C.signed(record.imps)} IMPs for ${C.labels[record.pair[0]]} · ${C.signed(record.tables[0].ns_score)} − (${C.signed(record.tables[1].ns_score)}) = ${C.signed(record.tables[0].ns_score-record.tables[1].ns_score)} points`;
  $('result').className=record.imps>0?'pos':record.imps<0?'neg':'';
  $('provenance').textContent=`${cohort.title} · Original board ID ${record.board.id} · Source index ${record.index} · Record SHA256 ${record.episode_sha256}`;
  const back=new URL('index.html',location.href);back.searchParams.set('cohort',cohort.id);back.searchParams.set('pair',record.pair);$('back').href=back;
  auction();$('loading').classList.add('hidden');$('viewer').classList.remove('hidden');setPly(params.get('ply')||0);
}catch(e){$('loading').textContent=e.message;$('loading').classList.add('notice');$('title').textContent='Play record unavailable';}}
for(const [id,fn]of Object.entries({start:()=>0,previous:()=>ply-1,next:()=>ply+1,trick:()=>Math.min(52,(Math.floor(ply/4)+1)*4),end:()=>52,difference:()=>difference+1}))$(id).onclick=()=>{stop();setPly(fn());};
$('position').oninput=e=>{stop();setPly(e.target.value);};$('play').onclick=()=>{if(timer){stop();return;}if(ply===52)setPly(0);$('play').textContent='Pause';timer=setInterval(()=>setPly(ply+1),850);};
document.addEventListener('keydown',e=>{if(!record||['INPUT','SELECT','BUTTON'].includes(e.target.tagName))return;if(e.key==='ArrowRight'){e.preventDefault();stop();setPly(ply+1);}if(e.key==='ArrowLeft'){e.preventDefault();stop();setPly(ply-1);}if(e.code==='Space'){e.preventDefault();$('play').click();}});load();
