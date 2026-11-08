import ctypes as C
import os
from pathlib import Path
import platform

DDS_REVISION = "0f969b86a4841f438fd0cdff2924c4f2404abf6a"


class Deal(C.Structure):
    _fields_ = [("trump", C.c_int), ("first", C.c_int),
                ("suits", C.c_int * 3), ("ranks", C.c_int * 3),
                ("hands", (C.c_uint * 4) * 4)]


class Future(C.Structure):
    _fields_ = [("nodes", C.c_int), ("cards", C.c_int)] + [
        (key, C.c_int * 13) for key in ("suit", "rank", "equals", "score")]


class DDS:
    """One persistent context per player/process; never share across threads."""
    def __init__(self, path=None):
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
        self.ctx = self.lib.dds_c_create_solvercontext(1, 16, 64)
        if not self.ctx:
            raise RuntimeError("Could not allocate DDS context")

    def close(self):
        if getattr(self, "ctx", None):
            self.lib.dds_c_destroy_solvercontext(self.ctx)
            self.ctx = None

    def __del__(self):
        self.close()

    def solve(self, hands, trump, leader, trick):
        d = Deal(trump=trump, first=leader)
        for i, (_, c) in enumerate(trick):
            d.suits[i], d.ranks[i] = c // 13, c % 13 + 2
        for seat, hand in enumerate(hands):
            for c in hand:
                d.hands[seat][c // 13] |= 1 << (c % 13 + 2)
        f = Future()
        # Mode 1 handles new worlds safely; solutions=3 scores all legal cards.
        status = self.lib.dds_c_solve_board(self.ctx, C.byref(d), -1, 3, 1, C.byref(f))
        if status != 1:
            msg = C.create_string_buffer(80)
            self.lib.dds_c_error_message(status, msg)
            raise RuntimeError(f"DDS {status}: {msg.value.decode()}")
        scores = {}
        for i in range(f.cards):
            ranks = f.equals[i] | (1 << f.rank[i])
            for rank in range(2, 15):
                if ranks & (1 << rank):
                    scores[f.suit[i] * 13 + rank - 2] = f.score[i]
        return scores, f.nodes
