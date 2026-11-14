"""Personas at the play server (sidplay/personas.py): drawn per board, passed to Sid by seat, shown to the person as
told during the board and as they were after it, kept for a deal played again, and Sid's own table playing the same
North, East and West with a plain South.

Needs a bundle source with bridge_harness/persona.py: SIDPLAY_TEST_SOURCE=/path/to/checkout (skipped without it). The
server runs in a child process, since the play tests start theirs without personas.

  cd play && SIDPLAY_TEST_SOURCE=~/loopsrc python -m pytest tests/test_personas.py -q
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = os.environ.get('SIDPLAY_TEST_SOURCE', '')
HAVE = bool(SOURCE) and (Path(SOURCE) / 'bridge_harness' / 'persona.py').is_file()

CHILD = r'''
import sys, time
sys.path.insert(0, ROOT)
from fastapi.testclient import TestClient
from sidplay import app as appmod, fake_engine
from tests.test_play import H, play_board, state, wait_for

assert appmod.CONFIG.personas and appmod.CONFIG.variable_id == 'SidVariable'
with TestClient(appmod.app) as c:
    me = c.get('/api/me').json()
    assert me['bot']['variable'] == 'SidVariable' and len(me['bot']['personas']) == 4
    tid = c.post('/api/tables', json={}, headers=H).json()['table']
    s = state(c, tid)
    told = s['board']['personas']['told']
    assert set(told) == {'N', 'E', 'W'} and all(isinstance(v, str) and v for v in told.values())
    assert s['board']['personas']['actual'] is None                      # not while the board is played
    s = play_board(c, tid, bid_first='7N')
    s = wait_for(c, tid, lambda s: s['board']['sid'] not in ('pending', None))
    actual = s['board']['personas']['actual']
    assert set(actual) == {'N', 'E', 'W'} and set(actual['E']['bid']) == {'aggressive', 'shape', 'random', 'near'}
    # Sid got its seat's persona: every call and card of N, E, W carried a style, and none of South's (the person's)
    seats_bid = {seat for seat, st in fake_engine.SEEN['bid_styles'] if st}
    assert seats_bid <= {0, 1, 3} and seats_bid
    assert all(st and st['near'] == 0.05 and set(st['play']) >= {'tempo', 'active', 'high', 'random'}
               for seat, st in fake_engine.SEEN['play_styles'] if seat in (1, 3))
    assert all(st is None for seat, st in fake_engine.SEEN['bid_styles'] if seat == 2)      # Sid's South is plain
    sp = fake_engine.SEEN['sid_personas'][-1]
    assert sorted(sp) == [0, 1, 3]                                        # Sid's own table: the same Sids, South plain
    bid1 = s['board']['board_id']
    detail = c.get(f'/api/boards/{bid1}').json()
    assert detail['personas']['actual']['W']['text'] == actual['W']['text']
    # The next board draws new personas; a deal played again keeps its own.
    assert c.post(f'/api/tables/{tid}/next', json={}, headers=H).status_code == 200
    rid = c.post('/api/tables', json={'replay': bid1}, headers=H).json()['table']
    assert state(c, rid)['board']['personas']['told'] == told
print('ok')
'''


@pytest.mark.skipif(not HAVE, reason='SIDPLAY_TEST_SOURCE does not name a checkout with bridge_harness/persona.py')
def test_personas_end_to_end():
    env = dict(os.environ, SIDPLAY_ENGINE='fake', SIDPLAY_DATA=tempfile.mkdtemp(), SIDPLAY_PACE='0', SIDPLAY_TRICK_PAUSE='0',
               SIDPLAY_WORKERS='2', SIDPLAY_BACKGROUND_WORKERS='1', SIDPLAY_SOURCE=SOURCE, SIDPLAY_ANALYSIS='0')
    code = 'ROOT = %r\n' % str(ROOT) + CHILD.replace("os.environ.update(", "dict(")
    r = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0 and r.stdout.strip().endswith('ok'), r.stdout[-3000:] + r.stderr[-3000:]
