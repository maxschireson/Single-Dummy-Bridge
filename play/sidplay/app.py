"""HTTP: the page, accounts, tables (long-polled), history and analyses.

  SIDPLAY_BUNDLE=/path/to/bundle uvicorn sidplay.app:app --app-dir play --host 127.0.0.1 --port 8090
  SIDPLAY_ENGINE=fake uvicorn sidplay.app:app --app-dir play        # no models: a stand-in bot

Every POST must carry the header `X-Sid: 1`. A cross-site form cannot set it, and no CORS is allowed, which
is the CSRF defence together with SameSite cookies.
"""
import asyncio
from collections import defaultdict, deque
import contextlib
import logging
from pathlib import Path
import re
import secrets
import sys
import time

from .config import Config

CONFIG = Config.from_env()
if CONFIG.source and CONFIG.source not in sys.path:
    sys.path.insert(0, CONFIG.source)        # bridge_harness comes from the bundle's own source checkout

from fastapi import FastAPI, HTTPException, Request, Response          # noqa: E402
from fastapi.responses import FileResponse, JSONResponse                # noqa: E402
from fastapi.staticfiles import StaticFiles                             # noqa: E402

from .pool import Bots                                                  # noqa: E402
from .store import Store                                                # noqa: E402
from .tables import Registry, TableError, Viewer                        # noqa: E402

log = logging.getLogger('sidplay')
STATIC = Path(__file__).with_name('static')
SESSION_COOKIE, ANON_COOKIE = 'sid_session', 'sid_anon'
SESSION_AGE = 60 * 60 * 24 * 60
USERNAME = re.compile(r'^[A-Za-z0-9_-]{3,20}$')


class Limiter:
    """At most `n` events per `seconds` for each key (in memory; resets on restart)."""
    def __init__(self, n, seconds):
        self.n, self.seconds, self.events = n, seconds, defaultdict(deque)

    def allow(self, key):
        now, q = time.time(), self.events[key]
        while q and now - q[0] > self.seconds:
            q.popleft()
        if len(q) >= self.n:
            return False
        q.append(now)
        return True


STATE = {}


@contextlib.asynccontextmanager
async def lifespan(app):
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
    CONFIG.data.mkdir(parents=True, exist_ok=True)
    store = Store(CONFIG.data / 'sidplay.sqlite')
    bots = Bots(CONFIG)
    registry = Registry(CONFIG, store, bots)
    STATE.update(store=store, bots=bots, registry=registry, started=time.time(),
                 signup=Limiter(5, 3600), login=Limiter(20, 900), create=Limiter(60, 3600), suggest=Limiter(60, 3600))
    log.info('Starting %s workers for %s', CONFIG.interactive_workers + CONFIG.background_workers, CONFIG.bot_label)
    STATE['workers'] = await bots.warm()
    log.info('Workers ready: %s', STATE['workers'])

    async def reaper():
        while True:
            await asyncio.sleep(60)
            try:
                registry.reap()
            except Exception:
                log.exception('reaper')
    task = asyncio.create_task(reaper())
    yield
    task.cancel()
    bots.close()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


def client_ip(request):
    ip = request.client.host if request.client else 'unknown'
    if ip == CONFIG.trusted_proxy and request.headers.get('x-forwarded-for'):
        ip = request.headers['x-forwarded-for'].split(',')[-1].strip()
    return ip


def viewer(request):
    store = STATE['store']
    user_id = store.session_user(request.cookies.get(SESSION_COOKIE), SESSION_AGE)
    anon = request.cookies.get(ANON_COOKIE)
    name = store.username(user_id) if user_id else None
    return Viewer(user_id, anon if anon and re.fullmatch(r'[A-Za-z0-9_-]{20,64}', anon) else None, name)


def set_cookie(response, name, value, age):
    response.set_cookie(name, value, max_age=age, httponly=True, samesite='lax', secure=CONFIG.secure_cookies, path='/')


def ensure_anon(request, response, v):
    """Every browser gets an anonymous id, so a guest's boards can follow it into an account."""
    if v.anon is None:
        v.anon = secrets.token_urlsafe(24)
        set_cookie(response, ANON_COOKIE, v.anon, SESSION_AGE)
    return v


@app.middleware('http')
async def guard(request: Request, call_next):
    if request.method == 'POST' and request.headers.get('x-sid') != '1':
        return JSONResponse({'error': 'Missing request header.'}, status_code=400)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.exception_handler(TableError)
async def table_error(request, exc):
    return JSONResponse({'error': str(exc)}, status_code=409)


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse({'error': exc.detail}, status_code=exc.status_code)


async def body(request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, 'Expected JSON.')
    if not isinstance(data, dict):
        raise HTTPException(400, 'Expected a JSON object.')
    return data


# ---- page ----------------------------------------------------------------------------------
@app.get('/')
async def index():
    return FileResponse(STATIC / 'index.html', headers={'Cache-Control': 'no-cache'})


app.mount('/static', StaticFiles(directory=STATIC), name='static')


@app.get('/api/health')
async def health():
    bots, reg = STATE['bots'], STATE['registry']
    return dict(ok=True, bot=CONFIG.bot, label=CONFIG.bot_label, stand_in=CONFIG.bot_stand_in, engine=CONFIG.engine, open_tables=reg.open_count(),
                busy=bots.busy, decisions=bots.decisions, analysis=CONFIG.analysis, uptime=int(time.time() - STATE['started']))


# ---- accounts ------------------------------------------------------------------------------
@app.get('/api/me')
async def me(request: Request, response: Response):
    v = ensure_anon(request, response, viewer(request))
    t = STATE['registry'].current(v)
    return dict(user=v.name, table=t.id if t else None,
                bot=dict(label=CONFIG.bot_label, system=CONFIG.bot_system, stand_in=CONFIG.bot_stand_in,
                         description=CONFIG.bot_description),
                sid_tables=CONFIG.sid_tables, analysis=CONFIG.analysis)


def start_session(response, request, user_id, old):
    store = STATE['store']
    set_cookie(response, SESSION_COOKIE, store.new_session(user_id), SESSION_AGE)
    store.adopt_anonymous(old.anon, user_id)
    STATE['registry'].adopt(old, Viewer(user_id, None, store.username(user_id)))


WORDS = ('finesse', 'squeeze', 'endplay', 'ruff', 'trump', 'slam', 'grand', 'double', 'redouble', 'overtrick', 'duck',
         'coup', 'tenace', 'singleton', 'void', 'dummy', 'lead', 'cuebid', 'sacrifice', 'safety', 'crossruff', 'stopper')


def suggest_name(store):
    rng = secrets.SystemRandom()
    for _ in range(50):
        name = f'{rng.choice(WORDS)}-{rng.randrange(100, 1000)}'
        if store.username_free(name):
            return name
    return f'player-{secrets.token_hex(4)}'


@app.get('/api/signup/suggest')
async def signup_suggest(request: Request):
    """A free username and a fresh password, which the sign-up form shows and the person may change."""
    if not STATE['suggest'].allow(client_ip(request)):
        raise HTTPException(429, 'Too many requests. Try later.')
    alphabet = 'abcdefghijkmnpqrstuvwxyz23456789'
    password = '-'.join(''.join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3))
    return dict(username=suggest_name(STATE['store']), password=password)


@app.post('/api/signup')
async def signup(request: Request, response: Response):
    data = await body(request)
    username, password = str(data.get('username', '')).strip(), str(data.get('password', ''))
    if not USERNAME.fullmatch(username):
        raise HTTPException(400, 'Usernames are 3 to 20 letters, digits, - or _.')
    if not 8 <= len(password) <= 200:
        raise HTTPException(400, 'Use a password of at least 8 characters.')
    if not STATE['signup'].allow(client_ip(request)):
        raise HTTPException(429, 'Too many new accounts from here. Try later.')
    user_id = STATE['store'].create_user(username, password)
    if user_id is None:
        raise HTTPException(409, 'That username is taken.')
    start_session(response, request, user_id, viewer(request))
    return dict(user=username)


@app.post('/api/login')
async def login(request: Request, response: Response):
    data = await body(request)
    username, password = str(data.get('username', '')).strip(), str(data.get('password', ''))
    if not STATE['login'].allow(client_ip(request)) or not STATE['login'].allow('user:' + username.lower()):
        raise HTTPException(429, 'Too many attempts. Wait a few minutes.')
    user_id = STATE['store'].authenticate(username, password)
    if user_id is None:
        raise HTTPException(401, 'Wrong username or password.')
    start_session(response, request, user_id, viewer(request))
    return dict(user=STATE['store'].username(user_id))


@app.post('/api/logout')
async def logout(request: Request, response: Response):
    STATE['store'].end_session(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path='/')
    return dict(ok=True)


# ---- tables --------------------------------------------------------------------------------
@app.post('/api/tables')
async def create_table(request: Request, response: Response):
    data = await body(request)
    v = ensure_anon(request, response, viewer(request))
    if not STATE['create'].allow(client_ip(request)):
        raise HTTPException(429, 'Too many new tables from here. Try later.')
    reg = STATE['registry']
    replay = None
    if data.get('replay') is not None:
        if not isinstance(data['replay'], int) or isinstance(data['replay'], bool):
            raise HTTPException(400, 'Which board?')
        replay = STATE['store'].replay_source(data['replay'], v.user_id, v.anon)
        if replay is None:
            raise HTTPException(404, 'No such board in your history.')
    t = reg.create_solo(v, replay=replay)
    return dict(table=t.id)


@app.get('/api/tables/{table_id}')
async def table_state(table_id: str, request: Request, since: int = -1):
    v = viewer(request)
    t = STATE['registry'].get(table_id)
    t.view(v)                                   # refuses a viewer who is not seated before waiting
    if since >= 0:
        await t.wait(since, 25)
    return t.view(v)


@app.post('/api/tables/{table_id}/call')
async def call(table_id: str, request: Request):
    data = await body(request)
    t = STATE['registry'].get(table_id)
    await t.human_call(viewer(request), data.get('call', ''))
    return dict(ok=True)


@app.post('/api/tables/{table_id}/card')
async def card(table_id: str, request: Request):
    data = await body(request)
    t = STATE['registry'].get(table_id)
    await t.human_card(viewer(request), data.get('card', ''))
    return dict(ok=True)


@app.post('/api/tables/{table_id}/claim')
async def claim(table_id: str, request: Request):
    data = await body(request)
    t = STATE['registry'].get(table_id)
    tricks = data.get('tricks')
    await t.human_claim(viewer(request), tricks if isinstance(tricks, int) and not isinstance(tricks, bool) else -1)
    return dict(ok=True)


@app.post('/api/tables/{table_id}/next')
async def next_board(table_id: str, request: Request):
    await STATE['registry'].get(table_id).next_board(viewer(request))
    return dict(ok=True)


@app.post('/api/tables/{table_id}/leave')
async def leave(table_id: str, request: Request):
    STATE['registry'].leave(viewer(request), table_id)
    return dict(ok=True)


# ---- history -------------------------------------------------------------------------------
@app.get('/api/history')
async def history(request: Request, offset: int = 0):
    v = viewer(request)
    if v.user_id is None and v.anon is None:
        return dict(boards=[], totals=dict(boards=0, imps=0, compared=0), user=None)
    rows, totals = STATE['store'].history(v.user_id, v.anon, 50, max(0, offset))
    return dict(boards=rows, totals=totals, user=v.name)


@app.get('/api/boards/{board_id}')
async def board(board_id: int, request: Request):
    v = viewer(request)
    store = STATE['store']
    b = store.board(board_id, v.user_id, v.anon)
    if b is None:
        raise HTTPException(404, 'No such board in your history.')
    for s in b['seats']:
        s.pop('user_id', None)
    b['older'], b['newer'] = store.neighbours(board_id, v.user_id, v.anon)
    status = STATE['registry'].analysis_status(b)
    b['analysis_status'], b['sid_analysis_status'] = status['analysis'], status['sid_analysis']
    return b
