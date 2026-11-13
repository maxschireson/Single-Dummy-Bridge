"""Play whole boards against a running play server through its public API (standard library only).

  python play/smoke.py http://127.0.0.1:8090 --boards 2

The player passes throughout (bidding 3NT once if it gets the chance, so some boards are declared) and plays its
first legal card. It checks that no hidden hand is ever sent, that each board ends with a result, and (with
--sid) that Sid's own table and the IMPs arrive. Exit status 0 on success.
"""
import argparse
import http.cookiejar
import json
import sys
import time
import urllib.request


class Client:
    def __init__(self, base):
        self.base = base.rstrip('/')
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
                                                  urllib.request.ProxyHandler({}))

    def call(self, method, path, body=None, timeout=60):
        data = json.dumps(body or {}).encode() if method == 'POST' else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={'X-Sid': '1', 'Content-Type': 'application/json'})
        with self.opener.open(req, timeout=timeout) as r:
            return json.load(r)


def check_hidden(s):
    b = s['board']
    visible = {k for k, v in b['hands'].items() if v['cards'] is not None}
    if b['phase'] == 'done':
        assert visible == set('NESW'), 'not all hands shown at the end'
        return
    allowed = {s['me']}
    if b['phase'] == 'play' and b['played']:
        allowed |= {b['dummy']} | ({b['declarer']} if b['declarer'] in 'NS' else set())
    assert visible <= allowed, f'hidden hand sent: {visible - allowed}'


def play_board(c, tid, timeout):
    s = c.call('GET', f'/api/tables/{tid}')
    bid = True
    started = time.time()
    while time.time() - started < timeout:
        check_hidden(s)
        b = s['board']
        if b['error']:
            raise SystemExit(f'table error: {b["error"]}')
        if b['phase'] == 'done':
            return s
        if b['turn'] and b['turn']['mine']:
            if b['turn']['kind'] == 'call':
                call = '3N' if bid and '3N' in b['legal'] else 'PASS'
                bid = bid and call != '3N'
                c.call('POST', f'/api/tables/{tid}/call', {'call': call})
            else:
                c.call('POST', f'/api/tables/{tid}/card', {'card': b['legal'][0]})
            s = c.call('GET', f'/api/tables/{tid}')
        else:
            s = c.call('GET', f'/api/tables/{tid}?since={s["version"]}')
    raise SystemExit('board did not finish in time')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('base')
    p.add_argument('--boards', type=int, default=1)
    p.add_argument('--sid', action='store_true', help="also wait for Sid's own table and the IMPs")
    p.add_argument('--timeout', type=float, default=600)
    a = p.parse_args()
    c = Client(a.base)
    print(json.dumps(c.call('GET', '/api/health')))
    c.call('GET', '/api/me')
    tid = c.call('POST', '/api/tables', {'mode': 'solo'})['table']
    for n in range(a.boards):
        t0 = time.time()
        s = play_board(c, tid, a.timeout)
        r = s['board']['result']
        line = dict(board=s['board']['number'], contract=r['contract'], declarer=r['declarer'], tricks=r['tricks'],
                    score=r['ns_score'], seconds=round(time.time() - t0, 1))
        if a.sid:
            while s['board']['sid'] in ('pending', None) and time.time() - t0 < a.timeout:
                s = c.call('GET', f'/api/tables/{tid}?since={s["version"]}')
            assert s['board']['sid'] not in ('pending', 'error', None), f'Sid table: {s["board"]["sid"]}'
            line.update(sid=s['board']['sid']['contract'], sid_score=s['board']['sid']['ns_score'], imps=s['board']['imps'],
                        with_sid_seconds=round(time.time() - t0, 1))
        print(json.dumps(line), flush=True)
        if n + 1 < a.boards:
            c.call('POST', f'/api/tables/{tid}/next')
    c.call('POST', f'/api/tables/{tid}/leave')
    hist = c.call('GET', '/api/history')
    assert hist['totals']['boards'] >= a.boards, 'boards missing from history'
    print(json.dumps(dict(ok=True, history_boards=hist['totals']['boards'])))


if __name__ == '__main__':
    sys.exit(main())
