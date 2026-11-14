#!/usr/bin/env python3
"""The USBC's bidding and play records from LoveBridge vugraph's public archive (Max, 06:55 to 07:01 UTC on 14 November
2026: grade the bot on the boards played in the USBCs since 2021 or 2022, on lost tricks as declarer and defender).

  python3 harvest.py OUT_DIR [--since 2021-01] [--pause 0.25] [--limit N]

TEST DATA ONLY: never a training set. Writes OUT_DIR/<miniSessionId>.json.gz (the session's facts, its boards and every
table's record) and OUT_DIR/index.json. It resumes: a session already written is skipped.

Where the data is (read from the vugraph app's own script, vugraph.lovebridge.com/assets/index-*.js):
  /api/archive/miniSessions                      every archived session (id, event, stage, rounds, boards)
  /api/archive/boards/{session}                  the deals (hands, dealer, vulnerability, double-dummy table)
  /api/archive/teams/{session}                   teams and players
  /api/archive/tables/{session}/{round}          a round's matches: home and visiting team ids
  /api/archive/watch/{session}/{ns team}/{board} one table's events: FULL (deal, auction `bg`, tricks `tr`, players,
                                                 result), each card, the claim, the result. The open room's N-S is the
                                                 home team, the closed room's the visiting team.
Sessions of later USBCs that the archive list leaves out are found from USBF's own bracket and round-robin pages
(usbf.org/docs/vugraphs/<event>/...), which link vugraph screens usbc/<id>; their sessions are usbc_<id>_<s>_<m>.
"""
import argparse, gzip, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

VG = 'https://vugraph.lovebridge.com'
UA = 'Mozilla/5.0 (research; USBF bidding and play records for bot evaluation)'
EVENTS = ('Open', 'Women', 'Senior', 'Mixed', 'Junior', 'Beth Palmer', 'USBC')      # USBF's championships; ACBL events share the server
NOT_USBF = ('Spingold', 'Vanderbilt', 'Reisinger', 'Wagar', 'Baze', 'Soloway', 'Mitchell', 'Roth', 'NABC', 'GNT', 'Grand National')
USBF_PAGES = ['https://usbf.org/2026-usbcs', 'https://usbf.org/2026-usbcs/2026-usbcs-results', 'https://usbf.org/past-tournaments',
              'https://usbf.org/past-tournaments/2025-usbcs', 'https://usbf.org/past-tournaments/2024-usbcs',
              'https://usbf.org/past-tournaments/2024-sam-amer-jusbc', 'https://usbf.org/2026-sam-amer-jusbc', 'https://usbf.org/past-tournaments/2023-usbcs',
              'https://usbf.org/past-tournaments/2022-open-usbc', 'https://usbf.org/past-tournaments/2022-michael-seamon-junior-usbc']


class Client:
    def __init__(self, pause):
        self.pause, self.calls, self.last = pause, 0, 0.

    def get(self, url, as_json=True):
        wait = self.pause - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        for attempt in range(4):
            self.last = time.time()
            try:
                req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json' if as_json else '*/*'})
                with urllib.request.urlopen(req, timeout=40) as r:
                    body = r.read()
                self.calls += 1
                if not as_json:
                    return body.decode('utf-8', 'replace')
                return json.loads(body) if body.strip() else None
            except urllib.error.HTTPError as e:
                if e.code in (400, 404):
                    return None
                time.sleep(5 * (attempt + 1))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
                time.sleep(5 * (attempt + 1))
        return None


def usbf_screens(c):
    """vugraph screen ids (usbc/<id>) linked from USBF's pages: its tournament pages for 2022 to 2026 (results, brackets,
    round-robin and vugraph pages) and the bracket and round-robin sheets under docs/vugraphs/, with the page that links them."""
    seen, todo, screens = set(), [(u, 0) for u in USBF_PAGES], {}
    while todo and len(seen) < 600:
        url, depth = todo.pop(0)
        if url in seen:
            continue
        seen.add(url)
        html = c.get(url, as_json=False)
        if not html:
            continue
        for sid in re.findall(r'lovebridge\.com/screen/usbc/(\d+)', html):
            screens.setdefault(sid, url)
        for href in re.findall(r'(?:href|src)="([^"]+)"', html):
            u = urllib.parse.urljoin(url, href.replace('&amp;', '&')).split('#')[0]
            low = u.lower()
            if not re.match(r'https?://(www\.)?usbf\.org/', low) or low.endswith(('.pdf', '.jpg', '.png', '.ico', '.css', '.js', '.gif')):
                continue
            if 'docs/vugraphs/' in low and ('bracket.php' in low or 'rrsheet.php' in low):
                todo.append((u, depth + 1))
            elif depth < 3 and re.search(r'usbc|vugraph|bracket|round-robin|play-records|results', low) and re.search(r'202[2-6]|usbc', low) \
                    and 'index.php' not in low and 'search' not in low:
                todo.append((u, depth + 1))
    return screens


def sessions(c, since, extra=()):
    out = {}
    for m in c.get(f'{VG}/api/archive/miniSessions') or []:
        sid, text = m['miniSessionId'], ' '.join(str(m.get(k) or '') for k in ('namePlus', 'eventName', 'tournamentName', 'name'))
        if sid.startswith('usbc_') and m.get('type') == 'TEAM' and m.get('startDateTime', '')[:7] >= since \
                and any(w in text for w in EVENTS) and not any(w in text for w in NOT_USBF):
            out[sid] = m
    screens = usbf_screens(c)
    for sid in extra:                                   # screen ids given by hand (--screens)
        screens.setdefault(str(sid), 'given')
    for screen, page in screens.items():
        for s in range(1, 13):
            found = False
            for mini in range(1, 5):
                sid = f'usbc_{screen}_{s}_{mini}'
                if sid in out:
                    found = True
                    continue
                boards = c.get(f'{VG}/api/archive/boards/{sid}')
                if not boards:
                    break
                found = True
                out[sid] = dict(miniSessionId=sid, from_usbf_page=page, screen=screen, boards_seen=len(boards))
            if not found and s > 1:
                break
    return out


def harvest(c, sid, meta):
    boards = c.get(f'{VG}/api/archive/boards/{sid}') or []
    teams = c.get(f'{VG}/api/archive/teams/{sid}') or []
    rounds = c.get(f'{VG}/api/archive/rounds/{sid}') or {}
    first = int(meta.get('firstRound') or 0)
    n = int(meta.get('numberOfRounds') or 0)
    round_list = (rounds.get('rounds') if isinstance(rounds, dict) else None) or list(range(first, first + max(n, 1))) or [0, 1]
    matches = {}
    for r in round_list:
        r = r.get('round', r) if isinstance(r, dict) else r
        for t in c.get(f'{VG}/api/archive/tables/{sid}/{r}') or []:
            matches[(t['home'], t['visiting'])] = t
    if not matches:                                     # no round list: every pair of teams is tried as a match
        ids = [t['registrationId'] for t in teams]
        matches = {(a, b): {} for a in ids for b in ids if a < b}
    tables = []
    for (home, visiting), info in matches.items():
        for b in boards:
            for ns in (home, visiting):
                events = c.get(f'{VG}/api/archive/watch/{sid}/{ns}/{b["boardNumber"]}')
                if events:
                    tables.append(dict(board=b['boardNumber'], ns_team=ns, home=home, visiting=visiting, events=events))
    return dict(miniSessionId=sid, meta=meta, boards=boards, teams=teams, matches=[dict(i, home=h, visiting=v) for (h, v), i in matches.items()],
                tables=tables)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('out', type=Path)
    p.add_argument('--since', default='2021-01')
    p.add_argument('--pause', type=float, default=0.25)
    p.add_argument('--limit', type=int, default=0)
    p.add_argument('--screens', help='a file of vugraph screen ids (usbc/<id>) to take besides those found')
    p.add_argument('--discover-only', action='store_true', help='find the sessions, write OUT/sessions.json and stop')
    p.add_argument('--part', default='0/1', help='K/N: this box takes the sessions whose place in the sorted list is K modulo N')
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    c = Client(a.pause)
    extra = Path(a.screens).read_text().split() if a.screens else ()
    found = sessions(c, a.since, extra)
    (a.out / 'sessions.json').write_text(json.dumps(found, indent=1))
    if a.discover_only:
        print(f'{len(found)} sessions; from USBF pages: {sum(1 for m in found.values() if m.get("from_usbf_page"))}', flush=True)
        return
    index_path = a.out / 'index.json'
    index = json.loads(index_path.read_text()) if index_path.exists() else {}
    print(f'{time.strftime("%FT%TZ", time.gmtime())} sessions found: {len(found)}', flush=True)
    done = 0
    k, nparts = (int(x) for x in a.part.split('/'))
    for i, (sid, meta) in enumerate(sorted(found.items())):
        if i % nparts != k:
            continue
        path = a.out / f'{sid}.json.gz'
        if path.exists():
            continue
        rec = harvest(c, sid, meta)
        tmp = path.with_suffix('.tmp')
        with gzip.open(tmp, 'wt') as f:
            json.dump(rec, f, separators=(',', ':'))
        os.replace(tmp, path)
        index[sid] = dict(name=meta.get('namePlus') or meta.get('name'), start=meta.get('startDateTime'), boards=len(rec['boards']),
                          tables=len(rec['tables']), from_usbf_page=meta.get('from_usbf_page'))
        index_path.write_text(json.dumps(index, indent=1))
        done += 1
        print(f'{time.strftime("%FT%TZ", time.gmtime())} {sid} {index[sid]["name"]}: {len(rec["boards"])} boards, {len(rec["tables"])} tables '
              f'({c.calls} requests so far)', flush=True)
        if a.limit and done >= a.limit:
            break
    print(f'{time.strftime("%FT%TZ", time.gmtime())} done: {len(index)} sessions, {sum(v["tables"] for v in index.values())} tables, {c.calls} requests', flush=True)


if __name__ == '__main__':
    main()
