"""Bridge between the Python reference solver (sure.Sure) and the C++ one (sure.cpp)."""
import json, subprocess
from sure import Sure, cards_of

BIN = './sure_cpp'


def line(s):
    """Input line for sure_cpp from a Sure instance's root state (North-South declaring)."""
    hN, hS = s.h0[0], s.h0[2]
    vE, vW = s.void0
    trick = ' '.join(str(c) for _, c in s.trick0)
    return '%d %d %x %x %x %d %d %d %d %s' % (s.trump, s.leader0, hN, hS, s.pool0, s.cnt0[0], s.cnt0[1], vE, vW, trick)


def solve(lines, *args):
    out = subprocess.run([BIN, *args], input='\n'.join(lines) + '\n', capture_output=True, text=True, check=True).stdout
    return [json.loads(l) for l in out.splitlines()]
