"""System-aware play nets (NumPy inference).

Work in progress (Gen 8 system layer, not the final form, used by no arena bot): docs/gen8_systems.md.

SystemFitScorer  the hand-fit scorer (gen6_nets.FitScorer) with one change: the table that
                 turns a call into first-layer activations depends on the system declared by
                 the side that made the call. Everything after the first layer is shared.

File format (npz): FitScorer's arrays, except

  Wa        (K, 28*38, H)   K basis call tables. A 2-D Wa is a file made before systems
                            existed and is read as one table used for every system.
  sys_ids   (S,) str        the systems this file was trained on; sys_ids[0] is 'unknown'
  sys_gate  (S, K) float32  each system's weights over the basis tables

The call table of a system is sum_k sys_gate[system, k] * Wa[k]. A slot uses the table of the
side whose seat owns the slot. The trainer's default (system_fit.py) is one shared table plus
one correction per system, so 'unknown' is the shared table alone; nothing here depends on
that choice, on the number of systems, or on which systems they are. A declared system the
file has never seen is read as 'unknown'.
"""
import numpy as np

from .gen6_nets import FitScorer, MAX_SLOTS, N_CALLS, call_ids, slot_indices
from .systems import TableSystems, UNKNOWN, normal_id

D_AUC = MAX_SLOTS * N_CALLS
OWN_ROWS = (np.arange(D_AUC) // N_CALLS) % 2 == 0      # slots of the scored seat and its partner


class SystemFitScorer:
    """log P(a hand fits the calls its seat made), given what each side has declared."""

    def __init__(self, path):
        with np.load(path, allow_pickle=False) as z:
            p = {k: z[k] for k in z.files}
        wa = p.pop('Wa')
        self.basis = wa[None] if wa.ndim == 2 else wa
        if 'sys_ids' in p:
            self.ids = tuple(str(s) for s in p.pop('sys_ids'))
            self.gates = p.pop('sys_gate').astype(np.float32)
        else:
            self.ids, self.gates = (UNKNOWN,), np.ones((1, 1), np.float32)
        self.meta = str(p.pop('meta')) if 'meta' in p else ''
        if self.ids[0] != UNKNOWN or len(set(self.ids)) != len(self.ids):
            raise ValueError("sys_ids must be distinct and start with 'unknown'")
        if self.gates.shape != (len(self.ids), len(self.basis)) or self.basis.shape[1] != D_AUC:
            raise ValueError('sys_gate, sys_ids and Wa do not agree')
        self.trunk = p
        self.unseen = set()                             # declared systems this file had to read as unknown
        self._index = {s: i for i, s in enumerate(self.ids)}
        self._tables, self._bound = {}, {}

    def index(self, system):
        """Row of a declared system; 0 ('unknown') when nothing is declared or the file never saw it."""
        system = normal_id(system)
        if system is None:
            return 0
        if system not in self._index:
            self.unseen.add(system)
            return 0
        return self._index[system]

    def _system_table(self, i):
        gate = self.gates[i]
        used = np.flatnonzero(gate)
        if len(used) == 1 and gate[used[0]] == 1:
            return self.basis[used[0]]
        out = np.zeros(self.basis.shape[1:], np.float32)
        for k in used:
            out += gate[k] * self.basis[k]
        return out

    def table(self, own, opp):
        """Call table (28*38, H) for a seat whose side plays `own` against `opp`."""
        key = (self.index(own), self.index(opp))
        if key not in self._tables:
            if len(self._tables) >= 16:
                self._tables.clear()
            mine, theirs = self._system_table(key[0]), self._system_table(key[1])
            self._tables[key] = mine if key[0] == key[1] else np.where(OWN_ROWS[:, None], mine, theirs)
        return self._tables[key]

    def bind(self, systems=None):
        """This scorer fixed to one table's declarations, with FitScorer's interface."""
        systems = systems or TableSystems()
        key = (self.index(systems.ns), self.index(systems.ew))
        if key not in self._bound:
            if len(self._bound) >= 8:
                self._bound.clear()
            self._bound[key] = BoundFitScorer(self, systems)
        return self._bound[key]

    def type_log_score(self, length, hon, seat, dealer, vulnerability, auction, systems=None):
        return self.bind(systems).type_log_score(length, hon, seat, dealer, vulnerability, auction)

    def seat_log_score(self, member, seat, dealer, vulnerability, auction, systems=None):
        return self.bind(systems).seat_log_score(member, seat, dealer, vulnerability, auction)


class BoundFitScorer(FitScorer):
    """A SystemFitScorer at one table. Only the auction's first-layer term differs from
    FitScorer, so the Gen 6 layout code can use it unchanged."""

    def __init__(self, parent, systems):
        self.p = parent.trunk
        self.systems = systems
        self.cache, self.types = {}, {}
        self.tables = (parent.table(*systems.for_seat(0)), parent.table(*systems.for_seat(1)))

    def auction_part(self, auction, dealer, seat):
        key = (tuple(auction), dealer, seat)
        if key not in self.cache:
            if len(self.cache) > 256:
                self.cache.clear()
            self.cache[key] = self.tables[seat % 2][slot_indices(call_ids(auction), dealer, seat)].sum(axis=0) + self.p['b0']
        return self.cache[key]
