from dataclasses import replace
from functools import lru_cache
import json
import random
import threading
import time
import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from bridge_harness.core import *
from bridge_harness.corpus import generate, read_pbn, write_pbn, freeze_auction
from bridge_harness.sampling import Sampler, allocations, ways
from bridge_harness.players import RandomPlayer, GreedyPlayer, PIMCPlayer, BenPlayer, Decision
from bridge_harness.runner import run_pair, replay, play_table, isolated_pair
from bridge_harness.report import summarize, trick_difference


class CoreTests(unittest.TestCase):
    def test_cards_roundtrip(self):
        for c in range(52): self.assertEqual(card(symbol(c)),c)
        for b in generate(10):
            for h in b.hands:self.assertEqual(parse_hand(hand_text(h)),h)

    def test_scores(self):
        cases=[('3N',9,False,400),('3N',10,True,630),('4S',10,False,420),
               ('5C',11,True,600),('6N',12,False,990),('7N',13,True,2220),
               ('2HX',8,False,470),('2HXX',8,True,840),('1NXX',8,False,760),
               ('4SX',9,False,-100),('4SX',8,False,-300),('4SX',7,False,-500),
               ('4SX',6,False,-800),('4SX',6,True,-1100),('4SXX',6,True,-2200),
               ('4S',8,True,-200),('2D',9,False,110)]
        for ct,t,v,expected in cases:
            with self.subTest(ct=ct,t=t,v=v):self.assertEqual(score(Contract.parse(ct,0),t,v),expected)

    def test_imp_boundaries(self):
        for i,x in enumerate(IMP_LIMITS):
            self.assertEqual(imps(x),i+1);self.assertEqual(imps(x-1),i)
            self.assertEqual(imps(-x),-(i+1))

    def test_auction(self):
        self.assertEqual(auction_contract(0,['1H','PASS','2H','PASS','4H','X','XX','PASS','PASS','PASS']),Contract(4,'H',0,2))
        self.assertIsNone(auction_contract(2,['PASS']*4))
        for bad in (['1S','1H'],['1H','PASS','X'],['1H','XX'],['PASS']*4+['1C']):
            with self.assertRaises(ValueError):auction_contract(0,bad)
        for d in range(4):
            for s in range(4):
                for x in range(3):
                    c=Contract(3,'N',s,x)
                    self.assertEqual(auction_contract(d,synthetic_auction(d,c)),c)

    def test_observation_boundary(self):
        b=next(generate(1));g=Game(b);o=g.observation()
        self.assertEqual(sum(h is not None for h in o.known_hands),1)
        self.assertFalse(hasattr(o,'board'))
        self.assertFalse(hasattr(o,'seed'))
        g.play(o.legal[0]);o=g.observation()
        self.assertEqual(o.actor,b.contract.dummy)
        self.assertEqual(o.controller,b.contract.declarer)
        self.assertEqual(sum(h is not None for h in o.known_hands),2)
        self.assertEqual(o.original_hand(o.controller),b.hands[o.controller])
        with self.assertRaises(ValueError):o.original_hand((o.controller+1)%4)

    def test_same_observation_different_world(self):
        a,b=list(generate(2,family_size=2))
        # Same N/S, same observed lead chosen from the intersection of West holdings.
        lead=next(iter(set(a.hands[3])&set(b.hands[3])))
        ga,gb=Game(a),Game(b);ga.play(lead);gb.play(lead)
        self.assertEqual(ga.observation(),gb.observation())

    def test_follow_suit_and_trump(self):
        self.assertEqual(winner(((0,card('SA')),(1,card('H2')),(2,card('SK')),(3,card('HA'))),1),3)
        self.assertEqual(winner(((0,card('SA')),(1,card('H2')),(2,card('SK')),(3,card('HA'))),4),0)
        b=next(generate(1));g=Game(b);g.play(g.observation().legal[0]);o=g.observation()
        off=[c for c in g.hands[o.actor] if c not in o.legal]
        if off:
            with self.assertRaises(ValueError):g.play(off[0])

    def test_complete_legal_games(self):
        for b in generate(100,seed=47):
            g=Game(b);rng=random.Random(1)
            while not g.done:
                o=g.observation();g.play(rng.choice(o.legal))
            self.assertEqual(len(g.history),52)
            self.assertEqual(len(set(c for _,c in g.history)),52)
            self.assertTrue(0<=g.declarer_tricks<=13)

    def test_passed_out(self):
        b=replace(next(generate(1)),contract=None,auction=('PASS',)*4)
        r=run_pair(b,dict(candidate='random',baseline='greedy',common='greedy'))
        self.assertEqual(r['imps'],0);self.assertEqual(r['tables'][0]['actions'],[])

    def test_pbn_roundtrip(self):
        boards=list(generate(20,family_size=5))
        for b in boards:
            copy=next(read_pbn(write_pbn(b)))
            self.assertEqual(b.to_dict(),copy.to_dict())
        self.assertEqual(len(list(read_pbn('\n\n'.join(write_pbn(b) for b in boards)))),20)

    def test_family_fixed_ns(self):
        bs=list(generate(8,family_size=4))
        self.assertEqual(bs[0].hands[0],bs[3].hands[0])
        self.assertEqual(bs[0].hands[2],bs[3].hands[2])
        self.assertNotEqual(bs[0].hands[1],bs[3].hands[1])


class SamplerTests(unittest.TestCase):
    def test_all_positions_consistent(self):
        rng=random.Random(61)
        for b in generate(15,seed=8):
            g=Game(b)
            while not g.done:
                o=g.observation();s=Sampler(o)
                for _ in range(2):
                    h=s.draw(rng)
                    self.assertEqual(set(sum(h,()))|{c for _,c in o.history},set(range(52)))
                    for seat in range(4):
                        self.assertEqual(len(h[seat]),len(g.hands[seat]))
                        if o.known_hands[seat] is not None:self.assertEqual(h[seat],o.known_hands[seat])
                    for i,(seat,c) in enumerate(o.history):
                        led=o.history[i-i%4][1]//13
                        if c//13!=led:self.assertTrue(all(x//13!=led for x in h[seat]))
                g.play(rng.choice(o.legal))

    def test_uniform_late_deals(self):
        # Find a late position with few legal worlds, then check sampled world frequencies.
        rng=random.Random(75)
        for b in generate(30,seed=71):
            g=Game(b)
            while len(g.history)<44:g.play(rng.choice(g.observation().legal))
            s=Sampler(g.observation())
            expected=s.count(0,s.caps)
            if 2<=expected<=6:break
        self.assertTrue(2<=expected<=6)
        counts={}
        for _ in range(6000):
            h=s.draw(rng);counts[h]=counts.get(h,0)+1
        self.assertEqual(len(counts),expected)
        self.assertLess(max(abs(v-6000/expected) for v in counts.values()),160)


def exhaustive(hands,trump,leader,trick):
    actor=(leader+len(trick))%4
    target=actor%2
    @lru_cache(None)
    def rec(hands,leader,trick):
        if not any(hands):
            return int(winner(trick,trump)%2==target) if trick else 0
        seat=(leader+len(trick))%4
        legal=[c for c in hands[seat] if not trick or c//13==trick[0][1]//13] or list(hands[seat])
        vals=[]
        for c in legal:
            h=list(hands);h[seat]=tuple(x for x in h[seat] if x!=c)
            t=trick+((seat,c),)
            if len(t)==4:
                w=winner(t,trump);v=int(w%2==target)+rec(tuple(h),w,())
            else:v=rec(tuple(h),leader,t)
            vals.append(v)
        return (max if seat%2==target else min)(vals)
    legal=[c for c in hands[actor] if not trick or c//13==trick[0][1]//13] or list(hands[actor])
    result={}
    for c in legal:
        h=list(hands);h[actor]=tuple(x for x in h[actor] if x!=c)
        t=trick+((actor,c),)
        if len(t)==4:
            w=winner(t,trump);v=int(w%2==target)+rec(tuple(h),w,())
        else:v=rec(tuple(h),leader,t)
        result[c]=v
    return result


class DDSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from bridge_harness.dds import DDS
        try:cls.dds=DDS()
        except RuntimeError as e:raise unittest.SkipTest(str(e))

    @classmethod
    def tearDownClass(cls):cls.dds.close()

    def test_dds_against_exhaustive_all_trick_offsets(self):
        rng=random.Random(17)
        for b in generate(25,seed=16):
            g=Game(b)
            while len(g.history)<40:g.play(rng.choice(g.observation().legal))
            while not g.done:
                o=g.observation();h=tuple(tuple(sorted(x)) for x in g.hands)
                actual,_=self.dds.solve(h,o.contract.trump,o.leader,o.trick)
                self.assertEqual(actual,exhaustive(h,o.contract.trump,o.leader,o.trick))
                g.play(rng.choice(o.legal))

    def test_pimc_full_games(self):
        for b in generate(4,seed=29):
            r=run_pair(b,dict(candidate='pimc',baseline='greedy',common='greedy',samples=2,mode='partnership'))
            self.assertEqual(r['status'],'ok',r)
            replay(r)


class HarnessTests(unittest.TestCase):
    def test_paired_tricks_orientation(self):
        for mode in ('declarer','defence','partnership'):
            for declarer in SEATS:
                r=dict(board=dict(contract='3N',declarer=declarer),config=dict(mode=mode),
                       tables=[dict(declarer_tricks=10),dict(declarer_tricks=8)])
                expected=-2 if mode=='defence' or (mode=='partnership' and declarer in 'EW') else 2
                self.assertEqual(trick_difference(r),expected)
        r['board']['contract']=None
        self.assertEqual(trick_difference(r),0)

    def test_self_matches_zero_and_replay(self):
        for mode in ('declarer','defence','partnership'):
            for b in generate(8):
                r=run_pair(b,dict(candidate='random',baseline='random',common='greedy',mode=mode))
                self.assertEqual(r['status'],'ok',r)
                self.assertEqual(r['imps'],0)
                self.assertIsNone(r['first_difference'])
                replay(r)

    def test_comparison_sign(self):
        for b in generate(8):
            for mode in ('declarer','defence','partnership'):
                r=run_pair(b,dict(candidate='greedy',baseline='random',common='random',mode=mode))
                a,z=r['tables'];delta=a['ns_score']-z['ns_score']
                sign=1 if mode=='partnership' else (1 if b.contract.declarer%2==0 else -1)*(1 if mode=='declarer' else -1)
                self.assertEqual(r['score_difference'],sign*delta)

    def test_bad_player_is_recorded(self):
        class Bad:
            def choose(self,o,rng):return Decision(100)
        r=play_table(next(generate(1)),['bad']*4,{'bad':Bad()})
        self.assertEqual(r['status'],'error')
        self.assertEqual(r['actions'],[])

    def test_hard_deadline(self):
        r=isolated_pair(next(generate(1)),dict(candidate='random',baseline='greedy'),deadline=.0001)
        self.assertEqual(r['status'],'timeout')

    def test_family_cluster_count(self):
        rs=[run_pair(b,dict(candidate='random',baseline='greedy')) for b in generate(12,family_size=4)]
        self.assertEqual(summarize(rs)['independent_clusters'],3)

    def test_resume_prefix(self):
        b=next(generate(1));ps={'random':RandomPlayer()}
        a=play_table(b,['random']*4,ps,seed=919)
        z=play_table(b,['random']*4,ps,seed=919,prefix=a['actions'][:17])
        self.assertEqual([x['card'] for x in a['actions']],[x['card'] for x in z['actions']])


class BenAdapterTests(unittest.TestCase):
    def test_freeze_resume_preserves_completed_auction(self):
        from bridge_harness.cli import main
        from bridge_harness.corpus import save, load
        class PassBidder:
            def __init__(self): self.calls=0
            def bid(self,*args):
                self.calls+=1
                return 'PASS',{}
        with TemporaryDirectory() as directory:
            source=Path(directory)/'source.jsonl';out=Path(directory)/'frozen.jsonl'
            boards=list(generate(3,seed=843));save(boards[:1],source)
            bidder=PassBidder()
            with patch('bridge_harness.cli.BenPlayer',return_value=bidder):
                main(['freeze-auctions',str(source),str(out)])
                prefix=out.read_bytes();self.assertEqual(bidder.calls,4)
                save(boards,source)
                main(['freeze-auctions',str(source),str(out),'--resume'])
                self.assertEqual(bidder.calls,12)
                self.assertTrue(out.read_bytes().startswith(prefix))
                self.assertEqual(len(load(out)),3)
                save(list(generate(3,seed=844)),source)
                with self.assertRaisesRegex(ValueError,'original deal'):
                    main(['freeze-auctions',str(source),str(out),'--resume'])
                self.assertEqual(bidder.calls,12)

    def test_request_visibility_and_controller(self):
        b=next(generate(1));g=Game(b);g.play(g.observation().legal[0]);o=g.observation()
        p=BenPlayer();seen=[]
        def fake(endpoint,params):
            seen.append((endpoint,params));return {'card':symbol(o.legal[0])}
        p.request=fake;p.choose(o,random.Random(1))
        ep,d=seen[0]
        self.assertEqual(ep,'play');self.assertEqual(d['seat'],SEATS[o.controller])
        self.assertEqual(parse_hand(d['hand']),b.hands[o.controller])
        self.assertEqual(parse_hand(d['dummy']),b.hands[o.contract.dummy])
        self.assertNotIn('deal',d)

    def test_http_roundtrip(self):
        seen=[]
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append(parse_qs(urlparse(self.path).query))
                self.send_response(200);self.end_headers();self.wfile.write(b'{"bid":"1N"}')
            def log_message(self,*args):pass
        server=HTTPServer(('127.0.0.1',0),Handler)
        t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        try:
            b=next(generate(1));p=BenPlayer(f'http://127.0.0.1:{server.server_port}')
            bid,_=p.bid(b.hands[0],0,0,'Both',[])
            self.assertEqual(bid,'1N');self.assertEqual(seen[0]['vul'],['Both'])
        finally:server.shutdown();server.server_close();t.join()


if __name__=='__main__':unittest.main()
