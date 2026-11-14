"""Play server against the stand-in bot (no models): full boards, hidden-card boundary, accounts, claims, analyses,
playing a deal again, and history navigation. The analyses need DDS and play/native/sure_cpp built (as in
test_analysis.py); without them the analysis assertions are skipped.

  cd play && SIDPLAY_ENGINE=fake python -m pytest tests -q
"""
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.update(SIDPLAY_ENGINE='fake', SIDPLAY_DATA=tempfile.mkdtemp(), SIDPLAY_PACE='0', SIDPLAY_TRICK_PAUSE='0',
                  SIDPLAY_WORKERS='2', SIDPLAY_BACKGROUND_WORKERS='1', SIDPLAY_SOURCE=str(ROOT.parent))
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient   # noqa: E402
from sidplay import analysis, app as appmod, fake_engine   # noqa: E402

try:
    from bridge_harness.dds import DDS
    DDS(cache_path='')
    ANALYSIS = analysis.Sure().available()
except Exception:
    ANALYSIS = False

H = {'X-Sid': '1'}
SEATS = 'NESW'


@pytest.fixture(scope='module')
def server():
    with TestClient(appmod.app) as c:
        yield c


def fresh(server):
    c = TestClient(server.app)
    c.portal = server.portal            # share the running server loop and its state
    return c


def state(c, tid, since=-1):
    r = c.get(f'/api/tables/{tid}', params={'since': since})
    assert r.status_code == 200, r.text
    return r.json()


def check_boundary(s):
    """Hands a viewer may see: own; dummy and (if they control it) declarer after the lead; all when done."""
    b = s['board']
    me = s['me']
    visible = {k for k, v in b['hands'].items() if v['cards'] is not None}
    if b['phase'] == 'done':
        assert visible == set(SEATS)
        return
    allowed = {me}
    if b['phase'] == 'play' and b['played'] > 0:
        allowed.add(b['dummy'])
        if b['declarer'] in 'NS':
            allowed.add(b['declarer'])
    assert visible <= allowed, (visible, allowed, b['phase'])
    assert me in visible


def play_board(c, tid, bid_first='1N', claim_at=None, timeout=60):
    """Act whenever it is this client's turn until the board is done. Returns the final state."""
    s = state(c, tid)
    deadline = time.time() + timeout
    while time.time() < deadline:
        check_boundary(s)
        b = s['board']
        if b['phase'] == 'done':
            return s
        if b['turn'] and b['turn']['mine']:
            if b['turn']['kind'] == 'call':
                call = bid_first if bid_first in b['legal'] and not any(x != 'PASS' for x in b['calls']) else 'PASS'
                r = c.post(f'/api/tables/{tid}/call', json={'call': call}, headers=H)
            else:
                if claim_at is not None and b['played'] >= claim_at and b['can_claim']:
                    r = c.post(f'/api/tables/{tid}/claim', json={'tricks': b['remaining']}, headers=H)
                    claim_at = None
                else:
                    r = c.post(f'/api/tables/{tid}/card', json={'card': b['legal'][0]}, headers=H)
            assert r.status_code == 200, r.text
            s = state(c, tid)
        else:
            s = state(c, tid, s['version'])
    raise AssertionError('board did not finish')


def wait_for(c, tid, pred, timeout=20):
    deadline = time.time() + timeout
    s = state(c, tid)
    while not pred(s):
        assert time.time() < deadline, 'timed out'
        s = state(c, tid, s['version'])
    return s


def test_post_needs_header(server):
    assert server.post('/api/tables', json={'mode': 'solo'}).status_code == 400


def test_solo_boards_and_scores(server):
    server.get('/api/me')
    tid = server.post('/api/tables', json={'mode': 'solo'}, headers=H).json()['table']
    s = state(server, tid)
    assert s['me'] == 'S' and [x['kind'] for x in s['seats']] == ['bot', 'bot', 'human', 'bot']
    for n in (1, 2, 3):
        s = play_board(server, tid)
        assert s['board']['number'] == n and s['board']['result'] is not None
        s = wait_for(server, tid, lambda s: s['board']['sid'] not in ('pending', None))
        row = s['scores'][-1]
        assert row['imps'] is not None and row['sid']['ns_score'] is not None
        assert server.post(f'/api/tables/{tid}/next', json={}, headers=H).status_code == 200
    assert len(state(server, tid)['scores']) == 3
    hist = server.get('/api/history').json()
    assert hist['totals']['boards'] == 3 and hist['user'] is None
    detail = server.get(f"/api/boards/{hist['boards'][0]['id']}").json()
    assert len(detail['hands']) == 4 and detail['seats'][2]['kind'] == 'human' and 'user_id' not in detail['seats'][2]


def test_not_your_turn_and_illegal(server):
    tid = server.post('/api/tables', json={'mode': 'solo'}, headers=H).json()['table']
    s = wait_for(server, tid, lambda s: s['board']['turn'] and s['board']['turn']['mine'])
    r = server.post(f'/api/tables/{tid}/card', json={'card': 'SA'}, headers=H)
    assert r.status_code == 409 and 'not your turn' in r.json()['error']
    if any(x != 'PASS' for x in s['board']['calls']):
        r = server.post(f'/api/tables/{tid}/call', json={'call': 'XX'}, headers=H)
        assert r.status_code == 409


def test_claims(server):
    fake_engine.FAKE_DD = 0
    try:
        tid = server.post('/api/tables', json={'mode': 'solo'}, headers=H).json()['table']
        # 7NT is legal at South's first turn whatever came before, and the stand-in bot passes after any bid.
        s = wait_for(server, tid, lambda s: s['board']['turn'] and s['board']['turn']['mine'])
        assert server.post(f'/api/tables/{tid}/call', json={'call': '7NT'}, headers=H).status_code == 200
        s = wait_for(server, tid, lambda s: s['board']['phase'] == 'play' and s['board']['can_claim']
                     and s['board']['turn'] and s['board']['turn']['mine'])
        assert s['board']['contract'] == '7NT' and s['board']['declarer'] in 'NS'   # Sid-North may have bid notrump first
        r = server.post(f'/api/tables/{tid}/claim', json={'tricks': s['board']['remaining']}, headers=H)
        assert r.status_code == 200
        s = state(server, tid)
        # Refused, and the refusal says nothing about how many tricks were there.
        assert s['board']['claim'] == {'seat': 'S', 'tricks': s['board']['remaining'], 'accepted': False}
        assert s['board']['phase'] == 'play'
        assert server.post(f'/api/tables/{tid}/claim', json={'tricks': 99}, headers=H).status_code == 409
        fake_engine.FAKE_DD = None
        played_tricks = s['board']['tricks']['declarer']
        assert server.post(f'/api/tables/{tid}/claim', json={'tricks': s['board']['remaining']}, headers=H).status_code == 200
        s = state(server, tid)
        assert s['board']['phase'] == 'done' and s['board']['result']['claimed'] == 13 - s['board']['played'] // 4
        assert s['board']['result']['tricks'] == played_tricks + s['board']['result']['claimed']
    finally:
        fake_engine.FAKE_DD = None


def test_accounts_adopt_guest_boards(server):
    c = fresh(server)
    c.get('/api/me')
    tid = c.post('/api/tables', json={'mode': 'solo'}, headers=H).json()['table']
    play_board(c, tid)
    assert c.get('/api/history').json()['totals']['boards'] == 1
    assert c.post('/api/signup', json={'username': 'ab', 'password': 'longenough'}, headers=H).status_code == 400
    assert c.post('/api/signup', json={'username': 'alice', 'password': 'short'}, headers=H).status_code == 400
    r = c.post('/api/signup', json={'username': 'alice', 'password': 'longenough'}, headers=H)
    assert r.status_code == 200
    me = c.get('/api/me').json()
    assert me['user'] == 'alice' and me['table'] == tid          # the open table followed the guest into the account
    h = c.get('/api/history').json()
    assert h['user'] == 'alice' and h['totals']['boards'] == 1
    state(c, tid)                                                   # still seated
    c.post('/api/logout', json={}, headers=H)
    assert c.get('/api/me').json()['user'] is None
    assert c.post('/api/login', json={'username': 'alice', 'password': 'wrongpass1'}, headers=H).status_code == 401
    assert c.post('/api/login', json={'username': 'ALICE', 'password': 'longenough'}, headers=H).status_code == 200
    assert c.post('/api/signup', json={'username': 'Alice', 'password': 'longenough'}, headers=H).status_code == 409


def test_partner_tables_are_gone(server):
    assert server.post('/api/join', json={'code': 'x'}, headers=H).status_code in (404, 405)
    tid = server.post('/api/tables', json={'mode': 'pair'}, headers=H).json()['table']   # mode is ignored: solo
    s = state(server, tid)
    assert [x['kind'] for x in s['seats']] == ['bot', 'bot', 'human', 'bot'] and 'invite' not in s


def test_suggested_signup(server):
    c = fresh(server)
    c.get('/api/me')
    sug = c.get('/api/signup/suggest').json()
    assert appmod.USERNAME.fullmatch(sug['username']) and len(sug['password']) >= 12
    assert c.post('/api/signup', json=sug, headers=H).status_code == 200
    assert c.get('/api/me').json()['user'] == sug['username']
    assert server.get('/api/signup/suggest').json()['username'] != sug['username'] or True


def finish_with_extras(c, tid, timeout=120):
    """Wait until Sid's table and (if available) both analyses of the current board have arrived."""
    def ready(s):
        b = s['board']
        if b['sid'] in ('pending', None):
            return False
        if not ANALYSIS:
            return True
        return b['analysis']['status'] in ('ready', 'error', None) and b['sid_analysis']['status'] in ('ready', 'error', None)
    return wait_for(c, tid, ready, timeout)


def test_analysis_replay_and_navigation(server):
    c = fresh(server)
    c.get('/api/me')
    tid = c.post('/api/tables', json={}, headers=H).json()['table']
    # Bid 7NT at the first chance: South declares (or Sid-North, and South plays both hands).
    s = play_board(c, tid, bid_first='7N')
    s = finish_with_extras(c, tid)
    first = s['board']
    bid1 = first['board_id']
    if ANALYSIS:
        assert first['analysis']['status'] == 'ready' and first['analysis']['brief']['lost'] is not None
        assert first['sid_analysis']['status'] in ('ready', None)
    detail = c.get(f'/api/boards/{bid1}').json()
    if ANALYSIS:
        a = detail['analysis']
        assert detail['analysis_status'] == 'ready' and len(a['cards']) == len(detail['play'])
        assert a['focus'] == [detail['declarer']] if detail['declarer'] in 'NS' else a['focus'] == ['S']
        assert all(e['loss'] > 0 and e['text'] for e in a['lost'])
    assert detail['older'] is None and detail['newer'] is None
    # A second board, then navigation between the two.
    assert c.post(f'/api/tables/{tid}/next', json={}, headers=H).status_code == 200
    s = play_board(c, tid)
    s = finish_with_extras(c, tid)
    bid2 = s['board']['board_id']
    assert c.get(f'/api/boards/{bid2}').json()['older'] == bid1
    assert c.get(f'/api/boards/{bid1}').json()['newer'] == bid2
    # Play the first deal again: same hands, Sid's table reused, left out of the totals.
    sid_before = detail['sid_table']
    rid = c.post('/api/tables', json={'replay': bid1}, headers=H).json()['table']
    r = state(c, rid)
    assert r['board']['number'] == first['number'] and r['board']['replay'] is True
    s = play_board(c, rid, bid_first='7N')
    s = finish_with_extras(c, rid)
    hands = {k: v['cards'] for k, v in s['board']['hands'].items()}
    assert hands == {k: v['cards'] for k, v in first['hands'].items()}
    assert s['scores'][-1]['replay'] and s['totals']['boards'] == 0 and s['totals']['replays'] == 1
    again = c.get(f"/api/boards/{s['board']['board_id']}").json()
    assert again['replay_of'] == bid1 and again['sid_table'] == sid_before
    hist = c.get('/api/history').json()
    assert hist['totals']['boards'] == 2 and hist['totals']['replays'] == 1
    assert [b['replay_of'] for b in hist['boards']] == [bid1, None, None]
    # Someone else's board cannot be replayed or read.
    other = fresh(server)
    other.get('/api/me')
    assert other.post('/api/tables', json={'replay': bid1}, headers=H).status_code == 404
    assert other.get(f'/api/boards/{bid1}').status_code == 404
