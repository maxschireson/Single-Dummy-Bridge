"""Bidding and carding systems as data: packages, registry, table declarations.

Work in progress (Gen 8 system layer, not the final form, used by no arena bot): docs/gen8_systems.md.

A system package is what one partnership plays and can be asked about. It is one JSON file
under configs/systems/ with three parts that are kept apart:

  bidding     the public declaration: a convention card (any format), a structured
              descriptor, notes
  carding     the public carding agreements, as a descriptor over the fields listed in
              configs/systems/_carding_fields.json
  generators  the bidders verified to bid this system, identified by SHA-256. Provenance
              only: it gates which auctions may be labelled with the system and is never a
              model input.

Nothing here names a particular system or assumes how many there are. Nets do not depend on
the registry's order either: each system-aware net file lists the system ids it was trained
on (system_nets.py) and reads any other declared system as "unknown".
"""
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Iterable, Mapping, Sequence

SCHEMA = 'system-package-v1'
CARDING_SCHEMA = 'carding-fields-v1'
UNKNOWN = 'unknown'
STATUSES = ('active', 'draft', 'retired')
VIEWS = ('declared', 'unknown', 'partnership')
DEFAULT_DIR = Path(__file__).resolve().parents[1] / 'configs' / 'systems'

_ID = re.compile(r'[a-z0-9][a-z0-9._-]{0,63}')
_SHA = re.compile(r'[0-9a-f]{64}')
_KEYS = {'schema', 'id', 'display_name', 'status', 'family', 'bidding', 'carding', 'generators', 'lineage', 'notes'}


def normal_id(system):
    """None when nothing is declared ('unknown' counts as nothing); otherwise the id."""
    return None if system in (None, UNKNOWN) else system


@dataclass(frozen=True)
class SystemPackage:
    id: str
    display_name: str
    status: str
    bidding: Mapping
    carding: Mapping
    generators: tuple
    lineage: Mapping

    @classmethod
    def from_dict(cls, d):
        if d.get('schema') != SCHEMA:
            raise ValueError(f'not a {SCHEMA} document: {d.get("schema")!r}')
        extra = set(d) - _KEYS
        if extra:
            raise ValueError(f'unknown keys in system package: {sorted(extra)}')
        sid = d.get('id')
        if not isinstance(sid, str) or not _ID.fullmatch(sid) or sid == UNKNOWN:
            raise ValueError(f'invalid system id: {sid!r}')
        status = d.get('status', 'draft')
        if status not in STATUSES:
            raise ValueError(f'{sid}: status must be one of {STATUSES}')
        bidding, carding = dict(d.get('bidding') or {}), dict(d.get('carding') or {})
        for name, part in (('bidding', bidding), ('carding', carding)):
            if not isinstance(part.get('descriptor', {}), Mapping):
                raise ValueError(f'{sid}: {name}.descriptor must be an object')
        card = bidding.get('card')
        if card is not None and not (isinstance(card, Mapping) and isinstance(card.get('format'), str)):
            raise ValueError(f'{sid}: bidding.card must be null or an object with a format')
        generators = []
        for g in d.get('generators') or ():
            if not isinstance(g, Mapping) or not isinstance(g.get('kind'), str):
                raise ValueError(f'{sid}: every generator needs a kind')
            sha = g.get('sha256')
            if sha is None and status == 'active':
                raise ValueError(f'{sid}: an active system pins every generator by sha256')
            if sha is not None and not (isinstance(sha, str) and _SHA.fullmatch(sha)):
                raise ValueError(f'{sid}: invalid generator sha256')
            generators.append(dict(g))
        return cls(sid, d.get('display_name') or sid, status, bidding, carding, tuple(generators), dict(d.get('lineage') or {}))

    def generator(self, kind=None):
        """The first generator (of a kind, if given)."""
        for g in self.generators:
            if kind is None or g['kind'] == kind:
                return g
        raise ValueError(f'{self.id}: no generator' + (f' of kind {kind}' if kind else ''))


class SystemRegistry:
    """The registered packages. A declared id that is not registered fails closed."""

    def __init__(self, packages: Iterable[SystemPackage], carding_fields: Mapping[str, Sequence[str]] | None = None):
        self._by_id, self._by_sha = {}, {}
        self.carding_fields = {k: tuple(v) for k, v in (carding_fields or {}).items()}
        for p in packages:
            if p.id in self._by_id:
                raise ValueError(f'duplicate system id: {p.id}')
            for g in p.generators:
                sha = g.get('sha256')
                if sha and self._by_sha.setdefault(sha, p.id) != p.id:
                    raise ValueError(f'generator {sha[:12]} is pinned to both {self._by_sha[sha]} and {p.id}')
            if self.carding_fields:
                for field, value in (p.carding.get('descriptor') or {}).items():
                    if field not in self.carding_fields or _text(value) not in self.carding_fields[field]:
                        raise ValueError(f'{p.id}: carding {field}={value!r} is not in the carding field list')
            self._by_id[p.id] = p

    @classmethod
    def load(cls, directory=DEFAULT_DIR):
        """Every *.json in the directory is a package, except names starting with '_'."""
        directory = Path(directory)
        fields = None
        path = directory / '_carding_fields.json'
        if path.exists():
            doc = json.loads(path.read_text())
            if doc.get('schema') != CARDING_SCHEMA:
                raise ValueError(f'{path}: not a {CARDING_SCHEMA} document')
            fields = doc['fields']
        packages = []
        for path in sorted(directory.glob('*.json')):
            if path.name.startswith('_'):
                continue
            package = SystemPackage.from_dict(json.loads(path.read_text()))
            if package.id != path.stem:
                raise ValueError(f'{path}: file name and id {package.id!r} differ')
            packages.append(package)
        return cls(packages, fields)

    def ids(self):
        return tuple(sorted(self._by_id))

    def __contains__(self, system):
        return system in self._by_id

    def __getitem__(self, system):
        if system not in self._by_id:
            raise KeyError(f'unregistered system: {system!r}')
        return self._by_id[system]

    def check_declared(self, system):
        """A declaration is nothing, or a registered id."""
        if normal_id(system) is not None and system not in self._by_id:
            raise ValueError(f'unregistered system: {system!r}')

    def system_of_generator(self, sha256):
        return self._by_sha.get(sha256)

    def require_generator(self, system, sha256):
        """Refuse to label auctions with a system unless this exact generator is pinned to it."""
        if self._by_sha.get(sha256) != system or system not in self._by_id:
            raise ValueError(f'generator {str(sha256)[:12]} is not pinned to system {system!r}')


@dataclass(frozen=True)
class TableSystems:
    """What each side has declared at one table. None = nothing declared."""
    ns: str | None = None
    ew: str | None = None

    def __post_init__(self):
        object.__setattr__(self, 'ns', normal_id(self.ns))
        object.__setattr__(self, 'ew', normal_id(self.ew))

    @classmethod
    def from_seats(cls, declared: Sequence[str | None]):
        """From four declarations in seat order N, E, S, W. Partners play one system."""
        if len(declared) != 4:
            raise ValueError('provide exactly four seat declarations')
        d = [normal_id(x) for x in declared]
        if d[0] != d[2] or d[1] != d[3]:
            raise ValueError('partners must declare the same system')
        return cls(d[0], d[1])

    def of(self, seat):
        return self.ns if seat % 2 == 0 else self.ew

    def for_seat(self, seat):
        """(own side's system, opponents' system) for a seat."""
        return (self.ns, self.ew) if seat % 2 == 0 else (self.ew, self.ns)

    def view(self, mode, rng=None):
        """A training view: 'declared' as is, 'unknown' hides both sides, 'partnership' hides
        each side independently with probability 1/2 (needs a seeded random.Random)."""
        if mode == 'declared':
            return self
        if mode == 'unknown':
            return TableSystems()
        if mode == 'partnership':
            if rng is None:
                raise ValueError('an explicit seeded rng is required')
            return TableSystems(self.ns if rng.random() >= .5 else None, self.ew if rng.random() >= .5 else None)
        raise ValueError(f'unknown view: {mode}')


def _text(value):
    if isinstance(value, bool):
        return '1' if value else '0'
    return str(value).strip().lower()


class DescriptorVocabulary:
    """A fixed, ordered encoding of open key/value descriptors (carding fields, card switches).

    Each field is a one-hot over its listed values with one leading 'unspecified' slot, so a
    missing field, or a value the vocabulary has never seen, is still representable. A net
    stores the vocabulary it was trained with; the registry can grow without changing it.
    """

    def __init__(self, fields: Mapping[str, Sequence]):
        self.fields = {str(k): tuple(_text(v) for v in values) for k, values in fields.items()}
        self.offsets, n = {}, 0
        for k, values in self.fields.items():
            if len(set(values)) != len(values):
                raise ValueError(f'duplicate values in field {k}')
            self.offsets[k] = n
            n += 1 + len(values)
        self.size = n

    @classmethod
    def from_descriptors(cls, descriptors: Iterable[Mapping]):
        """Every field and value that occurs in a population of descriptors, in sorted order."""
        fields = {}
        for d in descriptors:
            for k, v in (d or {}).items():
                fields.setdefault(str(k), set()).add(_text(v))
        return cls({k: sorted(fields[k]) for k in sorted(fields)})

    def encode(self, descriptor: Mapping | None):
        import numpy as np
        x = np.zeros(self.size, np.float32)
        descriptor = descriptor or {}
        for k, values in self.fields.items():
            v = _text(descriptor[k]) if k in descriptor else None
            x[self.offsets[k] + (1 + values.index(v) if v in values else 0)] = 1
        return x

    def to_json(self):
        return json.dumps({k: list(v) for k, v in self.fields.items()})

    @classmethod
    def from_json(cls, text):
        return cls(json.loads(text))


CARD_READERS = {}       # card format -> function(text) -> descriptor. No format has a reader yet.


def card_descriptor(card: Mapping, root='.'):
    """Read a package's convention card into a descriptor, when its format has a reader."""
    reader = CARD_READERS.get(card.get('format'))
    if reader is None or not card.get('path'):
        raise ValueError(f'no reader for card format {card.get("format")!r}, or the card has no path')
    return reader((Path(root) / card['path']).read_text(errors='replace'))
