"""Compile a convention card into call meanings (Gen 9 WIP).

``CardSystem(card).rules(ctx)`` returns, for one auction context seen from one seat, the
calls the card defines there, as Rules in priority order, or None when the card does not
cover the context. Rules end with a catch-all, so the first satisfied rule is always a call.

The coverage is the declared layer of a natural or strong-club card: openings; responses to
one-level, 1NT, 2NT, strong 2C, weak-two and strong-club openings; opener's first rebid;
the 1NT relays; direct and balancing overcalls, takeout doubles, two-suiters, defence to
1NT; negative doubles and simple advances; key-card answers. Everything later is left to
the nets (scorer) or to the natural continuation (rule bidder), on purpose.

Known simplifications are listed in docs/gen9_card_semantics.md. The opponents' card does
not change the meaning of our calls yet (e.g. a cue-bid of an artificial 1C).
"""
from .card import load_card
from .context import BIDS, LHO, ME, PARTNER, RANK, RHO, Context, is_bid, level, strain
from .features import ANY, MAJORS, SUITS, C, Pred, Rule

HIGHER = {'C': 'DHS', 'D': 'HS', 'H': 'S', 'S': ''}
CHEAPER = {'S': 'HDC', 'H': 'DC', 'D': 'C', 'C': ''}


def L(s, lo=None, hi=None):
    """Bound on one suit's length, as keyword arguments for C()."""
    return {s: (lo, hi)}


def kw(*dicts, **more):
    out = {}
    for d in dicts:
        out.update(d)
    out.update(more)
    return out


def cheapest(strain_, above):
    """Cheapest bid in a strain above `above` (a bid or None)."""
    start = RANK[above] + 1 if above else 0
    for b in BIDS[start:]:
        if b[1] == strain_:
            return b
    return None


def jump(strain_, above):
    b = cheapest(strain_, above)
    return None if b is None or level(b) == 7 else f'{level(b) + 1}{strain_}'


def parse_seq(after_open):
    out = []
    for tok in after_open.split():
        call = tok[1:]
        out.append(('MLPR'.index(tok[0]), 'PASS' if call == 'P' else call))
    return out


class CardSystem:
    def __init__(self, card):
        self.card = load_card(card)
        self.d = self.card.d
        self.o, self.r, self.rb, self.cp = self.d['open'], self.d['resp'], self.d['rebid'], self.d['comp']
        self._cache = {}

    @property
    def id(self):
        return self.card.id

    # ------------------------------------------------------------------ dispatch
    def rules(self, ctx: Context):
        key = (ctx.key, ctx.opening_index, ctx.position)
        if key not in self._cache:
            out = self._dispatch(ctx)
            if out is not None:
                legal = set(ctx.legal)
                out = [r for r in out if r.call in legal]
                if not out or out[-1].pred != ANY:
                    out = None if not out else out + [Rule('PASS', ANY, 'catch', 'nothing else fits')]
            self._cache[key] = out
        return self._cache[key]

    def _dispatch(self, ctx):
        cover = set(self.d['cover'])
        if ctx.opening_index is None:
            return self.opening(ctx) if 'open' in cover else None
        seq = parse_seq(ctx.after_open)
        opener, opening = ctx.opener, ctx.opening
        mine = ctx.bids_of(ME)
        if 'asks' in cover:
            ask = self._ask_answer(ctx, seq)
            if ask is not None:
                return ask
        if opener == PARTNER and len(seq) == 2:
            passed = any(c == 'PASS' for r, c in ctx.roles[:ctx.opening_index] if r == ME)
            if seq[1][1] == 'PASS':
                key = 'respond_nt' if opening in ('1N', '2N') else 'respond'
                return self.responder(ctx, opening, seq[1][1], passed) if key in cover else None
            return self.responder(ctx, opening, seq[1][1], passed) if 'resp_comp' in cover else None
        if opener == RHO and len(seq) == 1:
            if opening == '1N':
                return self.direct(ctx, opening, balancing=False) if 'vs_nt' in cover else None
            return self.direct(ctx, opening, balancing=False) if 'overcall' in cover else None
        if opener == LHO and len(seq) == 3 and seq[1][1] == 'PASS' and seq[2][1] == 'PASS':
            return self.direct(ctx, opening, balancing=True) if 'balance' in cover else None
        if opener == LHO and len(seq) == 3 and seq[1][1] != 'PASS':
            return self.advancer(ctx, opening, seq[1][1], seq[2][1]) if 'advance' in cover else None
        if opener == ME and len(seq) == 4 and seq[1][1] == 'PASS' and seq[3][1] == 'PASS':
            if opening in ('1N', '2N'):
                return self.opener_rebid(ctx, opening, seq[2][1]) if 'nt_answers' in cover else None
            return self.opener_rebid(ctx, opening, seq[2][1]) if 'rebid' in cover else None
        if opener == PARTNER and len(seq) == 6 and mine and seq[1][1] == 'PASS' and seq[3][1] == 'PASS' and seq[5][1] == 'PASS':
            return self.responder_rebid(ctx, opening, seq[2][1], seq[4][1]) if 'nt_relays' in cover else None
        return None

    # ------------------------------------------------------------------ shapes and ranges
    def nt_shape(self):
        o = self.o
        p = C(bal=1) if o['nt_five_major'] else C(bal=1, S=(None, 4), H=(None, 4))
        if o['nt_six_minor']:
            p = p | C(semibal=1, longest=6, S=(None, 3), H=(None, 3))
        return p

    def nt_range(self, position, we_vul):
        return self.card.nt_range(position, we_vul)

    def rebid_nt(self, position, we_vul):
        if self.rb['one_nt']:
            return tuple(self.rb['one_nt'])
        nt = self.nt_range(position, we_vul)
        if nt is None or nt[0] > 14:
            return (self.o['min_hcp'], 14)
        return (nt[1] + 1, min(nt[1] + 3, 17))

    def strength(self, ctx, suit=None):
        """Clauses for a one-level suit opening in this seat."""
        o = self.o
        mn, mx = o['min_hcp'], o['one_level_max']
        if o['strong_club']:
            mx = min(mx, o['strong_club']['hcp'] - 1)
        cl = [C(hcp=(mn, mx))]
        if o['light'] and o['light']['hcp'] < mn:
            lh = (o['light']['hcp'], mn - 1)
            cl += [C(hcp=lh, longest=(6, None)), C(hcp=lh, second=(5, None))]
        if ctx.position == 4 and o['fourth_seat_rule_of_15']:
            return C(hcp=(10, mx), r15=(15, None)) | C(hcp=(14, mx))
        if o['rule_of_20'] and mn > 10:
            cl.append(C(hcp=(10, mn - 1), r20=(20, None)))
        if ctx.position == 3 and o['third_seat_min'] < mn and suit is not None:
            cl.append(C(**kw(L(suit, 5), hcp=(o['third_seat_min'], mn - 1))))
        return Pred.of(*cl)

    # ------------------------------------------------------------------ openings
    def opening(self, ctx):
        o = self.o
        out = []
        sc = o['strong_club']
        if sc:
            out.append(Rule('1C', C(hcp=(sc['hcp'], None)), 'open_strong', 'strong club 1C', forcing=1, artificial=True))
        elif o['strong_2c']:
            s2 = o['strong_2c']
            p2c = C(hcp=(s2['hcp'], None))
            if s2.get('ltc') is not None:
                p2c = p2c | C(ltc=(None, s2['ltc']), hcp=(s2.get('ltc_hcp', 17), None))
            sc_call = s2.get('call', '2C')
            out.append(Rule(sc_call, p2c, 'open_strong', f'strong {sc_call}', forcing=2, artificial=True))
        pc = o['polish_club']
        if pc:
            out.append(Rule('1C', C(bal=1, hcp=tuple(pc['bal'])) | C(hcp=(pc['strong'], None))
                            | C(C=(5, None), hcp=tuple(pc['clubs'])), 'open_polish', 'Polish 1C', forcing=1, artificial=True))
        if o['two_nt']:
            shape = C(bal=1) if o['two_nt_five_major'] else C(bal=1, S=(None, 4), H=(None, 4))
            out.append(Rule('2N', shape & C(hcp=tuple(o['two_nt'])), 'open_nt', '2NT'))
        nt = self.nt_range(ctx.position, ctx.we_vul)
        if nt:
            out.append(Rule('1N', self.nt_shape() & C(hcp=nt), 'open_nt', f'1NT {nt[0]}-{nt[1]}'))
        t3 = o['three_nt']
        if t3 and t3.get('type') == 'natural':
            out.append(Rule('3N', C(bal=1, hcp=tuple(t3['hcp'])), 'open_nt', '3NT natural'))
        two = o['two']
        if (two.get('2D') or {}).get('type') == 'flannery':
            sp = two['2D']
            out.append(Rule('2D', C(S=4, H=5, hcp=tuple(sp.get('hcp', [11, 15]))), 'open_two', 'Flannery 2D', artificial=True))
        out.extend(self._one_level(ctx))
        out.extend(self._twos(ctx))
        out.extend(self._preempts(ctx))
        out.append(Rule('PASS', ANY, 'open_pass', 'pass'))
        return out

    def _one_level(self, ctx):
        o = self.o
        out = []
        strong = lambda s: self.strength(ctx, s)
        if o['major_len'] == 5:
            out.append(Rule('1S', strong('S') & C(S=(5, None), rel=[('S', 'H', 0)]), 'open_major', '1S five-card'))
            out.append(Rule('1H', strong('H') & C(H=(5, None)), 'open_major', '1H five-card'))
            if o['precision_2c']:
                p2 = o['precision_2c']
                h = tuple(p2.get('hcp', [11, 15]))
                pred = C(C=(p2.get('len', 6), None), hcp=h)
                if p2.get('five_four', True):
                    pred = pred | C(C=5, S=(4, None), hcp=h) | C(C=5, H=(4, None), hcp=h)
                out.append(Rule('2C', pred, 'open_two', 'Precision 2C'))
            sp = o['two'].get('2D') or {}
            if sp.get('type') == 'precision':
                out.append(Rule('2D', C(D=(None, 1), S=(3, 4), H=(3, 4), C=tuple(sp.get('clubs', [3, 5])), longest=(None, 5),
                                        hcp=tuple(sp.get('hcp', [11, 15]))), 'open_two', 'Precision 2D', artificial=True))
            if o['polish_club']:
                out.append(Rule('1D', strong('D') & C(D=(4, None)), 'open_minor', '1D four-plus'))
                out.append(Rule('1C', strong('C'), 'open_minor', '1C (rest)'))        # never reached: Polish 1C above
                return out
            if o['strong_club'] and o['nebulous_1d']:
                out.append(Rule('1D', strong('D') & C(D=(o['nebulous_1d'].get('min_len', 2), None)), 'open_minor', 'nebulous 1D'))
                return out
            m = o['minor']
            d_clauses = [C(D=(5, None), rel=[('D', 'C', 0)]), C(D=4, C=(None, 3)), C(D=3, C=(None, 2))]
            if m['with_44'] == '1D':
                d_clauses.append(C(D=4, C=4))
            if m['with_33'] == '1D':
                d_clauses.append(C(D=3, C=3))
            dmin = m['1D_min']
            out.append(Rule('1D', strong('D') & Pred.of(*d_clauses) & C(D=(dmin, None)), 'open_minor', '1D'))
            out.append(Rule('1C', strong('C') & C(C=(m['1C_min'], None)), 'open_minor', '1C'))
            out.append(Rule('1D', strong('D') & C(D=(dmin, None)), 'open_minor', '1D (rest)'))
            return out
        # four-card suits: longest first, higher of equal five-card suits, cheapest of four-card suits
        for s in 'SHDC':
            higher = [t for t in SUITS if SUITS.index(t) < SUITS.index(s)]
            lower = [t for t in SUITS if SUITS.index(t) > SUITS.index(s)]
            rel = [(s, t, 1) for t in higher] + [(s, t, 0) for t in lower]
            long_ = C(**L(s, 5), rel=rel)
            four = C(**kw(L(s, 4, 4), longest=(None, 4), **{t: (None, 3) for t in CHEAPER[s]}))
            out.append(Rule(f'1{s}', strong(s) & (long_ | four), 'open_suit', f'1{s} longest / cheapest four'))
        return out

    def _twos(self, ctx):
        out = []
        if ctx.position not in self.o['preempt_seats']:
            return out
        for call in ('2S', '2H', '2D', '2C'):
            sp = self.o['two'].get(call) or {}
            t = sp.get('type')
            s = call[1]
            if t == 'weak':
                lo, hi = sp.get('len', [6, 6])
                cl = kw(L(s, lo, hi), hcp=tuple(sp.get('hcp', [5, 10])), **{'top5' + s: (self.o['weak_quality'], None)})
                om = self.o['weak_other_major_max']
                if s in MAJORS and om is not None:
                    cl.update(L('H' if s == 'S' else 'S', None, om))
                out.append(Rule(call, C(**cl), 'open_weak', f'weak {call}'))
            elif t == 'multi':
                h = tuple(sp.get('hcp', [5, 10]))
                out.append(Rule(call, C(H=6, S=(None, 3), hcp=h) | C(S=6, H=(None, 3), hcp=h), 'open_weak', 'Multi 2D', artificial=True))
            elif t == 'natural':
                lo, hi = sp.get('len', [6, 7])
                out.append(Rule(call, C(**kw(L(s, lo, hi), hcp=tuple(sp.get('hcp', [16, 22])), ltc=(None, 5))), 'open_strong', f'strong {call}'))
        return out

    def _preempts(self, ctx):
        out = []
        if ctx.position not in self.o['preempt_seats']:
            return out
        t4, t3 = self.o['four_level'], self.o['three_level']
        if t4:
            for s in 'SH':
                out.append(Rule(f'4{s}', C(**kw(L(s, t4['len']), hcp=(None, t4['hcp_max']))), 'open_preempt', f'4{s} preempt'))
        if t3:
            for s in 'SHDC':
                out.append(Rule(f'3{s}', C(**kw(L(s, t3['len'], t3.get('len_max', t3['len'])), hcp=(t3.get('hcp_min', 0), t3['hcp_max']),
                                                **{'top5' + s: (self.o['weak_quality'], None)})),
                                'open_preempt', f'3{s} preempt'))
        t3n = self.o['three_nt']
        if t3n and t3n.get('type') == 'gambling':
            out.append(Rule('3N', C(D=(7, None), top3D=3, ctrl=3, hcp=(9, 12)) | C(C=(7, None), top3C=3, ctrl=3, hcp=(9, 12)),
                            'open_preempt', 'gambling 3NT', artificial=True))
        if t4 and t4.get('minors', True):
            for s in 'DC':
                out.append(Rule(f'4{s}', C(**kw(L(s, t4['len']), hcp=(None, t4['hcp_max']))), 'open_preempt', f'4{s} preempt'))
        return out

    # ------------------------------------------------------------------ responder
    def responder(self, ctx, opening, rho, passed):
        o = self.o
        if rho == 'PASS':
            if opening == '1C' and o['strong_club']:
                return self.resp_strong_club(ctx)
            if opening == '1C' and o['polish_club']:
                return self.resp_minor(ctx, 'C', passed, polish=True)
            if opening in ('1C', '1D'):
                return self.resp_minor(ctx, opening[1], passed)
            if opening in ('1H', '1S'):
                return self.resp_major(ctx, opening[1], passed)
            if opening == '1N':
                nt = self.nt_range((ctx.opening_index % 4) + 1, ctx.we_vul)
                return self.resp_nt(ctx, nt or (15, 17), 1)
            if opening == '2N' and o['two_nt']:
                return self.resp_nt(ctx, tuple(o['two_nt']), 2)
            if o['strong_2c'] and not o['strong_club'] and opening == o['strong_2c'].get('call', '2C'):
                return self.resp_2c(ctx, opening)
            sp = o['two'].get(opening) or {}
            if sp.get('type') == 'weak':
                return self.resp_weak_two(ctx, opening[1])
            return None
        if opening in ('1C', '1D', '1H', '1S') and not o['strong_club'] and not (o['polish_club'] and opening == '1C'):
            return self.resp_competitive(ctx, opening[1], rho, passed)
        return None

    def resp_major(self, ctx, M, passed):
        r = self.r
        out = []
        other = 'S' if M == 'H' else 'H'
        gf = r['two_over_one'] == 'gf' and not passed
        cap = 11 if passed else None
        if not passed and r['major_2nt'] == 'jacoby':
            out.append(Rule('2N', C(**L(M, 4), hcp=(r['jacoby_min'], None)), 'resp_raise', 'Jacoby 2NT', forcing=2, artificial=True, shows={'fit': M}))
        if not passed and r['splinters']:
            for side in SUITS:
                if side == M:
                    continue
                call = jump(side, f'1{M}')
                call = call if call and level(call) == 3 else f'4{side}'
                if call == f'3{other}' and M == 'S':
                    continue
                if level(call) == 3 and side != 'S':
                    call = f'4{side}'
                out.append(Rule(call, C(**kw(L(M, 4), L(side, None, 1), hcp=(12, 15))), 'resp_raise', f'splinter in {side}',
                                forcing=2, artificial=True, shows={'fit': M}))
        if r['weak_game_raise']:
            out.append(Rule(f'4{M}', C(**L(M, 5), hcp=(None, 9)), 'resp_raise', 'preemptive game raise', shows={'fit': M}))
        if r['major_jump_raise'] == 'weak':
            out.append(Rule(f'3{M}', C(**L(M, 4), hcp=(None, 9)), 'resp_raise', 'weak jump raise', shows={'fit': M}))
        else:
            out.append(Rule(f'3{M}', C(**L(M, r['limit_raise_len']), hcp=tuple(r['limit_raise'])), 'resp_raise', 'limit raise', shows={'fit': M}))
        if r['major_3nt'] and not passed:
            out.append(Rule('3N', C(**L(M, 2, 2), bal=1, hcp=tuple(r['major_3nt'])), 'resp_nt', '3NT balanced'))
        two_one_min = 12 if gf else (10 if not passed else 10)
        two_one_max = cap
        new2 = [s for s in 'HDC' if s != M and (M == 'S' or s != 'H')]
        if r['major_2nt'] == 'natural' and not passed:
            out.append(Rule('2N', C(bal=1, hcp=(13, 15), **L(M, None, 2)), 'resp_nt', '2NT natural', forcing=2))
        for s in new2:
            need = 5 if s == 'H' else 5
            out.append(Rule(f'2{s}', C(**kw(L(s, need), hcp=(two_one_min, two_one_max))), 'resp_new',
                            f'2/1 in {s}' + (' GF' if gf else ''), forcing=2 if gf else 1))
        out.append(Rule(f'2{M}', C(**L(M, 3), hcp=tuple(r['single_raise'])), 'resp_raise', 'single raise', shows={'fit': M}))
        if M == 'H':
            out.append(Rule('1S', C(S=(4, None), hcp=(6, None)), 'resp_new', '1S', forcing=1))
        for s in ('D', 'C'):
            if s in new2:
                out.append(Rule(f'2{s}', C(**kw(L(s, 4), hcp=(two_one_min, two_one_max))), 'resp_new',
                                f'2/1 in {s} (four)' + (' GF' if gf else ''), forcing=2 if gf else 1))
        if r['major_2nt'] == 'invite':
            out.append(Rule('2N', C(bal=1, hcp=(11, 12)), 'resp_nt', '2NT invitational'))
        if not passed:
            # strong hands that fit nothing above: a forcing new suit in a three-card minor
            big = 13 if gf or r['one_nt_to_major'] != 'forcing' else 13
            for s in ('C', 'D'):
                out.append(Rule(f'2{s}', C(**kw(L(s, 3), hcp=(max(two_one_min, big), None))), 'resp_new', f'2{s} (three-card, forcing)',
                                forcing=2 if gf else 1))
        lo1, hi = r['one_nt_range'] or (6, {'forcing': 12, 'semi': 12, 'nf': 10}[r['one_nt_to_major']])
        if passed:
            hi = min(hi, 11)
        out.append(Rule('1N', C(hcp=(lo1, hi)), 'resp_nt', f'1NT {r["one_nt_to_major"]}',
                        forcing=1 if r['one_nt_to_major'] == 'forcing' and not passed else 0))
        out.append(Rule('PASS', ANY, 'resp_pass', 'pass'))
        return out

    def resp_minor(self, ctx, m, passed, polish=False):
        r = self.r
        out = []
        cap = 11 if passed else None
        out.append(Rule('1S', C(S=(5, None), rel=[('S', 'H', 0)], hcp=(6, None)) | C(S=4, H=(None, 3), hcp=(6, None)),
                        'resp_new', '1S', forcing=1))
        out.append(Rule('1H', C(H=(4, None), hcp=(6, None)), 'resp_new', '1H', forcing=1))
        if polish:
            out.append(Rule('1N', C(bal=1, hcp=(7, 10)), 'resp_nt', '1NT 7-10'))
            out.append(Rule('2N', C(bal=1, hcp=(11, 12)), 'resp_nt', '2NT 11-12'))
            out.append(Rule('1D', ANY, 'resp_relay', '1D negative or waiting', forcing=1, artificial=True))
            return out
        gf = r['two_over_one'] == 'gf' and not passed
        sup = 4 if m == 'D' and not self.o['nebulous_1d'] else 5
        if m == 'C':
            out.append(Rule('2D', C(D=(5, None), hcp=(12 if gf else 10, cap)), 'resp_new', '2D' + (' GF' if gf else ''), forcing=2 if gf else 1))
            out.append(Rule('1D', C(D=(4, None), hcp=(6, None)), 'resp_new', '1D', forcing=1))
        else:
            out.append(Rule('2C', C(C=(5, None), hcp=(12 if gf else 10, cap)), 'resp_new', '2C' + (' GF' if gf else ''), forcing=2 if gf else 1))
        if r['inverted_minors']:
            out.append(Rule(f'2{m}', C(**L(m, sup), hcp=(10, cap), H=(None, 3), S=(None, 3)), 'resp_raise', 'inverted raise', forcing=1, shows={'fit': m}))
            out.append(Rule(f'3{m}', C(**L(m, 5), hcp=(None, 9)), 'resp_raise', 'preemptive raise', shows={'fit': m}))
        else:
            out.append(Rule(f'3{m}', C(**L(m, sup), hcp=tuple(r['limit_raise'])), 'resp_raise', 'limit raise', shows={'fit': m}))
        if not passed:
            out.append(Rule('2N', C(bal=1, hcp=tuple(r['minor_2nt'])), 'resp_nt', '2NT'))
            out.append(Rule('3N', C(bal=1, hcp=tuple(r['minor_3nt'])), 'resp_nt', '3NT'))
        if not r['inverted_minors']:
            out.append(Rule(f'2{m}', C(**L(m, sup), hcp=(6, 10)), 'resp_raise', 'single raise', shows={'fit': m}))
        out.append(Rule('1N', C(hcp=(6, 10)), 'resp_nt', '1NT 6-10'))
        if passed:
            out.append(Rule('2N', C(hcp=(11, 12)), 'resp_nt', '2NT passed hand'))
        out.append(Rule('PASS', ANY, 'resp_pass', 'pass'))
        return out

    def resp_strong_club(self, ctx):
        neg = self.r['strong_club']
        mx = neg.get('negative_max', 7)
        out = []
        for s in 'SH':
            out.append(Rule(f'1{s}', C(**L(s, 5), hcp=(mx + 1, None)), 'resp_positive', f'positive 1{s}', forcing=2))
        for s in 'CD':
            out.append(Rule(f'2{s}', C(**L(s, 5), hcp=(mx + 1, None)), 'resp_positive', f'positive 2{s}', forcing=2))
        out.append(Rule('2N', C(bal=1, hcp=(14, None)), 'resp_positive', 'positive 2NT', forcing=2))
        out.append(Rule('1N', C(bal=1, hcp=(mx + 1, 13)), 'resp_positive', 'positive 1NT', forcing=2))
        out.append(Rule('1D', ANY, 'resp_negative', 'negative', forcing=1, artificial=True))
        return out

    def resp_nt(self, ctx, nt, step):
        lo, hi = nt
        rn = self.r['nt']
        G = rn.get('game', 25)
        game, inv = G - lo, (G - hi, G - lo - 1)
        quant = (31 - lo, 32 - lo)
        top = quant[0] - 1 if rn['quantitative'] else None
        out = []
        b = lambda lv, s: f'{lv + step - 1}{s}'
        if rn['slam_first']:
            out.append(Rule('6N', C(bal=1, hcp=(33 - lo, None)), 'resp_nt', 'slam'))
        if rn['texas']:
            out.append(Rule('4D', C(H=(6, None), hcp=(game, quant[0] - 1)), 'resp_nt_relay', 'Texas to 4H', artificial=True))
            out.append(Rule('4H', C(S=(6, None), hcp=(game, quant[0] - 1)), 'resp_nt_relay', 'Texas to 4S', artificial=True))
        smin = inv[0] if step == 1 or rn['stayman_min_2nt'] == 'invite' else game
        if rn['stayman']:
            if rn['stayman_five_four']:
                spred = C(H=4, hcp=(smin, None)) | C(S=4, hcp=(smin, None))
            else:
                spred = C(H=4, S=(None, 4), hcp=(smin, None)) | C(S=4, H=(None, 4), hcp=(smin, None))
            stayman = [Rule(b(2, 'C'), spred, 'resp_nt_relay', 'Stayman', forcing=1, artificial=True)]
        else:
            stayman = []
        transfers = []
        if rn['transfers']:
            transfers.append(Rule(b(2, 'H'), C(S=(5, None), rel=[('S', 'H', 0)]), 'resp_nt_relay', 'transfer to spades', forcing=1, artificial=True))
            transfers.append(Rule(b(2, 'D'), C(H=(5, None)), 'resp_nt_relay', 'transfer to hearts', forcing=1, artificial=True))
            if step == 1 and rn['two_spade'] == 'clubs':
                transfers.append(Rule('2S', C(C=(6, None), hcp=(None, inv[0] - 1)), 'resp_nt_relay', 'transfer to clubs', forcing=1, artificial=True))
            elif step == 1 and rn['two_spade'] == 'minors':
                transfers.append(Rule('2S', C(C=(5, None), D=(5, None)), 'resp_nt_relay', 'both minors', forcing=1, artificial=True))
        out += (transfers + stayman) if rn['transfers_first'] else (stayman + transfers)
        if not rn['slam_first']:
            out.append(Rule('6N', C(hcp=(33 - lo, 36 - lo)), 'resp_nt', 'slam'))
        if rn['quantitative']:
            out.append(Rule('4N', C(hcp=quant), 'resp_nt', 'quantitative', forcing=0))
        out.append(Rule('3N', C(hcp=(game, top)), 'resp_nt', 'game'))
        if step == 1:
            out.append(Rule('2N', C(hcp=inv), 'resp_nt', 'invitational'))
        out.append(Rule('PASS', ANY, 'resp_pass', 'pass'))
        return out

    def waiting_call(self, opening):
        w = self.r['strong_2c'].get('waiting')
        return w if w and RANK.get(w, -1) > RANK[opening] else BIDS[RANK[opening] + 1]

    def resp_2c(self, ctx, opening='2C'):
        sp = self.r['strong_2c']
        mn = sp.get('positive_min', 8)
        wait = self.waiting_call(opening)
        out = []
        for s in 'HSCD':
            b = cheapest(s, opening)
            if b == wait:
                continue
            out.append(Rule(b, C(**kw(L(s, 5), hcp=(mn, None), **{'top3' + s: (2, None)})), 'resp_positive', f'positive {b}', forcing=2))
        out.append(Rule('2N', C(bal=1, hcp=(mn, None)), 'resp_positive', 'positive 2NT', forcing=2))
        out.append(Rule(wait, ANY, 'resp_negative', 'waiting', forcing=2, artificial=True))
        return out

    def resp_weak_two(self, ctx, s):
        out = [Rule('2N', C(hcp=(15, None)), 'resp_ask', 'ask', forcing=1, artificial=True)]
        if s in 'HS':
            out.append(Rule(f'4{s}', C(**L(s, 3), hcp=(16, None)) | C(**L(s, 4), hcp=(None, 10)), 'resp_raise', 'game', shows={'fit': s}))
        out.append(Rule(f'3{s}', C(**L(s, 3), hcp=(None, 13)), 'resp_raise', 'preemptive raise', shows={'fit': s}))
        out.append(Rule('3N', C(hcp=(16, None), bal=1), 'resp_nt', 'to play'))
        for t in 'SHDC':
            if t == s:
                continue
            b = cheapest(t, f'2{s}')
            out.append(Rule(b, C(**L(t, 5), hcp=(14, None)), 'resp_new', f'new suit {t}', forcing=1))
        out.append(Rule('PASS', ANY, 'resp_pass', 'pass'))
        return out

    def resp_competitive(self, ctx, m, rho, passed):
        """Partner opened one of a suit; RHO doubled or overcalled."""
        out = []
        if rho == 'X':
            out.append(Rule('XX', C(hcp=(10, None)), 'resp_comp', 'redouble 10+'))
            if m in MAJORS:
                out.append(Rule('2N', C(**L(m, 4), hcp=(10, None)), 'resp_comp', 'Jordan 2NT', artificial=True, shows={'fit': m}))
                out.append(Rule(f'3{m}', C(**L(m, 4), hcp=(None, 9)), 'resp_comp', 'preemptive raise', shows={'fit': m}))
            out.append(Rule(f'2{m}', C(**L(m, 3 if m in MAJORS else 5), hcp=(6, 9)), 'resp_comp', 'raise', shows={'fit': m}))
            for s in 'HS':
                b = cheapest(s, f'1{m}')
                if level(b) == 1:
                    out.append(Rule(b, C(**L(s, 4), hcp=(6, 9)), 'resp_comp', f'{b} natural'))
            out.append(Rule('1N', C(hcp=(6, 9)), 'resp_comp', '1NT 6-9'))
            out.append(Rule('PASS', ANY, 'resp_pass', 'pass'))
            return out
        if not is_bid(rho) or strain(rho) == 'N':
            return None
        y = strain(rho)
        out = []
        if y in 'CDHS' and y != m:
            cue = cheapest(y, rho)
            out.append(Rule(cue, C(**L(m, 3 if m in MAJORS else 4), hcp=(10, None)), 'resp_comp', 'cue-bid raise', forcing=1, artificial=True, shows={'fit': m}))
        raise_ = cheapest(m, rho)
        if raise_ and level(raise_) <= 3:
            out.append(Rule(raise_, C(**L(m, 3 if m in MAJORS else 5), hcp=(6, 10)), 'resp_comp', 'raise', shows={'fit': m}))
        jr = jump(m, rho)
        if jr and level(jr) <= 4 and m in MAJORS:
            out.append(Rule(jr, C(**L(m, 4), hcp=(None, 9)), 'resp_comp', 'preemptive jump raise', shows={'fit': m}))
        thru = self.cp['negative_double_thru']
        neg_ok = thru is not None and y != 'N' and RANK[rho] <= RANK[thru]
        unbid_majors = [s for s in 'HS' if s not in (m, y)]
        # a new suit at the one level is natural and forcing
        for s in 'SH':
            b = cheapest(s, rho)
            if s not in (m, y) and b and level(b) == 1:
                out.append(Rule(b, C(**L(s, 5 if neg_ok else 4), hcp=(6, None)), 'resp_comp', f'{b} natural', forcing=1))
        if neg_ok and unbid_majors:
            need = 6 if level(rho) == 1 else 8
            cl = [C(**kw({s: (4, None) for s in unbid_majors}, hcp=(need, None)))]
            if len(unbid_majors) == 2:
                cl = [C(H=(4, None), S=(4, None), hcp=(need, None))]
            out.append(Rule('X', Pred.of(*cl), 'resp_comp', 'negative double'))
        nt1 = cheapest('N', rho)
        if level(nt1) == 1:
            out.append(Rule(nt1, C(**{'stop' + y: 1}, hcp=(6, 10)), 'resp_comp', '1NT with a stopper'))
        elif level(nt1) == 2:
            out.append(Rule(nt1, C(**{'stop' + y: 1}, hcp=(11, 12)), 'resp_comp', '2NT with a stopper'))
        for s in 'SHDC':
            if s in (m, y):
                continue
            b = cheapest(s, rho)
            if b and level(b) == 2:
                out.append(Rule(b, C(**L(s, 5), hcp=(10, None)), 'resp_comp', f'{b} natural', forcing=1))
        out.append(Rule('PASS', ANY, 'resp_pass', 'pass'))
        return out

    # ------------------------------------------------------------------ opener's rebid
    def opener_rebid(self, ctx, opening, resp):
        o, rb = self.o, self.rb
        pos = ctx.opening_index % 4 + 1
        if opening == '1N':
            return self._nt_answer(ctx, resp, self.nt_range(pos, ctx.we_vul) or (15, 17), 1)
        if opening == '2N':
            return self._nt_answer(ctx, resp, tuple(o['two_nt']), 2) if o['two_nt'] else None
        if o['strong_2c'] and not o['strong_club'] and opening == o['strong_2c'].get('call', '2C') and resp == self.waiting_call(opening):
            out = [Rule('2N', C(bal=1, hcp=(22, 24)), 'rebid_nt', '2NT 22-24'),
                   Rule('3N', C(bal=1, hcp=(25, 27)), 'rebid_nt', '3NT 25-27')]
            for s in 'SHDC':
                out.append(Rule(cheapest(s, resp), C(**L(s, 5), rel=[(s, t, 0) for t in SUITS if t != s]), 'rebid_suit', f'natural {s}', forcing=2))
            out.append(Rule('2N', ANY, 'rebid_nt', 'catch'))
            return out
        sp = o['two'].get(opening) or {}
        if sp.get('type') == 'weak' and resp == '2N':
            s = opening[1]
            if self.r['weak_two_2nt'] == 'ogust':
                good = {'top3' + s: (2, None)}
                return [Rule('3S', C(hcp=(9, None), **good), 'rebid_ask', 'max, good suit', artificial=True),
                        Rule('3H', C(hcp=(9, None)), 'rebid_ask', 'max, bad suit', artificial=True),
                        Rule('3D', C(**good), 'rebid_ask', 'min, good suit', artificial=True),
                        Rule('3C', ANY, 'rebid_ask', 'min, bad suit', artificial=True)]
            out = []
            for t in 'SHDC':
                if t != s:
                    out.append(Rule(cheapest(t, '2N'), C(**{'top3' + t: (1, None), 'hcp': (9, None)}), 'rebid_ask', f'feature in {t}', artificial=True))
            out.append(Rule(f'3{s}', ANY, 'rebid_ask', 'minimum'))
            return out
        if opening not in ('1C', '1D', '1H', '1S') or (opening == '1C' and (o['strong_club'] or o['polish_club'])):
            return None
        x = opening[1]
        if resp == '1N':
            return self._rebid_over_1nt(ctx, x)
        if resp == f'2{x}' and x in MAJORS:
            return [Rule(f'4{x}', C(tp=(19, None)) | C(ltc=(None, 5)), 'rebid_raise', 'game'),
                    Rule(f'3{x}', C(tp=(16, 18)), 'rebid_raise', 'invitational'),
                    Rule('PASS', ANY, 'rebid_pass', 'minimum')]
        if resp == f'3{x}' and x in MAJORS:
            return [Rule(f'4{x}', C(hcp=(14, None)) | C(tp=(15, None)), 'rebid_raise', 'accept'),
                    Rule('PASS', ANY, 'rebid_pass', 'decline')]
        if resp == '2N' and x in MAJORS and self.r['major_2nt'] == 'jacoby':
            out = []
            for t in 'SHDC':
                if t != x:
                    out.append(Rule(cheapest(t, '2N'), C(**L(t, None, 1)), 'rebid_jacoby', f'shortness in {t}', artificial=True, forcing=2))
            return out + [Rule('3N', C(hcp=(15, 17), bal=1), 'rebid_jacoby', '15-17 balanced', forcing=2),
                          Rule(f'3{x}', C(hcp=(16, None)), 'rebid_jacoby', '16+ no shortness', forcing=2),
                          Rule(f'4{x}', ANY, 'rebid_jacoby', 'minimum', forcing=0)]
        if not (is_bid(resp) and level(resp) == 1):
            return None
        y = resp[1]
        rnt = self.rebid_nt(pos, ctx.we_vul)
        out = []
        if y in MAJORS:
            out.append(Rule(f'4{y}', C(**L(y, 4), tp=(19, None)), 'rebid_raise', 'raise to game', shows={'fit': y}))
            out.append(Rule(f'3{y}', C(**L(y, 4), tp=(16, 18)), 'rebid_raise', 'jump raise', shows={'fit': y}))
            out.append(Rule(f'2{y}', C(**L(y, 4), hcp=(None, 15)), 'rebid_raise', 'single raise', shows={'fit': y}))
        for t in 'SHDC':
            if t in (x, y):
                continue
            b = cheapest(t, resp)
            jb = jump(t, resp)
            out.append(Rule(jb, C(**L(t, 4), hcp=(rb['jump_shift_min'], None)), 'rebid_new', f'jump shift {t}', forcing=2))
            if level(b) == 2 and SUITS.index(t) < SUITS.index(x):        # higher-ranking than the opened suit
                out.append(Rule(b, C(**kw(L(t, 4), hcp=(rb['reverse_min'], None), rel=[(x, t, 1)])), 'rebid_new', f'reverse {t}', forcing=1))
        for t in 'SH':
            b = cheapest(t, resp)
            if t not in (x, y) and level(b) == 1:
                out.append(Rule(b, C(**L(t, 4)), 'rebid_new', f'{b} natural'))
        if rb['two_nt']:
            out.append(Rule('2N', C(bal=1, hcp=tuple(rb['two_nt'])), 'rebid_nt', '2NT'))
        out.append(Rule('1N', C(bal=1, hcp=rnt), 'rebid_nt', f'1NT {rnt[0]}-{rnt[1]}'))
        out.append(Rule(f'3{x}', C(**L(x, 6), hcp=(16, 18)), 'rebid_suit', 'jump rebid'))
        for t in 'SHDC':
            if t in (x, y):
                continue
            b = cheapest(t, resp)
            if level(b) == 2 and SUITS.index(t) > SUITS.index(x):
                out.append(Rule(b, C(**L(t, 4), hcp=(None, 18)), 'rebid_new', f'{b} natural'))
        out.append(Rule(f'2{x}', C(**L(x, 5)), 'rebid_suit', 'rebid own suit'))
        if y in 'CD':
            out.append(Rule(f'2{y}', C(**L(y, 4), hcp=(None, 15)), 'rebid_raise', 'minor raise', shows={'fit': y}))
        out.append(Rule(cheapest(x, resp), ANY, 'rebid_suit', 'catch: rebid own suit'))
        return out

    def _rebid_over_1nt(self, ctx, x):
        rb = self.rb
        forcing = self.r['one_nt_to_major'] == 'forcing' and x in MAJORS
        out = [Rule('3N', C(bal=1, hcp=(18, 19)), 'rebid_nt', '3NT'),
               Rule('2N', C(bal=1, hcp=(17, 18)), 'rebid_nt', '2NT invitational'),
               Rule(f'3{x}', C(**L(x, 6), hcp=(16, 18)), 'rebid_suit', 'jump rebid')]
        for t in 'SHDC':
            if t == x:
                continue
            if SUITS.index(t) < SUITS.index(x):
                out.append(Rule(f'2{t}', C(**kw(L(t, 4), hcp=(rb['reverse_min'], None))), 'rebid_new', f'reverse {t}', forcing=1))
            else:
                out.append(Rule(f'2{t}', C(**L(t, 4)), 'rebid_new', f'2{t} natural'))
        out.append(Rule(f'2{x}', C(**L(x, 6)), 'rebid_suit', 'six-card suit'))
        if forcing:
            out.append(Rule('2C', C(C=(3, None)), 'rebid_new', '2C three-card (1NT forcing)'))
            out.append(Rule('2D', C(D=(3, None)), 'rebid_new', '2D three-card (1NT forcing)'))
            out.append(Rule(f'2{x}', ANY, 'rebid_suit', 'catch'))
        else:
            out.append(Rule('PASS', ANY, 'rebid_pass', 'minimum balanced'))
        return out

    def _nt_answer(self, ctx, resp, nt, step):
        lo, hi = nt
        rn = self.r['nt']
        b = lambda lv, s: f'{lv + step - 1}{s}'
        if resp == b(2, 'C') and rn['stayman']:
            return [Rule(b(2, 'H'), C(H=(4, None)), 'nt_answer', 'four hearts'),
                    Rule(b(2, 'S'), C(S=(4, None)), 'nt_answer', 'four spades'),
                    Rule(b(2, 'D'), ANY, 'nt_answer', 'no major', artificial=True)]
        if rn['transfers'] and resp in (b(2, 'D'), b(2, 'H')):
            s = 'H' if resp == b(2, 'D') else 'S'
            out = []
            if rn['super_accept'] and step == 1:
                out.append(Rule(f'3{s}', C(**L(s, 4), hcp=(hi, None)), 'nt_answer', 'super-accept'))
            return out + [Rule(cheapest(s, resp), ANY, 'nt_answer', 'complete the transfer')]
        if resp == '2S' and step == 1 and rn['two_spade'] == 'clubs':
            return [Rule('3C', ANY, 'nt_answer', 'complete the transfer')]
        if rn['texas'] and resp in ('4D', '4H'):
            return [Rule('4H' if resp == '4D' else '4S', ANY, 'nt_answer', 'complete Texas')]
        if rn['answers'] != 'all':
            return None
        if resp == '2N' and step == 1:
            return [Rule('3N', C(hcp=(lo + 1, None)), 'nt_answer', 'accept'), Rule('PASS', ANY, 'nt_answer', 'decline')]
        if resp == '4N':
            return [Rule('6N', C(hcp=(lo + 1, None)), 'nt_answer', 'accept'), Rule('PASS', ANY, 'nt_answer', 'decline')]
        if resp in ('3N', '6N', '4S') or (resp == '4H' and not rn['texas']):
            return [Rule('PASS', ANY, 'nt_answer', 'signed off')]
        return None

    def responder_rebid(self, ctx, opening, first, answer):
        """Only the 1NT/2NT relays (Stayman, transfers)."""
        if opening not in ('1N', '2N') or (opening == '2N' and not self.o['two_nt']):
            return None
        step = 1 if opening == '1N' else 2
        nt = self.nt_range(ctx.opening_index % 4 + 1, ctx.we_vul) if step == 1 else tuple(self.o['two_nt'])
        lo = (nt or (15, 17))[0]
        game, inv = 25 - lo, (23 - lo, 24 - lo)
        b = lambda lv, s: f'{lv + step - 1}{s}'
        rn = self.r['nt']
        if first == b(2, 'C') and rn['stayman']:
            if answer in (b(2, 'H'), b(2, 'S')):
                s = answer[1]
                out = [Rule(f'4{s}', C(**L(s, 4), hcp=(game, None)), 'nt_relay2', 'game in the fit'),
                       Rule(f'3{s}', C(**L(s, 4), hcp=inv), 'nt_relay2', 'invite in the fit')]
            else:
                out = []
            if step == 1:
                out.append(Rule('2N', C(hcp=inv), 'nt_relay2', 'invite'))
            return out + [Rule('3N', C(hcp=(game, None)), 'nt_relay2', 'game'), Rule('PASS', ANY, 'nt_relay2', 'weak')]
        if rn['transfers'] and first in (b(2, 'D'), b(2, 'H')):
            s = 'H' if first == b(2, 'D') else 'S'
            if answer != cheapest(s, first):
                return None
            out = [Rule(f'4{s}', C(**L(s, 6), hcp=(game, None)), 'nt_relay2', 'game, six-card suit'),
                   Rule('3N', C(**L(s, 5, 5), hcp=(game, None)), 'nt_relay2', 'choice of games')]
            if step == 1:
                out += [Rule(f'3{s}', C(**L(s, 6), hcp=inv), 'nt_relay2', 'invite, six-card suit'),
                        Rule('2N', C(**L(s, 5, 5), hcp=inv), 'nt_relay2', 'invite, five-card suit')]
            return out + [Rule('PASS', ANY, 'nt_relay2', 'weak')]
        return None

    # ------------------------------------------------------------------ defence
    def direct(self, ctx, opening, balancing):
        cp = self.cp
        if opening == '1N':
            return None if balancing else self.vs_nt(ctx)
        if not (is_bid(opening) and level(opening) == 1):
            return None
        x = opening[1]
        out = []
        adj = -cp['balance'] if balancing else 0
        unbid = [s for s in 'SHDC' if s != x]
        if cp['michaels'] and not balancing:
            if x in 'CD':
                pred = C(S=(5, None), H=(5, None), hcp=(8, None))
            else:
                om, mm = 'S' if x == 'H' else 'H', cp['michaels_major_min']
                pred = C(**L(om, 5), D=(5, None), hcp=(mm, None)) | C(**L(om, 5), C=(5, None), hcp=(mm, None))
            out.append(Rule(f'2{x}', pred, 'comp_two_suited', 'Michaels', artificial=True))
        if cp['unusual_2nt'] and not balancing:
            low = [s for s in 'CDH' if s != x][:2]
            out.append(Rule('2N', C(**{low[0]: (5, None), low[1]: (5, None)}, hcp=(8, None)), 'comp_two_suited', 'unusual 2NT', artificial=True))
        ntr = cp['balancing_nt'] if balancing else cp['nt_overcall']
        out.append(Rule('1N', C(bal=1, hcp=tuple(ntr), **{'stop' + x: 1}), 'comp_nt', f'1NT overcall {ntr[0]}-{ntr[1]}'))
        out.append(Rule('X', C(hcp=(cp['strong_double_min'] + adj, None)), 'comp_double', 'strong double'))
        jt = cp['jump_overcall']
        o1, o2, o3 = cp['overcall_1'], cp['overcall_2'], cp['overcall_3_min']
        late_jumps = []
        for s in 'SHDC':
            if s == x:
                continue
            simple = []
            b = cheapest(s, opening)
            lv = level(b)
            if lv <= 2 or o3 is not None:
                rng = o1 if lv == 1 else o2 if lv == 2 else (o3, o2[1])
                q = {k + s: (v, None) for k, v in cp['overcall_quality'][str(min(lv, 3))].items()}
                simple.append(Rule(b, C(**kw(L(s, cp['overcall_len'] if lv == 1 else 5), q, hcp=(rng[0] + adj, rng[1]))), 'comp_overcall', f'{b} overcall'))
            jumps = []
            j = jump(s, opening)
            if j and level(j) <= 3 and jt != 'none' and (cp['balancing_jumps'] or not balancing):
                jl = 6 if level(j) == 2 else cp['jump_overcall_len3']
                if jt == 'weak' and not balancing:
                    jumps.append(Rule(j, C(**kw(L(s, jl), hcp=tuple(cp['weak_jump_hcp']), **{'top5' + s: (cp['overcall_quality']['1'].get('top5', 2), None)})),
                                      'comp_jump', f'weak jump {j}'))
                elif jt == 'intermediate' or balancing:
                    jumps.append(Rule(j, C(**kw(L(s, jl), hcp=(12, 16))), 'comp_jump', f'intermediate jump {j}'))
                else:
                    jumps.append(Rule(j, C(**kw(L(s, jl), hcp=(17, None))), 'comp_jump', f'strong jump {j}'))
            if cp['jump_first']:
                out += jumps + simple
            else:
                out += simple
                late_jumps += jumps
        takeout_suits = [s for s in unbid if s in 'SH'] if cp['takeout_shape'] == 'majors' else unbid
        shape = C(**kw({x: (None, 2)}, {s: (3, None) for s in takeout_suits}, hcp=(cp['takeout_double_min'] + adj, None)))
        out.append(Rule('X', shape, 'comp_double', 'takeout double'))
        out.extend(late_jumps)
        out.append(Rule('PASS', ANY, 'comp_pass', 'pass'))
        return out

    def vs_nt(self, ctx):
        conv = self.cp['vs_nt']
        out = []
        if self.cp['vs_nt_double'] == 'penalty' and conv != 'dont':
            out.append(Rule('X', C(hcp=(self.cp['vs_nt_double_min'], None)), 'comp_vs_nt', 'penalty double'))
        if conv == 'cappelletti':
            out += [Rule('2D', C(H=(5, None), S=(4, None), hcp=(9, None)) | C(H=(4, None), S=(5, None), hcp=(9, None)), 'comp_vs_nt', 'both majors', artificial=True),
                    Rule('2H', C(H=(5, None), hcp=(9, None)) & (C(C=(4, None)) | C(D=(4, None))), 'comp_vs_nt', 'hearts and a minor'),
                    Rule('2S', C(S=(5, None), hcp=(9, None)) & (C(C=(4, None)) | C(D=(4, None))), 'comp_vs_nt', 'spades and a minor'),
                    Rule('2C', C(longest=(6, None), n4=1, hcp=(9, None)), 'comp_vs_nt', 'one long suit', artificial=True)]
        elif conv == 'dont':
            out += [Rule('2H', C(H=(5, None), S=(4, None)) | C(H=(4, None), S=(5, None)), 'comp_vs_nt', 'both majors'),
                    Rule('2D', C(D=(5, None), H=(4, None)) | C(D=(5, None), S=(4, None)), 'comp_vs_nt', 'diamonds and a major'),
                    Rule('2C', C(C=(5, None), D=(4, None)) | C(C=(5, None), H=(4, None)) | C(C=(5, None), S=(4, None)), 'comp_vs_nt', 'clubs and a higher suit'),
                    Rule('2S', C(S=(6, None)), 'comp_vs_nt', 'spades'),
                    Rule('X', C(longest=(6, None), n4=1, hcp=(8, None)), 'comp_vs_nt', 'one long suit', artificial=True)]
        elif conv == 'multi_landy':
            out += [Rule('2D', C(H=(4, None), S=(4, None), hcp=(8, None)), 'comp_vs_nt', 'both majors', artificial=True),
                    Rule('2H', C(H=(5, None), hcp=(8, None)) & (C(C=(4, None)) | C(D=(4, None))), 'comp_vs_nt', 'hearts and a minor'),
                    Rule('2S', C(S=(5, None), hcp=(8, None)) & (C(C=(4, None)) | C(D=(4, None))), 'comp_vs_nt', 'spades and a minor'),
                    Rule('2C', C(H=(6, None), hcp=(8, None)) | C(S=(6, None), hcp=(8, None)), 'comp_vs_nt', 'one six-card major', artificial=True)]
        elif conv == 'landy':
            out.append(Rule('2C', C(H=(4, None), S=(4, None), n5=(1, None), hcp=(9, None)), 'comp_vs_nt', 'Landy, both majors', artificial=True))
        if self.cp['vs_nt_2nt_minors']:
            out.append(Rule('2N', C(C=(5, None), D=(5, None), hcp=(8, None)), 'comp_vs_nt', 'both minors', artificial=True))
        nat = self.cp['vs_nt_natural']
        defined = {r.call for r in out}
        for s in 'SHDC':
            if f'2{s}' in defined:                  # an artificial meaning already holds this call
                continue
            q = {k + s: (nat[k], None) for k in ('top3', 'top5') if nat.get(k)}
            ln = nat['len_minor'] if s in 'CD' else nat['len_major']
            out.append(Rule(f'2{s}', C(**kw(L(s, ln), q, hcp=tuple(nat['hcp']))), 'comp_vs_nt', f'natural 2{s}'))
        out.append(Rule('PASS', ANY, 'comp_pass', 'pass'))
        return out

    def advancer(self, ctx, opening, pact, rho):
        if rho != 'PASS' or not is_bid(opening):
            return None
        x = opening[1]
        out = []
        if x == 'N':
            return None
        if pact == 'X' and level(opening) == 1:
            for s in 'SHDC':
                if s == x:
                    continue
                j = jump(s, opening)
                if j and level(j) <= 3:
                    out.append(Rule(j, C(**L(s, 4), hcp=(9, 11)), 'adv_double', f'jump {j}'))
            out.append(Rule(cheapest(x, opening), C(hcp=(12, None)), 'adv_double', 'cue-bid', forcing=1, artificial=True))
            out.append(Rule('2N', C(hcp=(11, 12), **{'stop' + x: 1}), 'adv_double', '2NT'))
            out.append(Rule('1N', C(hcp=(6, 10), **{'stop' + x: 1}), 'adv_double', '1NT'))
            out.append(Rule('PASS', C(**L(x, 5), **{'top5' + x: (3, None)}), 'adv_double', 'penalty pass'))
            for s in 'SHDC':
                if s != x:
                    b = cheapest(s, opening)
                    out.append(Rule(b, C(**L(s, 4), rel=[(s, t, 0) for t in 'SHDC' if t not in (s, x)]), 'adv_double', f'{b} longest'))
            for s in 'HSDC':
                if s != x:
                    out.append(Rule(cheapest(s, opening), C(**L(s, 3)), 'adv_double', 'three-card'))
            out.append(Rule(cheapest('D' if x != 'D' else 'C', opening), ANY, 'adv_double', 'catch'))
            return out
        if not is_bid(pact):
            return None
        y = strain(pact)
        two = self._two_suited_shown(opening, pact)
        if two:
            a, b2 = two
            out = [Rule(cheapest(a, pact), C(rel=[(a, b2, 0)]), 'adv_two_suited', f'prefer {a}'),
                   Rule(cheapest(b2, pact), ANY, 'adv_two_suited', f'prefer {b2}')]
            return out
        if y == 'N':
            return None
        out.append(Rule(cheapest(x, pact), C(**L(y, 3), hcp=(10, None)), 'adv_overcall', 'cue-bid raise', forcing=1, artificial=True, shows={'fit': y}))
        jr = jump(y, pact)
        if jr and level(jr) <= 4:
            out.append(Rule(jr, C(**L(y, 4), hcp=(None, 9)), 'adv_overcall', 'preemptive raise', shows={'fit': y}))
        out.append(Rule(cheapest(y, pact), C(**L(y, 3), hcp=(7, 10)), 'adv_overcall', 'raise', shows={'fit': y}))
        n1 = cheapest('N', pact)
        if level(n1) <= 2:
            out.append(Rule(n1, C(hcp=(8, 11) if level(n1) == 1 else (11, 13), **{'stop' + x: 1}), 'adv_overcall', 'NT with a stopper'))
        for s in 'SHDC':
            if s in (x, y):
                continue
            b = cheapest(s, pact)
            if level(b) <= 2:
                out.append(Rule(b, C(**L(s, 5), hcp=(8, None), **{'top3' + s: (1, None)}), 'adv_overcall', f'{b} natural'))
        out.append(Rule('PASS', ANY, 'adv_pass', 'pass'))
        return out

    def _two_suited_shown(self, opening, pact):
        """The two suits partner's Michaels or unusual 2NT showed, when both are known."""
        x = opening[1] if is_bid(opening) else None
        if self.cp['unusual_2nt'] and pact == '2N' and level(opening) == 1:
            low = [s for s in 'CDH' if s != x][:2]
            return low[1], low[0]
        if self.cp['michaels'] and pact == f'2{x}' and x in 'CD':
            return 'S', 'H'
        return None

    # ------------------------------------------------------------------ asks
    def _ask_answer(self, ctx, seq):
        """Key-card and Gerber answers to partner's ask."""
        if not seq or seq[-1][1] != 'PASS' or len(seq) < 2:
            return None
        role, call = seq[-2]
        if role != PARTNER:
            return None
        sl = self.d['slam']
        ours = [(r, c) for r, c in seq if r in (ME, PARTNER) and is_bid(c)]
        if call == '4C' and sl['gerber'] and len(ours) >= 2 and ours[-2] == (ME, ours[-2][1]) and ours[-2][1] in ('1N', '2N'):
            return [Rule('4N', C(aces=3), 'ask_answer', '3 aces', artificial=True), Rule('4S', C(aces=2), 'ask_answer', '2 aces', artificial=True),
                    Rule('4H', C(aces=1), 'ask_answer', '1 ace', artificial=True), Rule('4D', ANY, 'ask_answer', '0 or 4 aces', artificial=True)]
        if call != '4N':
            return None
        suits = [strain(c) for r, c in ours[:-1] if strain(c) != 'N']
        if not suits or ours[-2][1][1] == 'N':
            return None                       # 4NT after a no-trump bid is quantitative
        mine = [strain(c) for r, c in ours[:-1] if r == ME]
        theirs = [strain(c) for r, c in ours[:-1] if r == PARTNER]
        agreed = [s for s in reversed(suits) if s in mine and s in theirs]
        t = agreed[0] if agreed else suits[-1]
        kc = 'kc' + t
        if sl['blackwood'] == 'plain':
            return [Rule('5S', C(aces=3), 'ask_answer', '3 aces', artificial=True), Rule('5H', C(aces=2), 'ask_answer', '2 aces', artificial=True),
                    Rule('5D', C(aces=1), 'ask_answer', '1 ace', artificial=True), Rule('5C', ANY, 'ask_answer', '0 or 4 aces', artificial=True)]
        one_four, zero_three = '5C', '5D'
        if sl['blackwood'] == 'rkc3014':
            one_four, zero_three = '5D', '5C'
        return [Rule('5S', C(**{kc: 2, 'Q' + t: 1}), 'ask_answer', '2 key cards and the queen', artificial=True),
                Rule('5H', C(**{kc: 2}), 'ask_answer', '2 key cards', artificial=True),
                Rule(one_four, C(**{kc: (1, 1)}) | C(**{kc: (4, 5)}), 'ask_answer', '1 or 4 key cards', artificial=True),
                Rule(zero_three, ANY, 'ask_answer', '0 or 3 key cards', artificial=True)]
