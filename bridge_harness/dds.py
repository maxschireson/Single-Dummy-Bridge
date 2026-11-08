import ctypes as C
import os
from pathlib import Path
import platform

DDS_REVISION = "0f969b86a4841f438fd0cdff2924c4f2404abf6a"
DDS_VARIANT = "compact-ranks+related-all-moves-v1"


class Deal(C.Structure):
    _fields_ = [("trump", C.c_int), ("first", C.c_int),
                ("suits", C.c_int * 3), ("ranks", C.c_int * 3),
                ("hands", (C.c_uint * 4) * 4)]


class Future(C.Structure):
    _fields_ = [("nodes", C.c_int), ("cards", C.c_int)] + [
        (key, C.c_int * 13) for key in ("suit", "rank", "equals", "score")]


class DDS:
    """One persistent context per player/process; never share across threads."""
    def __init__(self, path=None, tt_kind=2):
        path = path or os.environ.get("BRIDGE_DDS_LIBRARY") or Path(__file__).with_name(
            "libbridge_dds.dylib" if platform.system() == "Darwin" else "libbridge_dds.so")
        try:
            self.lib = C.CDLL(str(path))
        except OSError as e:
            raise RuntimeError("DDS is not built. Run: python3 scripts/build_dds.py") from e
        self.lib.dds_c_create_solvercontext.argtypes = [C.c_int] * 3
        self.lib.dds_c_create_solvercontext.restype = C.c_void_p
        self.lib.dds_c_destroy_solvercontext.argtypes = [C.c_void_p]
        self.lib.dds_c_destroy_solvercontext.restype = None
        self.lib.dds_c_solve_board.argtypes = [C.c_void_p, C.POINTER(Deal), C.c_int,
                                              C.c_int, C.c_int, C.POINTER(Future)]
        self.lib.dds_c_solve_board.restype = C.c_int
        self.lib.dds_c_error_message.argtypes = [C.c_int, C.c_char_p]
        self.lib.dds_c_error_message.restype = None
        self.batch_available = hasattr(self.lib, "bridge_dds_all_moves_batch")
        if self.batch_available:
            self.lib.bridge_dds_all_moves_batch.argtypes = [C.c_void_p, C.POINTER(Deal),
                C.c_int, C.c_uint, C.c_int, C.POINTER(Future), C.c_char_p, C.c_int]
            self.lib.bridge_dds_all_moves_batch.restype = C.c_int
        self.ctx = self.lib.dds_c_create_solvercontext(tt_kind, 16, 64)
        if not self.ctx:
            raise RuntimeError("Could not allocate DDS context")

    def close(self):
        if getattr(self, "ctx", None):
            self.lib.dds_c_destroy_solvercontext(self.ctx)
            self.ctx = None

    def __del__(self):
        self.close()

    @staticmethod
    def _deal(hands, trump, leader, trick):
        if len(hands) != 4 or len(trick) > 3:
            raise ValueError("Expected four hands and at most three current-trick cards")
        d = Deal(trump=trump, first=leader)
        seen = set()
        for i, (seat, c) in enumerate(trick):
            if seat != (leader + i) % 4 or not 0 <= c < 52 or c in seen:
                raise ValueError("Invalid current trick")
            seen.add(c)
            d.suits[i], d.ranks[i] = c // 13, c % 13 + 2
        for seat, hand in enumerate(hands):
            for c in hand:
                if not isinstance(c, int) or not 0 <= c < 52 or c in seen:
                    raise ValueError("Invalid or duplicate card")
                seen.add(c)
                d.hands[seat][c // 13] |= 1 << (c % 13 + 2)
        return d

    def solve(self, hands, trump, leader, trick):
        d = self._deal(hands, trump, leader, trick)
        f = Future()
        # Mode 1 handles new worlds safely; solutions=3 scores all legal cards.
        status = self.lib.dds_c_solve_board(self.ctx, C.byref(d), -1, 3, 1, C.byref(f))
        if status != 1:
            msg = C.create_string_buffer(80)
            self.lib.dds_c_error_message(status, msg)
            raise RuntimeError(f"DDS {status}: {msg.value.decode()}")
        return self._scores(f), f.nodes

    @staticmethod
    def _scores(f):
        scores = {}
        for i in range(f.cards):
            ranks = f.equals[i] | (1 << f.rank[i])
            for rank in range(2, 15):
                if ranks & (1 << rank):
                    scores[f.suit[i] * 13 + rank - 2] = f.score[i]
        return scores

    def solve_batch(self, worlds, trump, leader, trick, fixed_seats=(), retain=True):
        """Score every legal move in each world; reset proofs between batches.

        Validation rejects the entire batch before any search. The caller marks
        all visible hands as fixed, including adjacent defender/dummy pairs.
        Root scalar certificates cannot certify all moves and are not used.
        """
        if not self.batch_available:
            raise RuntimeError("Rebuild DDS for batch support: python3 scripts/build_dds.py")
        worlds = list(worlds)
        if not 1 <= len(worlds) <= 100000 or any(s not in range(4) for s in fixed_seats):
            raise ValueError("Invalid batch size or fixed seats")
        deals = (Deal * len(worlds))(*(self._deal(h, trump, leader, trick) for h in worlds))
        output = (Future * len(worlds))()
        error = C.create_string_buffer(512)
        status = self.lib.bridge_dds_all_moves_batch(self.ctx, deals, len(worlds),
            sum(1 << s for s in set(fixed_seats)), int(retain), output, error, len(error))
        if status != 1:
            raise ValueError(error.value.decode())
        return [(self._scores(f), f.nodes) for f in output]
