# SPDX-License-Identifier: Apache-2.0
"""Scoped outcome partitions for executable strategies, not hidden-card policies.

A predicate here classifies a hypothetical world for EVALUATION. It never tells
an actor which action to take. Actions still come from the information-consistent
policy witness. Certificates cover a finite, completely enumerated domain only;
no extrapolation to unverified layouts, histories, or opponent models is implied.
"""
from dataclasses import dataclass
from itertools import combinations

from .core import symbol
from .strategy import AlphaMu, Position, evaluate_policy, validate_worlds


@dataclass(frozen=True)
class EndingDomain:
    anchor: Position
    declarer: int
    voids: frozenset[tuple[int,int]] = frozenset()

    def worlds(self):
        validate_worlds([self.anchor],[1],self.declarer)
        if self.anchor.trick:
            raise ValueError('Domain enumeration currently requires a trick boundary')
        defenders=tuple(s for s in range(4) if s%2!=self.declarer%2)
        a,b=defenders
        if any(s not in defenders or suit not in range(4) for s,suit in self.voids):
            raise ValueError('Void constraints must describe a defender and valid suit')
        pool=tuple(sorted(self.anchor.hands[a]+self.anchor.hands[b])); result=[]
        for split in combinations(pool,len(self.anchor.hands[a])):
            h=list(self.anchor.hands);h[a]=split;h[b]=tuple(c for c in pool if c not in split)
            if any(any(c//13==suit for c in h[seat]) for seat,suit in self.voids):continue
            result.append(Position(tuple(h),self.anchor.leader,(),self.anchor.tricks))
        if not result:raise ValueError('Empty domain')
        return tuple(result)


@dataclass(frozen=True)
class Predicate:
    kind: str
    seat: int
    value: int  # card for owns; suit for length_ge
    threshold: int = 0

    def test(self,world):
        if self.kind=='owns':return self.value in world.hands[self.seat]
        if self.kind=='length_ge':return sum(c//13==self.value for c in world.hands[self.seat])>=self.threshold
        raise ValueError('Unknown predicate')

    def text(self):
        from .core import SEATS, SUITS
        if self.kind=='owns':return f'{SEATS[self.seat]} holds {symbol(self.value)}'
        return f'{SEATS[self.seat]} has at least {self.threshold} {SUITS[self.value]}'


@dataclass(frozen=True)
class OutcomeCell:
    conditions: tuple[tuple[Predicate,bool],...]
    outcome: float
    indices: tuple[int,...]


@dataclass(frozen=True)
class OutcomePartition:
    cells: tuple[OutcomeCell,...]
    support: frozenset[Position]

    def value(self,world):
        if world not in self.support:
            raise ValueError('World outside validated domain; generalization is unproved')
        matches=[c.outcome for c in self.cells if all(p.test(world)==truth for p,truth in c.conditions)]
        if len(matches)!=1:raise AssertionError('Partition must be exhaustive and disjoint on its domain')
        return matches[0]

    def weighted_value(self,weights):
        """Weights follow CertifiedFrontier.worlds order, including zero mass."""
        if len(weights)!=len(self.support):raise ValueError('Wrong weight vector size')
        from math import isfinite
        if any(not isfinite(w) or w<0 for w in weights) or not isfinite(sum(weights)) or sum(weights)<=0:
            raise ValueError('Invalid weights')
        return sum(c.outcome*sum(weights[i] for i in c.indices) for c in self.cells)/sum(weights)


def partition_outcomes(worlds,values,declarer):
    """Greedy semantic tree, checked exactly on all supplied domain members."""
    if not worlds or len(worlds)!=len(values) or len(set(worlds))!=len(worlds):raise ValueError('Need nonempty unique worlds and aligned outcomes')
    seat=(declarer+1)%4
    pool=sorted({c for w in worlds for s,h in enumerate(w.hands) if s%2!=declarer%2 for c in h},key=lambda c:(-(c%13),c//13))
    predicates=[Predicate('length_ge',seat,s,k) for s in range(4) for k in range(1,len(worlds[0].hands[seat])+1)]
    predicates += [Predicate('owns',seat,c) for c in pool]
    leaves=[]
    def impurity(indices):
        from collections import Counter
        counts=Counter(values[i] for i in indices)
        return len(indices)-sum(n*n for n in counts.values())/len(indices)
    def split(indices,conditions):
        if len({values[i] for i in indices})==1:
            leaves.append(OutcomeCell(conditions,values[indices[0]],indices));return
        candidates=[]
        for rank,p in enumerate(predicates):
            yes=tuple(i for i in indices if p.test(worlds[i]));no=tuple(i for i in indices if not p.test(worlds[i]))
            if yes and no:candidates.append((impurity(yes)+impurity(no),rank,p,yes,no))
        if not candidates:raise AssertionError('Ownership predicates should distinguish unequal worlds')
        _,_,p,yes,no=min(candidates,key=lambda x:(x[0],x[1]))
        split(yes,conditions+((p,True),));split(no,conditions+((p,False),))
    split(tuple(range(len(worlds))),())
    partition=OutcomePartition(tuple(leaves),frozenset(worlds))
    if tuple(partition.value(w) for w in worlds)!=tuple(values):raise AssertionError('Partition verification failed')
    return partition


@dataclass(frozen=True)
class CertifiedStrategy:
    policy: object
    partition: OutcomePartition


@dataclass(frozen=True)
class CertifiedFrontier:
    domain: EndingDomain
    worlds: tuple[Position,...]
    strategies: tuple[CertifiedStrategy,...]
    assumptions: str
    objective: str
    contract: object
    vul: bool

    def best(self,weights):
        # Weights may be zero. Every pure strategy on a sub-support has an
        # extension to this full domain; dominated full-domain vectors cannot
        # become superior under nonnegative reweighting. Opponent model fixed.
        return max(self.strategies,key=lambda s:s.partition.weighted_value(weights))


def certify_domain(domain,contract,objective='tricks',vul=False):
    if contract.declarer!=domain.declarer:raise ValueError('Declarer mismatch')
    worlds=domain.worlds()
    solver=AlphaMu(contract,objective,vul,max_nodes=1_000_000,seconds=60)
    result=solver.solve(worlds)
    strategies=[]
    for entry in result.front:
        realized=tuple(evaluate_policy(p,entry.policy,contract,solver.utility) for p in result.worlds)
        if realized!=entry.values:raise AssertionError('Policy witness verification failed')
        strategies.append(CertifiedStrategy(entry.policy,partition_outcomes(result.worlds,realized,domain.declarer)))
    return CertifiedFrontier(domain,result.worlds,tuple(strategies),
        'deterministic declarer; omniscient adversarial defenders; fully enumerated fixed-card domain',
        objective,contract,vul),result.stats
