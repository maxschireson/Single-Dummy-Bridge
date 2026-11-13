"""Convention-card descriptors (Gen 9 WIP): schema, defaults, validation.

A descriptor is the structured form of what a partnership declares, in the fields of the
ACBL and WBF cards. Ingest (an LLM or a person reading a PDF/image/text card) fills it; the
compiler (system.py) reads only a validated descriptor. Every field has a default, so a
descriptor states only where it differs from the base: a natural five-card-major,
15-17 no-trump system close to SAYC.

Fields the compiler does not understand are kept and reported by ``unsupported()``, so a
card's residual against what was compiled is explicit rather than silently dropped.

Three optional blocks sit beside the descriptor (G9-B8):

- ``variants``: departures by seat and vulnerability, ``[{"when": {"seats": [1], "vul": "fav",
  "scoring": "imps"}, "descriptor": {flat keys}, "source": "..."}]``. ``seats`` are positions in
  the bidding order from the dealer (1..4) of the player making the call; ``vul`` is one of
  any | we | nv | fav | unfav | both | none, seen from that player; ``scoring`` is any | imps | mp.
  ``Card.at(position, we_vul, they_vul, scoring)`` returns the card with every matching variant
  applied in list order (later entries win). A variant changes the calls of the seats it names;
  partner reads the base card unless the variant names partner's seat too, so a 1NT range by seat
  belongs in ``open.nt``'s own entries (both partners read those).
- ``recorded``: agreements with a field in ``configs/cards/_fields.json`` marked ``executable: no``
  (Drury, Smolen, ...), kept as structured values and not compiled; an unknown key is reported.
- ``style``: the card's and the notes' style statements, each with where it was placed
  (a field, a variant, the defaults) or why it was not.
"""
import copy
import json
from pathlib import Path

SCHEMA = 'card-descriptor-v0'
CARD_DIR = Path(__file__).resolve().parents[2] / 'configs' / 'cards'

DEFAULTS = {
    'schema': SCHEMA,
    'id': None,
    'name': None,
    'family': 'natural',
    'notes': [],
    'open': {
        'min_hcp': 12,                 # sound one-level opening
        'rule_of_20': True,            # 10-11 HCP opens when HCP + two longest suits >= 20
        'third_seat_min': 10,          # lighter one-level openings in third seat (5+ suit)
        'light': None,                 # {'hcp': 10}: one-level openings this light with a six-card suit or two five-card suits
        'fourth_seat_rule_of_15': True,
        'one_level_max': 21,
        'major_len': 5,                # 4 = four-card majors
        'minor': {'1C_min': 3, '1D_min': 3, 'with_33': '1C', 'with_44': '1D'},
        'nt': [{'hcp': [15, 17], 'seats': [1, 2, 3, 4], 'vul': 'any'}],   # vul: any | we | nv
        'nt_five_major': True,
        'nt_six_minor': False,
        'two_nt': [20, 21],
        'two_nt_five_major': True,     # a 2NT opening may hold a five-card major
        'strong_2c': {'hcp': 22, 'ltc': 3, 'ltc_hcp': 17, 'call': '2C'},   # 22+, or 17+ with at most 3 losers; 'call' may be 2D; null: none
        'strong_club': None,           # {'hcp': 16}: 1C artificial and forcing
        'nebulous_1d': None,           # {'min_len': 2} (Precision 1D)
        'polish_club': None,           # {'bal': [12, 14], 'strong': 18, 'clubs': [15, 17]}
        'two': {
            '2D': {'type': 'weak', 'hcp': [5, 10], 'len': [6, 6]},
            '2H': {'type': 'weak', 'hcp': [5, 10], 'len': [6, 6]},
            '2S': {'type': 'weak', 'hcp': [5, 10], 'len': [6, 6]},
        },                              # types: weak | multi | flannery | precision | natural | none
        'weak_quality': 2,             # weak twos and preempts: honours among the suit's top five
        'weak_top3': None,             # weak twos and three-level preempts: honours among the suit's top three (null: no condition)
        'weak_other_major_max': 3,     # a weak two in a major denies this many or more in the other major (null: no limit)
        'preempt_seats': [1, 2, 3, 4], # seats in which weak twos and preempts are opened
        'precision_2c': None,          # {'hcp': [11, 15]}: 6+ clubs, or 5 clubs and a 4-card major
        'three_level': {'len': 7, 'len_max': 7, 'hcp_min': 0, 'hcp_max': 10},
        'four_level': {'len': 8, 'hcp_max': 12},
        'three_nt': {'type': 'gambling'},            # gambling | natural ({'hcp': [25, 27]}) | null
    },
    'resp': {
        'two_over_one': 'gf',          # gf | standard (10+, forcing one round)
        'one_nt_to_major': 'forcing',  # forcing | semi | nf
        'single_raise': [6, 10],
        'limit_raise': [10, 12],
        'limit_raise_len': 4,          # support for a limit raise of a major
        'major_jump_raise': 'limit',   # limit | weak (4+ support, at most 9)
        'one_nt_range': None,          # [lo, hi] of 1NT over a major; default from one_nt_to_major
        'major_3nt': None,             # [lo, hi]: 3NT over a major, balanced with two-card support
        'jacoby_min': 13,
        'major_2nt': 'jacoby',         # jacoby | natural (13-15 balanced) | invite (11-12)
        'splinters': True,
        'weak_game_raise': True,
        'inverted_minors': False,
        'minor_2nt': [11, 12],
        'minor_3nt': [13, 15],
        'nt': {'stayman': True, 'transfers': 'jacoby', 'texas': True, 'two_spade': 'clubs', 'super_accept': True,
               'transfers_first': False,     # a five-card major and a four-card major: transfer (true) or Stayman
               'stayman_five_four': True,    # Stayman may hold a five-card major beside the four
               'stayman_min_2nt': 'invite',  # over 2NT: Stayman from invitational values, or 'game'
               'slam_first': False,          # 6NT (balanced, slam values) before everything else
               'quantitative': True,         # 4NT quantitative
               'answers': 'all',             # all | relays (only Stayman and transfer answers are defined)
               'game': 25},                  # combined points for game, for the response ranges
        'strong_2c': {'waiting': None, 'positive_min': 8},   # waiting: the next step unless set
        'weak_two_2nt': 'feature',     # feature | ogust
        'strong_club': {'negative': '1D', 'negative_max': 7},
    },
    'rebid': {
        'one_nt': None,                # opener's 1NT rebid range; default from the opening ranges
        'two_nt': [18, 19],
        'reverse_min': 17,
        'jump_shift_min': 19,
    },
    'comp': {
        'overcall_1': [8, 16],
        'overcall_2': [11, 16],
        'overcall_len': 5,
        'jump_overcall': 'weak',       # weak | intermediate | strong | none
        'nt_overcall': [15, 18],
        'balancing_nt': [11, 14],
        'balancing_nt_major': None,    # [lo, hi]: balancing 1NT over a major, where it differs from balancing_nt
        'takeout_double_min': 12,
        'michaels': True,
        'michaels_major_min': 8,       # Michaels over a major: HCP from (over a minor: 8)
        'unusual_2nt': True,
        'negative_double_thru': '2S',  # highest overcall over which a double is negative; null = none
        'vs_nt': 'natural',            # natural | cappelletti | dont | landy | multi_landy | woolsey
        'vs_nt_double': 'penalty',
        'vs_nt_double_min': 15,
        'vs_nt_natural': {'len_major': 5, 'len_minor': 6, 'hcp': [8, 15], 'top3': 2, 'top5': 0},
        'vs_nt_2nt_minors': True,
        'strong_double_min': 18,
        'overcall_3_min': None,        # three-level simple overcalls from this many HCP (null: none defined)
        'overcall_quality': {'1': {'top5': 2}, '2': {'top3': 2}, '3': {'top3': 2}},
        'takeout_shape': 'majors',     # majors: 3+ in each unbid major | all: 3+ in every unbid suit
        'jump_overcall_len3': 6,
        'weak_jump_hcp': [5, 10],
        'jump_first': False,           # a suit's jump overcall is tried before its simple overcall
        'balancing_jumps': True,
        'balance': 3,                  # points borrowed in the pass-out seat
    },
    'slam': {'blackwood': 'rkc1430', 'gerber': True},
    'cover': ['open', 'respond', 'respond_nt', 'rebid', 'nt_answers', 'nt_relays', 'overcall', 'balance', 'vs_nt', 'resp_comp', 'advance', 'asks'],
    'carding': {},                     # fields of configs/systems/_carding_fields.json (Gen 8)
}

# dict-valued fields a card replaces whole rather than merging key by key
LEAF = {'overcall_quality', 'vs_nt_natural', 'light', 'strong_2c', 'strong_club', 'nebulous_1d', 'polish_club',
        'precision_2c', 'three_level', 'four_level', 'three_nt'}

TYPES_TWO = ('weak', 'multi', 'flannery', 'precision', 'natural', 'none')
VS_NT = ('natural', 'cappelletti', 'dont', 'landy', 'multi_landy', 'woolsey')
VUL_WHEN = ('any', 'we', 'nv', 'fav', 'unfav', 'both', 'none')
SCORING = ('any', 'imps', 'mp')
SIDE_BLOCKS = ('provenance', 'generator', 'residual', 'variants', 'recorded', 'style')
LATER_FIELDS = {('open', 'weak_top3'): None, ('comp', 'balancing_nt_major'): None}   # added in G9-B8 (13 Nov 2026)
FIELDS = CARD_DIR / '_fields.json'


def vul_matches(when, we_vul, they_vul):
    """Whether a variant's `vul` holds for the caller's side (we_vul) and the opponents (they_vul)."""
    we, they = bool(we_vul), bool(they_vul)
    return {'any': True, 'we': we, 'nv': not we, 'fav': not we and they, 'unfav': we and not they,
            'both': we and they, 'none': not we and not they}[when]


def recorded_fields():
    """Keys of _fields.json that are recorded and not compiled (executable: no)."""
    try:
        fields = json.loads(FIELDS.read_text())['fields']
    except (OSError, ValueError, KeyError):
        return set()
    return {k for k, v in fields.items() if v.get('executable') == 'no'}


def _merge(base, over, path, unknown):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        p = f'{path}.{k}' if path else k
        if k not in base:
            unknown.append(p)
            out[k] = v
        elif isinstance(base[k], dict) and isinstance(v, dict) and k not in ('two', 'carding') and k not in LEAF:
            out[k] = _merge(base[k], v, p, unknown)
        elif k == 'two' and isinstance(v, dict):
            merged = copy.deepcopy(base[k])
            for call, spec in v.items():
                merged[call] = spec
            out[k] = merged
        else:
            out[k] = v
    return out


def unflatten(descriptor):
    """Flat dotted keys ('open.nt_five_major': true), as configs/cards/_fields.json lists them, to the
    nested form; nested input passes through. A document may also keep them under 'descriptor'."""
    d = dict(descriptor)
    flat = d.pop('descriptor', None) or {}
    for k in [k for k in d if '.' in k]:
        flat[k] = d.pop(k)
    for k, v in flat.items():
        node = d
        parts = k.split('.')
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = v
    return d


class Card:
    """A validated descriptor with defaults filled in."""

    def __init__(self, descriptor):
        self.residual = {str(k): (dict(v) if isinstance(v, dict) else list(v)) for k, v in (descriptor.get('residual') or {}).items()}
        variants = descriptor.get('variants') or []
        self.recorded = dict(descriptor.get('recorded') or {})
        self.style = list(descriptor.get('style') or [])
        descriptor = unflatten({k: v for k, v in descriptor.items() if k not in SIDE_BLOCKS})
        if descriptor.get('schema', SCHEMA) != SCHEMA:
            raise ValueError(f'not a {SCHEMA} document: {descriptor.get("schema")!r}')
        self.unknown = []
        self.raw = copy.deepcopy(descriptor)
        self.d = _merge(DEFAULTS, descriptor, '', self.unknown)
        if not self.d.get('id'):
            raise ValueError('a card needs an id')
        self._check()
        self.variant = ()
        self.variants = [self._variant_spec(i, v) for i, v in enumerate(variants)]
        self._at = {}
        for i in range(len(self.variants)):                     # each variant must stand on the base card
            unknown = []
            self._apply((i,), unknown)
            self.unknown += [f'variants[{i}].{p}' for p in unknown]
        if self.recorded:
            known = recorded_fields()
            self.unknown += [f'recorded.{k}' for k in self.recorded if k not in known]

    @staticmethod
    def _variant_spec(i, v):
        when = dict(v.get('when') or {})
        bad = set(when) - {'seats', 'vul', 'scoring'}
        if bad:
            raise ValueError(f'variants[{i}].when: unexpected keys {sorted(bad)}')
        seats = [int(s) for s in when.get('seats', [1, 2, 3, 4])]
        vul, scoring = when.get('vul', 'any'), when.get('scoring', 'any')
        if not seats or any(s not in (1, 2, 3, 4) for s in seats):
            raise ValueError(f'variants[{i}].when.seats must be positions 1..4')
        if vul not in VUL_WHEN:
            raise ValueError(f'variants[{i}].when.vul must be one of {VUL_WHEN}')
        if scoring not in SCORING:
            raise ValueError(f'variants[{i}].when.scoring must be one of {SCORING}')
        over = unflatten(dict(v.get('descriptor') or {}))
        if not over:
            raise ValueError(f'variants[{i}] changes nothing')
        return {'seats': seats, 'vul': vul, 'scoring': scoring, 'over': over, 'source': v.get('source')}

    def _apply(self, idx, unknown=None):
        """This card with the variants `idx` (indices, in order) applied; cached."""
        if idx not in self._at:
            c = copy.copy(self)
            d = self.d
            for i in idx:
                d = _merge(d, self.variants[i]['over'], '', unknown if unknown is not None else [])
            c.d, c.variant, c.variants, c._at = d, tuple(idx), [], {}
            c._check()
            self._at[idx] = c
        return self._at[idx]

    def at(self, position, we_vul, they_vul, scoring='imps'):
        """The card that holds for a caller in this seat (1..4 from the dealer) and vulnerability."""
        if not self.variants:
            return self
        idx = tuple(i for i, v in enumerate(self.variants)
                    if position in v['seats'] and vul_matches(v['vul'], we_vul, they_vul) and v['scoring'] in ('any', scoring))
        return self._apply(idx) if idx else self

    def variant_doc(self):
        """The variants as a card file states them (for identities and reports)."""
        return [{'when': {'seats': v['seats'], 'vul': v['vul'], 'scoring': v['scoring']}, 'descriptor': v['over']} for v in self.variants]

    def identity_doc(self):
        """What a bidder's identity hashes: the filled descriptor without fields added after a card's identity
        was first taken (while they hold their defaults), and the variants when there are any. Cards from before
        G9-B8 keep their identities."""
        d = copy.deepcopy(self.d)
        for (sec, key), default in LATER_FIELDS.items():
            if d.get(sec, {}).get(key, default) == default:
                d.get(sec, {}).pop(key, None)
        doc = {'kind': 'card', 'card': d}
        if self.variants:
            doc['variants'] = self.variant_doc()
        return doc

    @property
    def id(self):
        return self.d['id']

    def __getitem__(self, k):
        return self.d[k]

    def _check(self):
        o = self.d['open']
        if o['major_len'] not in (4, 5):
            raise ValueError('open.major_len must be 4 or 5')
        for e in o['nt']:
            lo, hi = e['hcp']
            if not 8 <= lo <= hi <= 22:
                raise ValueError(f'implausible 1NT range {e["hcp"]}')
            if e.get('vul', 'any') not in ('any', 'we', 'nv'):
                raise ValueError('1NT vul must be any | we | nv')
        for call, spec in o['two'].items():
            if call not in ('2C', '2D', '2H', '2S'):
                raise ValueError(f'open.two: unexpected call {call}')
            if spec and spec.get('type') not in TYPES_TWO:
                raise ValueError(f'open.two.{call}: type must be one of {TYPES_TWO}')
        if self.d['resp']['two_over_one'] not in ('gf', 'standard'):
            raise ValueError('resp.two_over_one must be gf or standard')
        if self.d['comp']['vs_nt'] not in VS_NT:
            raise ValueError('comp.vs_nt must be ' + ' | '.join(VS_NT))
        bm = self.d['comp']['balancing_nt_major']
        if bm is not None and not (len(bm) == 2 and 8 <= bm[0] <= bm[1] <= 22):
            raise ValueError(f'implausible comp.balancing_nt_major {bm}')

    def unsupported(self):
        """Descriptor paths the compiler does not read (kept, reported, not compiled)."""
        return list(self.unknown)

    def nt_range(self, position, we_vul):
        """The 1NT opening range for a seat (1..4) and our vulnerability, or None."""
        for e in self.d['open']['nt']:
            if position in e.get('seats', [1, 2, 3, 4]):
                v = e.get('vul', 'any')
                if v == 'any' or (v == 'we') == bool(we_vul):
                    return tuple(e['hcp'])
        return None

    def to_json(self):
        return json.dumps(self.raw, indent=2, sort_keys=True)


def load_card(source):
    """A Card from a dict, a path, or an id under configs/cards/."""
    if isinstance(source, Card):
        return source
    if isinstance(source, dict):
        return Card(source)
    p = Path(source)
    if not p.exists():
        p = CARD_DIR / f'{source}.json'
    return Card(json.loads(p.read_text()))


def builtin_ids():
    return sorted(p.stem for p in CARD_DIR.glob('*.json') if not p.name.startswith('_'))
