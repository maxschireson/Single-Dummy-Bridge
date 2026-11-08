#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Measure certified full-domain strategy frontiers and outcome partitions."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.core import Contract
from bridge_harness.partitions import EndingDomain, certify_domain
from bridge_harness.strategy import Policy, evaluate_policy
from scripts.benchmark_strategies import family


def pack_witnesses(policies):
    """Measurement format only: intern equal policy suffixes, then compress JSON.

    This payload omits domain, model, outcomes and proof metadata; it is not a
    stand-alone cache certificate. Node IDs are local to this payload.
    """
    ids={};nodes=[];objects={}
    def visit(p):
        if id(p) in objects:return objects[id(p)]
        key=(p.kind,p.card,tuple((c,visit(q)) for c,q in p.children))
        if key not in ids:
            ids[key]=len(nodes);nodes.append(key)
        objects[id(p)]=ids[key]
        return ids[key]
    roots=[visit(p) for p in policies]
    raw=json.dumps(dict(nodes=nodes,roots=roots),separators=(',',':')).encode()
    return zlib.compress(raw),len(nodes),len(raw)


def unpack_witnesses(payload):
    data=json.loads(zlib.decompress(payload));nodes=[]
    for kind,card,children in data['nodes']:
        nodes.append(Policy(kind,card,tuple((c,nodes[i]) for c,i in children)))
    return tuple(nodes[i] for i in data['roots'])


def main():
    p=argparse.ArgumentParser();p.add_argument('--count',type=int,default=100);p.add_argument('--out',required=True);a=p.parse_args()
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True);rows=[]
    with dest.open('w') as f:
        for i in range(a.count):
            anchor=family(940001+i,3,1)[0]
            cert,stats=certify_domain(EndingDomain(anchor,2),Contract(6,'NSHDC'[i%5],2))
            seen=set();edges=0
            def visit(policy):
                nonlocal edges
                if id(policy) in seen:return
                seen.add(id(policy));edges+=len(policy.children)
                for _,child in policy.children:visit(child)
            for s in cert.strategies:visit(s.policy)
            packed,structural_nodes,raw_bytes=pack_witnesses(s.policy for s in cert.strategies)
            decoded=unpack_witnesses(packed)
            for s,p in zip(cert.strategies,decoded,strict=True):
                for w in cert.worlds:
                    if evaluate_policy(w,p,cert.contract,lambda t:t)!=s.partition.value(w):
                        raise AssertionError('Compressed witness round trip changed strategy outcome')
            cells=[len(s.partition.cells) for s in cert.strategies]
            row=dict(id=i,worlds=len(cert.worlds),strategies=len(cert.strategies),cells=cells,
                predicates=[sum(len(c.conditions) for c in s.partition.cells) for s in cert.strategies],
                policy_dag_nodes=len(seen),policy_dag_edges=edges,
                structural_dag_nodes=structural_nodes,witness_json_bytes=raw_bytes,
                witness_zlib_bytes=len(packed),
                illustrative_dag_bytes=16*len(seen)+8*edges,seconds=stats['seconds'])
            if i<3:
                row['partitions']=[[[[(p.text(),v) for p,v in c.conditions],c.outcome,len(c.indices)] for c in s.partition.cells] for s in cert.strategies]
            rows.append(row);f.write(json.dumps(row)+'\n');f.flush()
            if (i+1)%10==0:print(f'{i+1}/{a.count} complete full-domain certificates',flush=True)
    cells=[c for r in rows for c in r['cells']]
    summary=dict(families=len(rows),worlds=sum(r['worlds'] for r in rows),
        strategies=sum(r['strategies'] for r in rows),mean_strategies=statistics.mean(r['strategies'] for r in rows),
        max_strategies=max(r['strategies'] for r in rows),mean_cells_per_strategy=statistics.mean(cells),max_cells=max(cells),
        constant_outcome_strategies=sum(c==1 for c in cells),
        mean_dag_nodes=statistics.mean(r['policy_dag_nodes'] for r in rows),
        mean_structural_dag_nodes=statistics.mean(r['structural_dag_nodes'] for r in rows),
        mean_witness_json_bytes=statistics.mean(r['witness_json_bytes'] for r in rows),
        mean_witness_zlib_bytes=statistics.mean(r['witness_zlib_bytes'] for r in rows),
        max_witness_zlib_bytes=max(r['witness_zlib_bytes'] for r in rows),
        mean_illustrative_dag_bytes=statistics.mean(r['illustrative_dag_bytes'] for r in rows),
        max_illustrative_dag_bytes=max(r['illustrative_dag_bytes'] for r in rows),
        mean_seconds=statistics.mean(r['seconds'] for r in rows))
    dest.with_suffix('.summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
