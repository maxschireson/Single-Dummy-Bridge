import json, sys
r=json.load(open(sys.argv[1])); stages=sys.argv[2].split(',') if len(sys.argv)>2 else ['all tricks']; nets=sys.argv[3].split(',') if len(sys.argv)>3 else [k for k in r if k!='between nets']
for net in nets:
    for key,line in r[net].items():
        if key.split(' | ')[0] not in stages: continue
        print(f"\n{net} | {key}: {line['pairs']} pairs, {line['deals']} deals, T better {line['t_better']:.1%}, S better {line['s_better']:.1%}, always T {line['cost_of_t'][0]:+.4f}±{line['cost_of_t'][1]:.4f} tr, {line['cost_of_t_imps'][0]:+.3f}±{line['cost_of_t_imps'][1]:.3f} IMPs, mean gap {line['mean_search_gap']:.3f}")
        for s,v in line['selectors'].items():
            print(f"   {s:24s} T {v['plays_t']:6.1%} | then {v['cost_of_t_then'][0]:+.4f}±{v['cost_of_t_then'][1]:.4f} | gain {v['gain'][0]:+.5f}±{v['gain'][1]:.5f} tr ({v['gain'][0]/v['gain'][1] if v['gain'][1] else 0:+.1f}se), {v['gain_imps'][0]:+.4f}±{v['gain_imps'][1]:.4f} IMPs ({v['gain_imps'][0]/v['gain_imps'][1] if v['gain_imps'][1] else 0:+.1f}se) | over policy {v['gain_over_policy'][0]:+.5f}±{v['gain_over_policy'][1]:.5f}")
for k,v in r.get('between nets',{}).items(): print(k, v['pairs'], f"differ {v['picks_differ']:.1%}", f"{v['gain_difference'][0]:+.5f}±{v['gain_difference'][1]:.5f}")
