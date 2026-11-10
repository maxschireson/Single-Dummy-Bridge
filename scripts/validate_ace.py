"""Cross-check ACE observation replay and its native DD evaluator."""
import os,sys,random,json
from pathlib import Path
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT.parent
sys.path[:0]=[str(ROOT),str(BASE/'python-deps')]
os.environ['DOTNET_ROOT']=str(BASE/'dotnet')
from pythonnet import load
load('coreclr')
import clr
clr.AddReference(str(ROOT/'vendor/ace/Ace.dll'))
from Ace import Game as AG, GameOptions, Extensions, Contract as AC, ConstraintSet, Engine, Config
from bridge_harness.core import Game,Contract,hand_text,symbol,card
from bridge_harness.bidding_env import make_board
from bridge_harness.dds import DDS
from bridge_harness.ace_player import rank_evaluations

dd=DDS(cache_path='');positions=solves=0
for strain in 'SHDCN':
    for declarer in range(4):
        b=replace(make_board(202611101015,declarer,'dev'),contract=Contract(3,strain,declarer))
        g=Game(b);rng=random.Random(54)
        while not g.done:
            o=g.observation();opts=GameOptions()
            opts.Deal=' '.join(hand_text(o.original_hand(s)) if h is not None else '...'
                               for s,h in enumerate(o.known_hands))
            opts.Declarer=Extensions.Player(declarer);opts.Contract=AC.Parse('3'+('NT' if strain=='N' else strain))
            opts.Constraints=ConstraintSet();ag=AG.New(opts)
            for _,c in o.history:assert ag.Play(symbol(c),False)
            assert {card(str(c)) for c in ag.GetMoves()}==set(o.legal)
            ag.Dispose();positions+=1
            if len(o.history) in (24,39) and len(o.legal)>1:
                # All-known fixtures solely for checking native score semantics;
                # the match adapter never receives these fixture hands.
                opts.Deal=' '.join(hand_text(h) for h in b.hands);ag=AG.New(opts)
                for _,c in o.history:assert ag.Play(symbol(c),False)
                e=Engine.New(1);e.SetGame(ag);e.SetIterations(1);e.SetSeed(55)
                cfg=Config();cfg.Limiter=False;e.Search(10000,10000,4,cfg).Wait()
                ranked=rank_evaluations(e.Evaluate())
                evaluated={card(str(v.Move)):v for v in ranked}
                expected,_=dd.solve(tuple(tuple(sorted(h)) for h in g.hands),o.contract.trump,o.leader,o.trick)
                declaring=o.actor%2==declarer%2
                for c,t in expected.items():
                    total=o.declarer_tricks+(t if declaring else 13-len(o.history)//4-t)
                    win=(total>=9) if declaring else (total<9)
                    margin=(total-9)*(1 if declaring else -1)
                    assert c in evaluated,(strain,declarer,len(o.history),c)
                    ev=evaluated[c]
                    assert abs(ev.Winrate-int(win))<1e-9,(strain,declarer,len(o.history),symbol(c),'win',ev.Winrate,win)
                    assert abs(ev.Utility-margin)<1e-9,(strain,declarer,len(o.history),symbol(c),'utility',ev.Utility,margin)
                best=max(expected.values())
                assert expected[card(str(ranked[0].Move))]==best,('native ranking',strain,declarer,len(o.history),[(str(v.Move),v.Winrate,v.Utility,v.Visits,expected[card(str(v.Move))]) for v in ranked])
                ag.Dispose();solves+=1
            g.play(rng.choice(o.legal))
dd.close()
result=dict(observation_positions=positions,native_dd_positions=solves,
            chosen_move_dd_positions=solves,all_passed=True)
(ROOT/'runs/ace-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
