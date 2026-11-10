"""Replay, audit and summarize independent paired confirmation games."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.selfplay import atomic_json
from scripts.belief_play_smoke import summarize

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();summarize(a)
    r=json.loads((a.run/'result.json').read_text());mean,se=r['mean_imps'],r['se_imps']
    r['ci95_imps']=[mean-1.96*se,mean+1.96*se] if se is not None else None
    r['evaluation_only']=True;r['fixed_target']=True;r['promoted']=False
    r['interpretation']='Independent fresh deal families; two swapped tables per family; positive IMPs favor the frozen candidate; common/native counted once. Final fixed-horizon interval.' if r['complete'] else 'Incomplete fixed-horizon confirmation; interim interval is descriptive. Positive IMPs favor the frozen candidate; common/native counted once.'
    atomic_json(a.run/'result.json',r)
if __name__=='__main__':main()
