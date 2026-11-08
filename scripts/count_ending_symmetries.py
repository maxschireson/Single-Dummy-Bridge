#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Exact DD trick-boundary counts after relative ranks and suit symmetries.

Derivation: concatenate the four suit ownership strings (four copies of each
seat symbol for a four-card ending), then choose suit lengths. Apply Burnside's
lemma to permutations of all suits (NT) or the three nontrump suits (trump).
Leader is fixed by rotating seats; scores are for the leader's partnership.
This is NOT a count of imperfect-information strategy states or proof regions.
"""
from itertools import product
from math import comb, factorial
import json


def multinomial(counts):
    result=factorial(sum(counts))
    for n in counts: result//=factorial(n)
    return result


def bounded_compositions(total, parts, cap=13):
    # Inclusion-exclusion for ordered suit lengths, each at most 13.
    return sum((-1)**j*comb(parts,j)*comb(total-j*(cap+1)+parts-1,parts-1)
               for j in range(parts+1) if total-j*(cap+1)>=0)


def strings(counts, parts):
    return multinomial(counts)*bounded_compositions(sum(counts),parts)


def counts(k):
    identity=strings((k,)*4,4)
    transposition=0
    for v in product(range(k//2+1),repeat=4):
        if sum(v)<=13:
            transposition+=multinomial(v)*strings(tuple(k-2*x for x in v),2)
    double_transposition=strings((k//2,)*4,2) if k%2==0 else 0
    three_cycle=0
    for v in product(range(k//3+1),repeat=4):
        if sum(v)<=13:
            three_cycle+=multinomial(v)*strings(tuple(k-3*x for x in v),1)
    four_cycle=multinomial((k//4,)*4) if k%4==0 and k<=13 else 0
    nt=(identity+6*transposition+3*double_transposition+8*three_cycle+6*four_cycle)//24
    trump=(identity+3*transposition+2*three_cycle)//6
    raw=factorial(52)//(factorial(52-4*k)*factorial(k)**4)
    bits=k.bit_length()  # ceil(log2(k + 1)), for values 0..k
    return dict(cards_per_hand=k,raw_fixed_strain_fixed_leader=raw,
                relative_rank_labelled_suits=identity,no_trump=nt,one_canonical_trump=trump,
                combined_states=nt+trump,bits_per_value=bits,
                ideal_packed_value_bytes=(nt+trump)*bits/8,
                four_bit_value_bytes=(nt+trump)/2,
                unseen_ew_splits=comb(2*k,k),arbitrary_support_subsets=2**comb(2*k,k))

if __name__=='__main__': print(json.dumps([counts(k) for k in range(1,5)],indent=2))
