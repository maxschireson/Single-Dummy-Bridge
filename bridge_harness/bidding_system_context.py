"""Optional, public bidding-system context; never infer declarations from actor IDs.

Seat order matches auction encoding: observer, LHO, partner, RHO. Unknown
system metadata does not remove the auction or public play history.
"""
from dataclasses import dataclass
from typing import Mapping, Sequence
import random

SCHEMA = 'public-bidding-system-context-v1'
SYSTEM_IDS = {'unknown': 0, 'gen5-ben': 1, 'gen6': 2}


@dataclass(frozen=True)
class PublicSystemContext:
    ids: tuple[int, int, int, int]
    known: tuple[bool, bool, bool, bool]


def encode_system_context(declared_systems: Sequence[str | None] | None,
                          observer: int) -> PublicSystemContext:
    """Use only declarations available to the observer at decision time.

    Corpus producer/model identities belong in audit provenance, not here.
    An unrecognized declaration fails closed until the registry is versioned.
    """
    if observer not in range(4):
        raise ValueError('observer must be an absolute seat 0..3')
    systems = [None] * 4 if declared_systems is None else list(declared_systems)
    if len(systems) != 4:
        raise ValueError('provide exactly four absolute-seat declarations')
    ids = []
    for offset in range(4):
        name = systems[(observer + offset) % 4]
        if name is not None and name not in SYSTEM_IDS:
            raise ValueError(f'unregistered bidding system: {name}')
        ids.append(SYSTEM_IDS[name] if name is not None else 0)
    return PublicSystemContext(tuple(ids), tuple(i != 0 for i in ids))


def hide_system_context(context: PublicSystemContext, mode: str,
                        rng: random.Random | None = None) -> PublicSystemContext:
    """Create training views while preserving seat identities and base examples.

    'unknown' hides all declarations; 'declared' keeps supplied declarations;
    'partnership' independently hides each partnership with probability1/2.
    Apply a view per training draw; do not duplicate a deal into other splits.
    """
    if mode == 'unknown':
        keep = [False] * 4
    elif mode == 'declared':
        keep = [True] * 4
    elif mode == 'partnership':
        if rng is None:
            raise ValueError('explicit seeded RNG required for training masking')
        a, b = rng.random() >= .5, rng.random() >= .5
        keep = [a, b, a, b]
    else:
        raise ValueError(f'unknown context mode: {mode}')
    ids = tuple(i if visible else 0 for i, visible in zip(context.ids, keep))
    return PublicSystemContext(ids, tuple(i != 0 for i in ids))


def require_verified_generator(system: str, actor_sha256: str,
                               bindings: Mapping[str, Sequence[str]]) -> None:
    """Gate training provenance without revealing the actor to policy inputs."""
    if system not in SYSTEM_IDS or system == 'unknown':
        raise ValueError('training source must have an explicitly registered system')
    if len(actor_sha256) != 64 or any(c not in '0123456789abcdef' for c in actor_sha256):
        raise ValueError('invalid actor SHA256')
    if actor_sha256 not in bindings.get(system, ()):
        raise ValueError(f'generator is not pinned to system {system}')
