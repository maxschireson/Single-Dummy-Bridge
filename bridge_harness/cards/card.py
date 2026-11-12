"""Convention-card descriptors (Gen 9 WIP): schema, defaults, validation.

A descriptor is the structured form of what a partnership declares, in the fields of the
ACBL and WBF cards. Ingest (an LLM or a person reading a PDF/image/text card) fills it; the
compiler (system.py) reads only a validated descriptor. Every field has a default, so a
descriptor states only where it differs from the base: a natural five-card-major,
15-17 no-trump system close to SAYC.

Fields the compiler does not understand are kept and reported by ``unsupported()``, so a
card's residual against what was compiled is explicit rather than silently dropped.
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
        'fourth_seat_rule_of_15': True,
        'one_level_max': 21,
        'major_len': 5,                # 4 = four-card majors
        'minor': {'1C_min': 3, '1D_min': 3, 'with_33': '1C', 'with_44': '1D'},
        'nt': [{'hcp': [15, 17], 'seats': [1, 2, 3, 4], 'vul': 'any'}],   # vul: any | we | nv
        'nt_five_major': True,
        'nt_six_minor': False,
        'two_nt': [20, 21],
        'strong_2c': {'hcp': 22, 'ltc': 3, 'ltc_hcp': 17},   # 22+, or 17+ with at most 3 losers; null when 2C is not strong
        'strong_club': None,           # {'hcp': 16}: 1C artificial and forcing
        'nebulous_1d': None,           # {'min_len': 2} (Precision 1D)
        'polish_club': None,           # {'bal': [12, 14], 'strong': 18, 'clubs': [15, 17]}
        'two': {
            '2D': {'type': 'weak', 'hcp': [5, 10], 'len': [6, 6]},
            '2H': {'type': 'weak', 'hcp': [5, 10], 'len': [6, 6]},
            '2S': {'type': 'weak', 'hcp': [5, 10], 'len': [6, 6]},
        },                              # types: weak | multi | flannery | precision | natural | none
        'precision_2c': None,          # {'hcp': [11, 15]}: 6+ clubs, or 5 clubs and a 4-card major
        'three_level': {'len': 7, 'hcp_max': 10},
        'four_level': {'len': 8, 'hcp_max': 12},
        'three_nt': {'type': 'gambling'},            # gambling | natural ({'hcp': [25, 27]}) | null
    },
    'resp': {
        'two_over_one': 'gf',          # gf | standard (10+, forcing one round)
        'one_nt_to_major': 'forcing',  # forcing | semi | nf
        'single_raise': [6, 10],
        'limit_raise': [10, 12],
        'major_2nt': 'jacoby',         # jacoby | natural (13-15 balanced) | invite (11-12)
        'splinters': True,
        'weak_game_raise': True,
        'inverted_minors': False,
        'minor_2nt': [11, 12],
        'minor_3nt': [13, 15],
        'nt': {'stayman': True, 'transfers': 'jacoby', 'texas': True, 'two_spade': 'clubs', 'super_accept': True},
        'strong_2c': {'waiting': '2D', 'positive_min': 8},
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
        'jump_overcall': 'weak',       # weak | intermediate | strong
        'nt_overcall': [15, 18],
        'balancing_nt': [11, 14],
        'takeout_double_min': 12,
        'michaels': True,
        'unusual_2nt': True,
        'negative_double_thru': '2S',  # highest overcall over which a double is negative; null = none
        'vs_nt': 'natural',            # natural | cappelletti | dont | landy
        'vs_nt_double': 'penalty',
    },
    'slam': {'blackwood': 'rkc1430', 'gerber': True},
    'carding': {},                     # fields of configs/systems/_carding_fields.json (Gen 8)
}

TYPES_TWO = ('weak', 'multi', 'flannery', 'precision', 'natural', 'none')


def _merge(base, over, path, unknown):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        p = f'{path}.{k}' if path else k
        if k not in base:
            unknown.append(p)
            out[k] = v
        elif isinstance(base[k], dict) and isinstance(v, dict) and k not in ('two', 'carding'):
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
        descriptor = unflatten({k: v for k, v in descriptor.items() if k not in ('provenance', 'generator')})
        if descriptor.get('schema', SCHEMA) != SCHEMA:
            raise ValueError(f'not a {SCHEMA} document: {descriptor.get("schema")!r}')
        self.unknown = []
        self.raw = copy.deepcopy(descriptor)
        self.d = _merge(DEFAULTS, descriptor, '', self.unknown)
        if not self.d.get('id'):
            raise ValueError('a card needs an id')
        self._check()

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
        if self.d['comp']['vs_nt'] not in ('natural', 'cappelletti', 'dont', 'landy'):
            raise ValueError('comp.vs_nt must be natural | cappelletti | dont | landy')

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
