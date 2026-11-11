"""Register an independent Gen6 stream and paired bidding/play/total dashboard views."""
import argparse
import json
from pathlib import Path


def once(text,old,new):
    if text.count(old)!=1:raise ValueError('Dashboard template changed: '+old[:80])
    return text.replace(old,new,1)


def register(pages,manifest):
    if manifest.get('variant')!='6' or not manifest.get('independent_cohort'):raise ValueError('Expected independent Gen6 manifest')
    pages=Path(pages);rpath=pages/'arena/reporting.js';spath=pages/'arena/supplemental.js'
    r=rpath.read_text();s=spath.read_text()
    entry="  {key:'gen6independent',group:'gen6',generation:6,variant:'6',environment:'codex',name:'Gen 6 · independent collector',branch:'arena-gen6-independent-feed',cohort:'"+manifest['identity']+"'},\n"
    r=once(r,' const sources=[\n',' const sources=[\n'+entry)
    r=once(r,' const labels={'," const labels={'6-32':'Gen 6 fast (32)','6-256':'Gen 6 medium (256)',")
    r=once(r,"order=['5RZ32'","order=['6-32','6-256','5RZ32'")
    r=once(r,"'5RZ32':'Gen 5RZ (32)'","'5RZ32':'Gen 5 (32, formerly 5RZ)'")
    # Preserve both candidate-oriented results when normalizing a pair's orientation.
    r=once(r,'rows.push({...r,pair,imps:',"rows.push({...r,pair,common_imps:flip?-r.imps:r.imps,native_imps:flip?-r.own_imps:r.own_imps,imps:")
    marker='  const generated_epoch=chosen.length?'
    code="""  const difference_views={};
  const paired=common.rows.filter(r=>Number.isFinite(r.native_imps));
  for(const n of [0,100,500,1000]){const groups={};for(const pair of new Set(paired.map(r=>r.pair))){let rows=paired.filter(r=>r.pair===pair);if(n)rows=rows.slice(-n);groups[pair]={play:stats(rows.map(r=>r.common_imps)),total:stats(rows.map(r=>r.native_imps)),bidding:stats(rows.map(r=>r.native_imps-r.common_imps)),different_bidding:rows.filter(r=>r.different_bidding).length};}difference_views[n]={groups};}
"""
    r=once(r,marker,code+marker)
    r=once(r,'rates,views,own_views:','rates,views,difference_views,own_views:')
    r=once(r,"model_note:chosen.some(x=>x.source.variant==='5RZ')?", "model_note:chosen.some(x=>x.source.variant==='6')?'Gen6: opening-lead belief net, then hand-fit scorer. Fast 32 layouts to trick7; medium 256 to trick6; compatible-layout lists solve up to 256. Common Gen6 bidding measures play; native partnership bidding measures total; bidding is paired native minus common and includes auction/play interaction. Fresh independent cohorts.':chosen.some(x=>x.source.variant==='5RZ')?")
    s=once(s,'<option value="gen5rz">','<option value="gen6independent">Gen 6 · independent collector</option><option value="gen5rz">')
    s=once(s,'  D=R.build(available,selected);renderAll();','  D=R.build(available,selected);renderAll();renderDifferences();')
    marker=' function report(){'
    ui=""" const differences=document.createElement('section');differences.id='gen6-differences';section.after(differences);
 function renderDifferences(){
  differences.hidden=!R.pickSources(selected).some(s=>s.generation===6);if(differences.hidden)return;
  differences.replaceChildren();const title=document.createElement('h2');title.textContent='Bidding, play and total differences';differences.append(title);
  const note=document.createElement('p');note.className='muted';note.textContent='IMPs per board, positive favors the first bot. Play: common Gen6 auctions. Total: native partnership auctions. Bidding: paired total minus play, including auction/play interaction. Each mean has its own paired 95% interval.';differences.append(note);
  const table=document.createElement('table'),head=document.createElement('tr');
  for(const value of ['Matchup','Boards','Different auctions','Bidding mean [95% CI]','Play mean [95% CI]','Total mean [95% CI]']){const th=document.createElement('th');th.textContent=value;head.append(th);}const thead=document.createElement('thead');thead.append(head);table.append(thead);
  const body=document.createElement('tbody'),groups=D.difference_views?.[document.getElementById('window').value]?.groups||{};
  const value=s=>s.mean===null?'—':s.mean.toFixed(3)+(s.ci?' ['+s.ci.map(x=>x.toFixed(3)).join(', ')+']':' [CI unavailable]');
  for(const [pair,g] of Object.entries(groups)){const tr=document.createElement('tr');for(const text of [R.members(pair).map(k=>D.labels[k]||k).join(' vs '),g.play.n,g.different_bidding,value(g.bidding),value(g.play),value(g.total)]){const td=document.createElement('td');td.textContent=text;tr.append(td);}body.append(tr);}table.append(body);differences.append(table);
 }
 document.getElementById('window').addEventListener('change',renderDifferences);
"""
    s=once(s,marker,ui+marker)
    rpath.write_text(r);spath.write_text(s)
    # The replay picker also discovers this feed, using its immutable cohort catalog.
    cpath=pages/'arena/replays/common.js';c=cpath.read_text()
    c=once(c,'const urls=[',"const urls=['https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/arena-gen6-independent-feed/arena/replays/catalog.json',")
    cpath.write_text(c)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pages',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True)
    a=p.parse_args();register(a.pages,json.loads(a.manifest.read_text()))
