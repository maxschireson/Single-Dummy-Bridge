#!/usr/bin/env python3
"""Extract original self-play deals, preserving seats, dealer, vulnerability, splits."""
import argparse
import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.core import Board
from bridge_harness.training import digest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--chunks',type=Path,nargs='+',required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():raise ValueError('Refuse overwrite')
    args.out.mkdir(parents=True);index={}
    with (args.out/'original-corpus.jsonl').open('x') as f:
        for chunk in args.chunks:
            for path in sorted((chunk/'episodes').glob('*.json.gz')):
                with gzip.open(path,'rt') as g:e=json.load(g)
                if e['record']['status']!='ok':raise ValueError('Incomplete original episode')
                b=Board.from_dict(e['record']['board']);h=digest(b.hands)
                if h in index:raise ValueError('Duplicate original deal')
                d=b.to_dict();d['id']=h
                f.write(json.dumps(d)+'\n');index[h]=str(path.resolve())
    if not index:raise ValueError('No original episodes')
    (args.out/'source-index.json').write_text(json.dumps(index,indent=2))
    print(json.dumps({'deals':len(index)}))


if __name__=='__main__':main()
