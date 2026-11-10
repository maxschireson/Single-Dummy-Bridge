"""ACE 1.0.5 cardplay through a private-information-only adapter.

The supplied belief net is translated into broad ORIGINAL-hand HCP/shape
ranges; ACE samples and searches within those ranges. It does not consume our
full card-location probabilities. No hidden deal or deal-generation seed enters.
"""
from pathlib import Path
import os
import time

from .core import card, symbol, hand_text
from .players import Decision
from .bidding_sampling import WeightedSampler
from .belief_capacity import Weights


def rank_evaluations(evaluations):
    """Prefer ACE's contract-success estimate, then its trick-margin estimate.

    Evaluate() is not best-first. Its native CompareTo uses visits and depth,
    which can tie for every candidate. Both value signals are from the actor.
    """
    return sorted(evaluations,key=lambda v:(float(v.Winrate),float(v.Utility)),reverse=True)


class ACEPlayer:
    def __init__(self, belief, milliseconds=200, lead_milliseconds=1000,
                 depth=4, iterations=0):
        from pythonnet import load
        load('coreclr')
        import clr
        folder = Path(os.environ['ACE_DIR'])
        clr.AddReference(str(folder/'Ace.dll'))
        from Ace import Engine, Game, GameOptions, ConstraintSet, Range, Config, Contract, Extensions, Library
        self.Engine, self.Game, self.Options = Engine, Game, GameOptions
        self.ConstraintSet, self.Range, self.Config = ConstraintSet, Range, Config
        self.Contract, self.Player = Contract, Extensions.Player
        self.version = str(Library.Version)
        self.belief = Weights(belief)
        self.ms, self.lead_ms, self.depth = milliseconds, lead_milliseconds, depth
        self.iterations = iterations

    def choose(self, o, rng):
        if len(o.legal) == 1:
            return Decision(o.legal[0], dict(forced=True, engine='ACE', iterations=0))
        start = time.perf_counter()
        seed = rng.randrange(1, 2**31-1)
        sampler = WeightedSampler(o, self.belief.logits(o), 1.)
        worlds = [sampler.draw(rng) for _ in range(32)]
        played = [tuple(c for s,c in o.history if s == seat) for seat in range(4)]
        cs = self.ConstraintSet()
        bounds = {}
        for seat, visible in enumerate(o.known_hands):
            if visible is not None:
                continue
            originals = [tuple(h[seat])+played[seat] for h in worlds]
            vals = [[sum(c//13 == suit for c in h) for suit in range(4)] +
                    [sum(max(0,c%13-8) for c in h)] for h in originals]
            ranges = []
            constraint = cs[self.Player(seat)]
            for i,name in enumerate(('Spades','Hearts','Diamonds','Clubs','Hcp')):
                margin,maximum = (1,13) if i<4 else (2,37)
                lo=max(0,min(v[i] for v in vals)-margin)
                hi=min(maximum,max(v[i] for v in vals)+margin)
                setattr(constraint,name,self.Range(lo,hi));ranges.append([lo,hi])
            bounds[str(seat)] = ranges
        options=self.Options()
        options.Deal=' '.join(hand_text(o.original_hand(s)) if h is not None else '...'
                              for s,h in enumerate(o.known_hands))
        options.Declarer=self.Player(o.contract.declarer)
        # ACE objective ignores vulnerability and doubling: contract success,
        # then trick margin. The harness still scores actual duplicate IMPs.
        options.Contract=self.Contract.Parse(f'{o.contract.level}'+
                            ('NT' if o.contract.strain=='N' else o.contract.strain))
        options.Constraints=cs
        game=self.Game.New(options)
        try:
            for _,c in o.history:
                if not game.Play(symbol(c),False):
                    raise RuntimeError('ACE rejected a public-history card')
            legal={card(str(c)) for c in game.GetMoves()}
            if legal != set(o.legal):
                raise RuntimeError(f'ACE legal move mismatch: {legal} != {set(o.legal)}')
            engine=self.Engine.New(1)
            engine.SetGame(game);engine.SetSeed(seed)
            if self.iterations:engine.SetIterations(self.iterations)
            config=self.Config();config.Exploration=.0058;config.Limiter=False
            duration=self.lead_ms if not o.history else self.ms
            prep=time.perf_counter()-start
            engine.Search(duration,max(duration,1000),self.depth,config).Wait()
            evaluations=rank_evaluations(engine.Evaluate())
            retry=False
            if not evaluations:
                # Keep the same inference and allow more time to obtain a valid
                # root evaluation. Never silently substitute another player.
                retry=True
                engine.Continue(max(duration,1000),1000,config).Wait()
                evaluations=rank_evaluations(engine.Evaluate())
            if not evaluations:raise RuntimeError('ACE produced no evaluated move')
            result=[]
            for ev in evaluations:
                c=card(str(ev.Move))
                if c not in legal:raise RuntimeError('ACE returned an illegal move')
                result.append(dict(card=symbol(c),visits=int(ev.Visits),depth=int(ev.Depth),
                                   winrate=float(ev.Winrate),utility=float(ev.Utility)))
            return Decision(card(result[0]['card']),dict(engine='ACE',ace_version=self.version,
                iterations=int(engine.Iterations),search_ms=float(engine.Elapsed.TotalMilliseconds),
                budget_ms=duration,depth=self.depth,threads=1,preparation_seconds=prep,
                retry=retry,constraints=bounds,evaluations=result,visible_seats=[s for s,h in enumerate(o.known_hands) if h is not None]))
        finally:
            game.Dispose()

    def close(self):
        pass
