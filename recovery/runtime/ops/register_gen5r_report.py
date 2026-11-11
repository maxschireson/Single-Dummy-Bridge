"""Register a frozen, published Gen5R cohort in a clean gh-pages checkout."""
import argparse
import json
from pathlib import Path
import re

def once(text,old,new):
    if text.count(old)!=1:raise ValueError('Dashboard template changed: '+old[:70])
    return text.replace(old,new,1)

def register(pages,manifest):
    if manifest.get('variant')!='5R' or not re.fullmatch('[0-9a-f]{64}',manifest['identity']):
        raise ValueError('Expected immutable Gen5R manifest')
    pages=Path(pages);files={name:(pages/'arena'/name).read_text() for name in
        ('reporting.js','supplemental.js','decision-timing.js','replays/common.js','replays/list.js')}
    r=files['reporting.js']
    if "key:'gen5r'" in r:raise ValueError('Gen5R already registered; inspect existing cohort')
    entry="  {key:'gen5r',generation:5,variant:'5R',environment:'codex',name:'Gen 5R · current round',branch:'arena-gen5r-feed',cohort:'"+manifest['identity']+"'},\n"
    r=once(r,' const sources=[\n',' const sources=[\n'+entry)
    r=once(r,"{key:'gen5',generation:5,environment:","{key:'gen5',generation:5,retired:true,environment:")
    r=once(r,"name:'Gen 5 · current round'","name:'Gen 5 · previous round'")
    r=once(r," const labels={"," const labels={'5R32':'Gen 5R (32)','5R192':'Gen 5R (192)',")
    r=once(r,"order=['5','5-32'","order=['5R32','5R192','5','5-32'")
    r=once(r,"scope==='gen5'&&s.generation===5","scope==='gen5'&&s.generation===5&&s.variant!=='5R'")
    r=once(r,"model_note:chosen.some(x=>x.source.generation===5)?",
        "model_note:chosen.some(x=>x.source.variant==='5R')?'Gen5R keeps Gen5 networks and changes only 10–13-trick layout selection and belief-moment weights. Pools 128/768; DDS ceilings 32/192. Original Gen5 (32) is the random-sampling control. Smaller positions are unchanged. Common and native bidding remain separate.':chosen.some(x=>x.source.generation===5)?")
    files['reporting.js']=r
    s=files['supplemental.js']
    s=once(s,"get('source')||'gen5'","get('source')||'gen5r'")
    s=once(s,"selected!=='gen5'","selected!=='gen5r'")
    s=s.replace("R.pickSources('gen5')","R.pickSources('gen5r')")
    s=once(s,"older||x.source.generation===5","older||x.source.key==='gen5r'")
    s=once(s,"selected=older?'all':'gen5'","selected=older?'all':'gen5r'")
    s=s.replace('Gen 5 collection','Gen 5R collection').replace('Loading Gen 5 results','Loading Gen 5R results')
    s=once(s,'<option value="gen5">Gen 5 · current generation</option>',
        '<option value="gen5r">Gen 5R · current round</option><option value="gen5">Gen 5 · previous round</option>')
    s=once(s,'Only Gen 5 games are counted here. ','Only Gen 5R games are counted here. ')
    files['supplemental.js']=s
    t=files['decision-timing.js']
    start=t.index('<p class="muted">Gen 5 round:');end=t.index('</p>',start)+4
    t=t[:start]+'<p class="muted">Gen 5R allocation: 40% vs 4b, 20% vs 3, 15% vs 2, 5% vs 1, 5% vs BEN, 7.5% R32 vs R192, and 7.5% R32 vs original 5-32. Representative selection applies only at 10–13 tricks remaining. Nominal 32/192 are DDS ceilings.</p>'+t[end:]
    files['decision-timing.js']=t
    c=files['replays/common.js']
    c=once(c,"const labels = {","const labels = {'5R32':'Gen 5R (32)','5R192':'Gen 5R (192)',")
    c=once(c,"const urls=[","const urls=['https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/arena-gen5r-feed/arena/replays/catalog.json',")
    files['replays/common.js']=c
    files['replays/list.js']=once(files['replays/list.js'],"Object.hasOwn(data.labels,'5'))","Object.hasOwn(data.labels,'5')||Object.hasOwn(data.labels,'5R32'))")
    # Validate every template before writing any changed file.
    for name,content in files.items():(pages/'arena'/name).write_text(content)
    return list(files)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pages',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);a=p.parse_args()
    print(json.dumps(register(a.pages,json.loads(a.manifest.read_text()))))
