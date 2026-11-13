"""Cards for the rule bidder's settings, and settings for cards (Gen 9 WIP).

``card_from_settings(settings)`` writes the card IR for a ``rule_bidder.Settings`` (given as a
dict of its fields): the agreements its tables make in the contexts the card covers, which are
openings, direct and balancing overcalls and doubles, the defence to 1NT, responses to 1NT and
2NT, opener's answers to Stayman and transfers, and (since 12 Nov) responder's first call to a suit
opening. Rebids and advances are left uncovered: there its tables value hands with support points
and its general procedure decides. Covering the responses is worth 0.2-0.3 nats a decision to the
card read alone (reports/gen9-e9-12-2026-11-12, supplement); three response fields (major_2nt,
minor_2nt, weak_game_raise) were chosen by a fit to the bidder's own auctions (scripts/gen9_fit_card.py),
the others are the documented settings. Written from the documented meaning
of each Settings field, not from the tables' code; tests/test_gen9_cards.py checks the card
against the bidder's own auctions.

``settings_from_card(card)`` goes the other way for a card inside the rule bidder's family, and
lists the fields that have no Settings form.
"""
from .card import load_card

STANDARD_OPPONENTS_NT_HI = 17         # the rule bidder reads opponents as its standard settings unless told otherwise


def card_from_settings(g, card_id='rb-custom', opponents_nt_hi=STANDARD_OPPONENTS_NT_HI, respond=True):
    """The card for the settings. respond=False leaves responses to suit openings uncovered: the card is then
    exact on every call it covers (the bidder never breaks it); with them covered the bidder breaks about 2% of
    the responses (it values raises by support points), and the card read alone is 0.2-0.3 nats better."""
    g = dict(g)
    precision = g.get('style', 'precision') == 'precision'
    lo = g['open_min']
    top = g['limited_max'] if precision else 21
    weak = {'type': 'weak', 'hcp': [g['weak_lo'], g['weak_hi']], 'len': [6, 6]}
    d = {
        'open.min_hcp': lo, 'open.rule_of_20': False, 'open.third_seat_min': lo, 'open.fourth_seat_rule_of_15': False,
        'open.light': {'hcp': lo - g['open_light']} if g['open_light'] > 0 else None,
        'open.one_level_max': top,
        'open.nt': [{'hcp': [g['nt_lo'], g['nt_hi']], 'seats': [1, 2, 3, 4], 'vul': 'any'}],
        'open.nt_five_major': g['nt_five_major'],
        'open.weak_quality': g['weak_quality'], 'open.weak_other_major_max': None, 'open.preempt_seats': [1, 2, 3],
        'open.three_level': {'len': g['preempt_len'], 'len_max': 13, 'hcp_min': max(0, g['weak_lo'] - 1), 'hcp_max': g['weak_hi']},
        'open.four_level': None, 'open.three_nt': None,
        'comp.michaels': False, 'comp.unusual_2nt': False,
        'comp.overcall_1': [g['overcall_min1'], g['overcall_max']], 'comp.overcall_2': [g['overcall_min2'], g['overcall_max']],
        'comp.overcall_3_min': g['overcall_min2'] + 2,
        'comp.overcall_quality': {k: {'top5': g['overcall_quality']} for k in ('1', '2', '3')},
        'comp.takeout_shape': 'all', 'comp.takeout_double_min': g['takeout_min'], 'comp.strong_double_min': g['takeout_min'] + 6,
        'comp.jump_overcall': 'weak' if g['jump_overcalls'] else 'none', 'comp.jump_overcall_len3': g['preempt_len'],
        'comp.weak_jump_hcp': [g['weak_lo'], g['weak_hi']], 'comp.jump_first': True, 'comp.balancing_jumps': False, 'comp.balance': g['balance'],
        'comp.nt_overcall': [g['nt_overcall_lo'], g['nt_overcall_hi']],
        'comp.balancing_nt': [g['nt_overcall_lo'] - g['balance'], g['nt_overcall_hi'] - g['balance']],
        'comp.vs_nt_double_min': max(16, opponents_nt_hi),
        'comp.vs_nt_natural': {'len_major': 6, 'len_minor': 6, 'hcp': [9, 15], 'top3': 0, 'top5': g['overcall_quality']},
        'comp.vs_nt_2nt_minors': False,
        'resp.nt': {'stayman': g['stayman'], 'transfers': 'jacoby' if g['transfers'] else None, 'texas': False, 'two_spade': None,
                    'super_accept': False, 'transfers_first': True, 'stayman_five_four': False, 'stayman_min_2nt': 'game',
                    'slam_first': True, 'quantitative': False, 'answers': 'relays', 'game': g['game']},
    }
    if precision:
        d.update({'open.strong_club': {'hcp': g['club_min']}, 'open.strong_2c': None, 'open.two_nt': None,
                  'open.nebulous_1d': {'min_len': 1},
                  'open.precision_2c': {'hcp': [lo, top], 'len': g['two_clubs_len'], 'five_four': False},
                  'open.two': {'2D': {'type': 'precision', 'hcp': [lo, top], 'clubs': [4, 5]} if g['two_diamonds'] else {'type': 'none'},
                               '2H': weak, '2S': weak}})
    else:
        d.update({'open.strong_2c': {'hcp': 22, 'ltc': None}, 'open.two_nt': [20, 21], 'open.two_nt_five_major': True,
                  'open.two': {'2D': weak, '2H': weak, '2S': weak}})
    cover = ['open', 'overcall', 'balance', 'vs_nt', 'respond_nt', 'nt_answers']
    if respond:
        d.update({'resp.major_2nt': 'invite', 'resp.minor_2nt': [13, 15], 'resp.weak_game_raise': False})
        if precision:
            d['resp.strong_club'] = {'negative': '1D', 'negative_max': g['neg_max']}
        cover.append('respond')
    return {'schema': 'card-descriptor-v0', 'id': card_id, 'family': 'strong_club' if precision else 'natural',
            'descriptor': d, 'cover': cover}


def settings_from_card(card):
    """(Settings fields as a dict, [card fields with no Settings form]) for a card in the rule bidder's family."""
    c = load_card(card)
    o, r, cp = c['open'], c['resp'], c['comp']
    out, missing = {}, []
    if o['strong_club']:
        out.update(style='precision', club_min=o['strong_club']['hcp'], limited_max=o['one_level_max'])
    else:
        out.update(style='standard')
    out['open_min'] = o['min_hcp']
    out['open_light'] = o['min_hcp'] - o['light']['hcp'] if o['light'] else 0
    nts = o['nt']
    if len(nts) != 1:
        missing.append('open.nt (more than one range)')
    out.update(nt_lo=nts[0]['hcp'][0], nt_hi=nts[0]['hcp'][1], nt_five_major=o['nt_five_major'])
    weak = o['two'].get('2S') or {}
    if weak.get('type') == 'weak':
        out.update(weak_lo=weak['hcp'][0], weak_hi=weak['hcp'][1])
    out['weak_quality'] = o['weak_quality']
    if o['three_level']:
        out['preempt_len'] = o['three_level']['len']
    if o['precision_2c']:
        out['two_clubs_len'] = o['precision_2c'].get('len', 6)
    out['two_diamonds'] = (o['two'].get('2D') or {}).get('type') == 'precision'
    out.update(overcall_min1=cp['overcall_1'][0], overcall_min2=cp['overcall_2'][0], overcall_max=cp['overcall_1'][1],
               takeout_min=cp['takeout_double_min'], nt_overcall_lo=cp['nt_overcall'][0], nt_overcall_hi=cp['nt_overcall'][1],
               jump_overcalls=cp['jump_overcall'] == 'weak', balance=cp['balance'],
               stayman=bool(r['nt']['stayman']), transfers=bool(r['nt']['transfers']), game=r['nt'].get('game', 25))
    cover = set(c['cover'])
    resp_covered = bool(cover & {'respond', 'rebid', 'resp_comp', 'advance'})
    for field, bad in (('open.major_len', o['major_len'] != 5), ('open.polish_club', bool(o['polish_club'])),
                       ('open.two.2D multi/flannery', (o['two'].get('2D') or {}).get('type') in ('multi', 'flannery')),
                       ('resp.inverted_minors', resp_covered and r['inverted_minors']), ('resp.major_2nt', resp_covered and r['major_2nt'] == 'jacoby'),
                       ('resp.nt.texas', r['nt']['texas']), ('comp.michaels', cp['michaels']), ('comp.unusual_2nt', cp['unusual_2nt']),
                       ('comp.vs_nt', cp['vs_nt'] != 'natural')):
        if bad:
            missing.append(field)
    return out, missing


def compile_card(card):
    """(rule_bidder.Settings, [fields with no Settings form]) for a card: the generator for a card inside its family."""
    from .. import rule_bidder as rb
    fields, missing = settings_from_card(card)
    return rb.Settings(**fields), missing
