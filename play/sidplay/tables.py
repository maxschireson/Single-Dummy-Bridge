"""Live tables: seating, the auction and the play, Sid's turns, claims, the analyses, and what each viewer may see.

Seats are N=0, E=1, S=2, W=3. One person sits South; Sid takes North (the partner) and East-West. When North-South
win the contract the person declares and plays both hands, even when Sid-North won the auction (as robot tables on
BBO do).

After each board two analyses run in the analysis pool: the person's play, and Sid's own table on the same deal (Sid at
all four seats), whose South is "Sid in your seat".

Personas (sidplay/personas.py): each board the three Sids get personalities, North its own and East-West a partnership.
The person sees North's as its partner knows it and East-West's as their partner describes them; the actual ones after
the board. Sid's own table plays the same North, East and West, and a plain Sid in South. A board can be played again from the person's history: the same
deal, dealer and vulnerability at a new table; Sid's table and its analysis are reused from the first time.

Hidden information: `view` sends a viewer only the hands that viewer may see. A bot gets only the Observation
the game gives the seat controlling the card. The full deal leaves this module only to the claim referee, to Sid's
own table and to the analyses, and to viewers once the board is over.
"""
import asyncio
from dataclasses import dataclass
import logging
import random
import secrets
import time

from . import personas as P
from .rules import (SEATS, Board, Contract, Game, auction_state, board_meta, contract_text, imps, legal_calls, new_deal,
                    parse_call, result_text, score, symbol, vulnerable, winner, card as parse_card)

HUMAN_NAMES = {0: 'Sid (North)', 1: 'Sid (East)', 2: 'You', 3: 'Sid (West)'}
SID_NAMES = {0: 'Sid North', 1: 'Sid East', 2: 'Sid South', 3: 'Sid West'}

log = logging.getLogger('sidplay.tables')
HUMAN, BOT = 'human', 'bot'


@dataclass
class Seat:
    kind: str
    user_id: int | None = None
    anon: str | None = None
    name: str = 'Sid'

    def matches(self, viewer):
        if self.kind != HUMAN:
            return False
        if self.user_id is not None:
            return viewer.user_id == self.user_id
        return viewer.user_id is None and viewer.anon is not None and viewer.anon == self.anon


@dataclass
class Viewer:
    user_id: int | None
    anon: str | None
    name: str | None = None

    @property
    def key(self):
        return f'u:{self.user_id}' if self.user_id is not None else f'a:{self.anon}'


class TableError(Exception):
    """A request the table refuses; the message is shown to the player."""


class BoardState:
    def __init__(self, number, hands, replay=None):
        self.number = number
        self.replay = replay         # a deal played again: dict(id, sid_table, sid_analysis) of the first time
        self.dealer, self.vul = board_meta(number)
        self.hands = hands
        self.calls = []
        self.contract = None
        self.game = None
        self.phase = 'auction'
        self.started = time.time()
        self.claim = None            # the last claim: dict(seat, tricks, accepted)
        self.claimed = None          # tricks claimed, if the board ended on a claim
        self.result = None
        self.db_id = None
        self.sid = None              # Sid's own table: None, 'pending', a record, or 'error'
        self.analysis = None         # None, 'pending', 'ready' or 'error'; the analysis itself is in the store
        self.sid_analysis = None
        self.brief = None            # a few lines of the person's analysis for the result panel
        self.sid_brief = None
        self.error = None
        self.personas = None         # {seat: persona} for the Sids this board (sidplay/personas.py), or None


class Table:
    def __init__(self, registry, seats, replay=None):
        self.registry = registry
        self.id = secrets.token_urlsafe(9)
        self.mode = 'solo'
        self.seats = seats
        self.status = 'playing'
        self.replay = replay         # the first board of this table is this deal again
        self.board = None
        self.number = 0
        self.scores = []
        self.version = 0
        self.changed = asyncio.Event()
        self.lock = asyncio.Lock()
        self.thinking = None
        self.created = self.last_action = time.time()
        self.rng = random.Random(secrets.randbits(64))
        self.tasks = set()

    # ---- bookkeeping ---------------------------------------------------------------------
    @property
    def config(self):
        return self.registry.config

    def bump(self):
        self.version += 1
        event, self.changed = self.changed, asyncio.Event()
        event.set()

    async def wait(self, since, timeout):
        if self.version != since:
            return
        event = self.changed
        try:
            await asyncio.wait_for(event.wait(), timeout)
        except asyncio.TimeoutError:
            pass

    def spawn(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    def humans(self):
        return [(i, s) for i, s in enumerate(self.seats) if s is not None and s.kind == HUMAN]

    def seat_of(self, viewer):
        for i, s in self.humans():
            if s.matches(viewer):
                return i
        return None

    def systems(self):
        """Declared systems (NS, EW). The person bids Sid's system with Sid."""
        own = self.config.bot_system
        return (own, own)

    def bot_kind(self, seat):
        """Which of the worker's two Sid instances plays this seat: the one facing humans, or the one facing Sid."""
        opponents = (self.seats[(seat + 1) % 4], self.seats[(seat + 3) % 4])
        return 'human' if any(s is not None and s.kind == HUMAN for s in opponents) else 'sid'

    # ---- whose turn ----------------------------------------------------------------------
    def declaring_controller(self):
        """The seat whose owner plays declarer's and dummy's cards."""
        c = self.board.contract
        return 2 if c.declarer % 2 == 0 else c.declarer

    def card_owner(self, actor):
        c = self.board.contract
        seat = self.declaring_controller() if actor % 2 == c.declarer % 2 else actor
        return seat, self.seats[seat]

    def turn(self):
        """(kind 'call' | 'card', acting seat, controlling seat, its Seat) or None."""
        b = self.board
        if b is None or b.phase == 'done' or b.error or self.status != 'playing':
            return None
        if b.phase == 'auction':
            seat = (b.dealer + len(b.calls)) % 4
            return 'call', seat, seat, self.seats[seat]
        actor = b.game.actor
        controller, owner = self.card_owner(actor)
        return 'card', actor, controller, owner

    # ---- the board -----------------------------------------------------------------------
    def start_board(self):
        if self.replay is not None:
            r, self.replay = self.replay, None
            self.number = r['number']
            self.board = BoardState(r['number'], r['hands'], replay=r)
            self.board.personas = P.from_json(r.get('personas'))      # the same Sids as the first time
        else:
            self.number += 1
            self.board = BoardState(self.number, new_deal())
            if self.config.personas:
                self.board.personas = P.draw(random.Random(self.rng.getrandbits(64)))
        self.bump()
        self.kick()

    def apply_call(self, call):
        b = self.board
        b.calls.append(call)
        state = auction_state(b.dealer, b.calls)
        if state == 'open':
            return
        b.contract = state
        if state is None:
            self.finish_board()
            return
        b.game = Game(Board(f'{self.id}-{b.number}', b.hands, state, b.dealer, b.vul, tuple(b.calls), auction_source='sidplay'))
        b.phase = 'play'

    def apply_card(self, c):
        b = self.board
        b.game.play(c)
        if b.game.done:
            self.finish_board()

    def finish_board(self):
        b = self.board
        b.phase = 'done'
        c = b.contract
        if c is None:
            tricks, ns = None, 0
        else:
            tricks = b.game.declarer_tricks if b.claimed is None else b.game.declarer_tricks + b.claimed
            ns = score(c, tricks, vulnerable(b.vul, c.declarer)) * (1 if c.declarer % 2 == 0 else -1)
        b.result = dict(contract=contract_text(c), declarer=SEATS[c.declarer] if c else None, tricks=tricks,
                        result=result_text(c, tricks) if c else 'Passed out', ns_score=ns, claimed=b.claimed)
        record = dict(table_id=self.id, mode=self.mode, number=b.number, started=b.started, finished=time.time(),
                      dealer=SEATS[b.dealer], vulnerability=b.vul, hands=[[symbol(x) for x in h] for h in b.hands],
                      calls=list(b.calls), contract=c.text() if c else None, declarer=SEATS[c.declarer] if c else None,
                      tricks=tricks, claimed=b.claimed, ns_score=ns,
                      play=[[SEATS[s], symbol(x)] for s, x in b.game.history] if b.game else [],
                      seats=[dict(kind=s.kind, name=s.name, user_id=s.user_id) for s in self.seats],
                      bot=self.config.bot, bot_identity=self.config.bot_identity,
                      replay_of=b.replay['id'] if b.replay else None, personas=P.to_json(b.personas))
        try:
            b.db_id = self.registry.store.save_board(record, [(SEATS[i], s.user_id, s.anon) for i, s in self.humans()])
        except Exception:
            log.exception('Could not save board %s-%s', self.id, b.number)
        self.scores.append(dict(number=b.number, **b.result, sid=None, imps=None, board_id=b.db_id, replay=bool(b.replay)))
        if self.config.analysis and c is not None and b.game.history:
            b.analysis = 'pending'
            self.spawn(self.analyse(b, 'analysis', b.hands, c.text(), c.declarer, list(b.game.history), HUMAN_NAMES,
                                    dict(calls=list(b.calls), dealer=b.dealer, vul=b.vul)))
        if b.replay and b.replay.get('sid_table'):
            self.spawn(self.sid_table_done(b, self.scores[-1], b.replay['sid_table'], b.replay.get('sid_analysis')))
        elif self.config.sid_tables:
            b.sid = 'pending'
            self.spawn(self.play_sid_table(b, self.scores[-1]))

    async def analyse(self, b, which, hands, contract, declarer, play, names, auction=None):
        """Run one analysis in the analysis pool (stored by the registry). which: 'analysis' or 'sid_analysis'."""
        result = await self.registry.run_analysis(b.db_id, which, hands, contract, declarer, play, names, auction)
        if result is None:
            setattr(b, which, 'error')
            self.bump()
            return
        self.set_analysis(b, which, result, store=False)

    def set_analysis(self, b, which, result, store=True):
        setattr(b, which, 'ready')
        setattr(b, 'brief' if which == 'analysis' else 'sid_brief', brief(result))
        if store and b.db_id is not None:
            try:
                self.registry.store.set_analysis(b.db_id, which, result)
            except Exception:
                log.exception('Could not save %s for board %s', which, b.db_id)
        self.bump()

    async def play_sid_table(self, b, row):
        try:
            sid = await self.registry.bots.sid_table(b.hands, b.dealer, b.vul, f'{self.id}-{b.number}-sid',
                                                     self.rng.getrandbits(64), (self.config.bot_system, self.config.bot_system),
                                                     b.personas)
        except Exception:
            log.exception('Sid table failed on %s-%s', self.id, b.number)
            b.sid = 'error'
            self.bump()
            return
        await self.sid_table_done(b, row, sid, None)

    async def sid_table_done(self, b, row, sid, analysis):
        """Sid's own table on this deal is known (played now, or reused for a deal played again)."""
        b.sid = sid
        sid_view = dict(contract=sid['contract'], declarer=sid['declarer'], tricks=sid['tricks'], ns_score=sid['ns_score'],
                        calls=sid['calls'])
        if sid['contract']:
            sid_view['result'] = result_text(Contract.parse(sid['contract'], SEATS.index(sid['declarer'])), sid['tricks'])
            sid_view['contract'] = contract_text(Contract.parse(sid['contract'], SEATS.index(sid['declarer'])))
        row['sid'] = sid_view
        row['imps'] = imps(row['ns_score'] - sid['ns_score'])
        if b.db_id is not None:
            try:
                self.registry.store.set_sid_table(b.db_id, sid, sid['ns_score'], row['imps'])
            except Exception:
                log.exception('Could not save Sid table for board %s', b.db_id)
        self.bump()
        if analysis:
            self.set_analysis(b, 'sid_analysis', analysis)
        elif self.config.analysis and sid['contract'] and sid['play']:
            b.sid_analysis = 'pending'
            self.bump()
            play = [(SEATS.index(seat), parse_card(c)) for seat, c in sid['play']]
            await self.analyse(b, 'sid_analysis', b.hands, sid['contract'], SEATS.index(sid['declarer']), play, SID_NAMES,
                               dict(calls=list(sid['calls']), dealer=b.dealer, vul=b.vul))

    # ---- Sid's turns ---------------------------------------------------------------------
    def kick(self):
        self.spawn(self.drive())

    async def drive(self):
        async with self.lock:
            while True:
                t = self.turn()
                if t is None or t[3].kind == HUMAN:
                    return
                kind, actor, controller, _ = t
                b = self.board
                pause = self.config.pace
                if kind == 'card' and not b.game.trick and b.game.history:
                    pause = self.config.trick_pause
                seed = self.rng.getrandbits(64)
                if kind == 'call':
                    job = self.registry.bots.bid(b.hands[actor], actor, b.dealer, b.vul, list(b.calls),
                                                 P.bid_style(b.personas, actor))
                else:
                    job = self.registry.bots.play(b.game.observation(), self.bot_kind(controller), self.systems(), seed,
                                                  P.play_style(b.personas, controller))
                job = asyncio.ensure_future(job)
                self.thinking = SEATS[actor]
                self.bump()
                try:
                    await asyncio.sleep(pause)
                    result, _ = await job
                except Exception:
                    log.exception('Bot failed at table %s board %s', self.id, b.number)
                    b.error = 'Sid hit an error on this board. Start the next board.'
                    self.thinking = None
                    self.bump()
                    return
                if self.board is not b or self.status != 'playing':
                    return
                self.thinking = None
                if kind == 'call':
                    self.apply_call(result)
                else:
                    self.apply_card(result)
                self.bump()

    # ---- human actions -------------------------------------------------------------------
    def _my_turn(self, viewer, kind):
        t = self.turn()
        if t is None or t[0] != kind or not t[3].matches(viewer):
            raise TableError('It is not your turn.')
        return t

    async def human_call(self, viewer, text):
        async with self.lock:
            _, seat, _, _ = self._my_turn(viewer, 'call')
            call = parse_call(text)
            if call not in legal_calls(self.board.dealer, self.board.calls):
                raise TableError('That call is not legal here.')
            self.apply_call(call)
            self.last_action = time.time()
            self.bump()
        self.kick()

    async def human_card(self, viewer, text):
        async with self.lock:
            self._my_turn(viewer, 'card')
            try:
                c = parse_card(str(text))
            except ValueError:
                raise TableError('Unknown card.') from None
            if c not in self.board.game.observation().legal:
                raise TableError('You cannot play that card.')
            self.apply_card(c)
            self.last_action = time.time()
            self.bump()
        self.kick()

    async def human_claim(self, viewer, tricks):
        async with self.lock:
            b = self.board
            if b is None or b.phase != 'play' or self.status != 'playing':
                raise TableError('You can claim only during the play.')
            controller = self.declaring_controller()
            if not self.seats[controller].matches(viewer):
                raise TableError('Only declarer can claim.')
            g = b.game
            remaining = 13 - len(g.history) // 4
            if not isinstance(tricks, int) or not 0 <= tricks <= remaining:
                raise TableError(f'Claim between 0 and {remaining} tricks.')
            side = b.contract.declarer % 2
            available = await self.registry.bots.side_tricks([tuple(sorted(h)) for h in g.hands], b.contract.trump,
                                                             g.leader, list(g.trick), side)
            accepted = tricks <= available
            # A refusal never says how many tricks were available: that would reveal the hidden hands.
            b.claim = dict(seat=SEATS[controller], tricks=tricks, accepted=accepted)
            self.last_action = time.time()
            if accepted:
                b.claimed = tricks
                self.finish_board()
            self.bump()
        self.kick()

    async def next_board(self, viewer):
        async with self.lock:
            if self.seat_of(viewer) is None:
                raise TableError('You are not at this table.')
            if self.status != 'playing':
                raise TableError('This table has closed.')
            if self.board is not None and self.board.phase != 'done' and not self.board.error:
                raise TableError('Finish this board first.')
            self.last_action = time.time()
            self.start_board()

    def close(self, reason='closed'):
        if self.status == 'closed':
            return
        self.status = 'closed'
        self.closed_reason = reason
        self.bump()

    # ---- what a viewer sees --------------------------------------------------------------
    def visible_seats(self, me):
        b = self.board
        if b is None:
            return set()
        if b.phase == 'done':
            return {0, 1, 2, 3}
        seen = {me}
        if b.phase == 'play' and b.game.history:
            seen.add(b.contract.dummy)
            if self.declaring_controller() == me:
                seen.add(b.contract.declarer)
        return seen

    def view(self, viewer):
        me = self.seat_of(viewer)
        if me is None:
            raise TableError('You are not at this table.')
        counted = [r for r in self.scores if not r.get('replay')]
        out = dict(id=self.id, mode=self.mode, status=self.status, version=self.version, me=SEATS[me],
                   seats=[dict(seat=SEATS[i], kind=s.kind, name=s.name) for i, s in enumerate(self.seats)],
                   bot=dict(label=self.config.bot_label, system=self.config.bot_system, stand_in=self.config.bot_stand_in,
                            variable=self.config.variable_id), scores=self.scores,
                   totals=dict(boards=len(counted), imps=sum(r['imps'] or 0 for r in counted),
                               compared=sum(r['imps'] is not None for r in counted), replays=len(self.scores) - len(counted)),
                   closed_reason=getattr(self, 'closed_reason', None))
        b = self.board
        if b is None:
            out['board'] = None
            return out
        seen = self.visible_seats(me)
        g = b.game
        hands = {}
        for s in range(4):
            if b.phase == 'done':
                cards = b.hands[s]
            elif g is not None:
                cards = tuple(sorted(g.hands[s]))
            else:
                cards = b.hands[s]
            hands[SEATS[s]] = dict(cards=[symbol(x) for x in sorted(cards, reverse=True)] if s in seen else None,
                                   count=len(cards))
        t = self.turn()
        turn = None
        legal = []
        if t is not None:
            kind, actor, controller, owner = t
            mine = owner.matches(viewer)
            turn = dict(kind=kind, seat=SEATS[actor], mine=mine)
            if mine:
                legal = legal_calls(b.dealer, b.calls) if kind == 'call' else [symbol(x) for x in g.observation().legal]
        board = dict(number=b.number, dealer=SEATS[b.dealer], vul=b.vul, phase=b.phase, calls=list(b.calls), hands=hands,
                     replay=bool(b.replay),
                     contract=contract_text(b.contract) if b.contract else None,
                     declarer=SEATS[b.contract.declarer] if b.contract else None,
                     dummy=SEATS[b.contract.dummy] if b.contract else None,
                     turn=turn, legal=legal, thinking=self.thinking, claim=b.claim, error=b.error,
                     personas=dict(told=P.told(b.personas), actual=P.full(b.personas) if b.phase == 'done' else None)
                     if b.personas else None,
                     can_claim=bool(b.phase == 'play' and self.seats[self.declaring_controller()].matches(viewer)))
        if g is not None:
            board.update(trick=[[SEATS[s], symbol(x)] for s, x in g.trick], leader=SEATS[g.leader],
                         tricks=dict(declarer=g.declarer_tricks, defence=len(g.history) // 4 - g.declarer_tricks),
                         remaining=13 - len(g.history) // 4, played=len(g.history))
            done = len(g.history) // 4
            if done and not g.trick:
                last = g.history[4 * (done - 1):4 * done]
                board['last_trick'] = dict(cards=[[SEATS[s], symbol(x)] for s, x in last],
                                           winner=SEATS[winner(last, b.contract.trump)])
        if b.phase == 'done':
            board['result'] = b.result
            board['play'] = [[SEATS[s], symbol(x)] for s, x in g.history] if g else []
            board['sid'] = 'pending' if b.sid == 'pending' else 'error' if b.sid == 'error' else (
                self.scores[-1]['sid'] if b.sid else None)
            board['imps'] = self.scores[-1]['imps'] if self.scores else None
            board['board_id'] = b.db_id
            board['analysis'] = dict(status=b.analysis, brief=b.brief)
            board['sid_analysis'] = dict(status=b.sid_analysis, brief=b.sid_brief)
        out['board'] = board
        return out


def brief(a):
    """A few lines of an analysis for the result panel: the trick count and the main events."""
    if not a:
        return None
    sm = a.get('summary') or {}
    order = {'gave_away': 0, 'handed_contract': 0, 'had_guarantee': 1, 'sure_trick': 2, 'handed_trick': 2, 'regained': 3}
    events = a.get('events', [])
    top = sorted(sorted(events, key=lambda e: (order.get(e['kind'], 9), e['n']))[:3], key=lambda e: e['n'])
    return dict(lost=sm.get('lost'), partner_lost=sm.get('partner_lost'), gifts=sm.get('gifts'),
                side_start=sm.get('side_start'), side_end=sm.get('side_end'), declaring=a.get('focus_declares'),
                events=[e['text'] for e in top], more=max(0, len(events) - 3))


class Registry:
    def __init__(self, config, store, bots):
        self.config, self.store, self.bots = config, store, bots
        self.tables = {}
        self.owner = {}           # viewer key -> table id (one open table each)
        self.analysing = set()    # (board id, which) running now
        self.failed = {}          # (board id, which) -> when it last failed
        self.tasks = set()

    # ---- analyses -------------------------------------------------------------------------
    async def run_analysis(self, board_id, which, hands, contract, declarer, play, names, auction=None):
        """One analysis in the analysis pool; stored when the board is saved. None if it failed."""
        key = (board_id, which)
        self.analysing.add(key)
        try:
            # Sid's table gets the sure-trick search from 10 cards only; the contract question at 11 to 13 cards is for
            # the person's play (Max, 14 Nov).
            limits = None if which == 'analysis' else dict(sure_need_cards=self.config.analysis_limits.get('sure_cards', 10))
            result = await self.bots.analyse([list(h) for h in hands], contract, declarer, [list(p) for p in play], [2], names,
                                             limits, auction)
        except Exception:
            log.exception('Analysis %s of board %s failed', which, board_id)
            self.failed[key] = time.time()
            return None
        finally:
            self.analysing.discard(key)
        if board_id is not None:
            try:
                self.store.set_analysis(board_id, which, result)
            except Exception:
                log.exception('Could not save %s for board %s', which, board_id)
        return result

    def analysis_status(self, d):
        """For a stored board (Store.board): the state of both analyses, starting any that is missing (a board from
        before analyses existed, or one whose analysis a restart cut off)."""
        out = {}
        jobs = {'analysis': (d['contract'], d['declarer'], d['play'], HUMAN_NAMES, d['calls'])}
        sid = d.get('sid_table') or {}
        jobs['sid_analysis'] = (sid.get('contract'), sid.get('declarer'), sid.get('play'), SID_NAMES, sid.get('calls'))
        for which, (contract, declarer, play, names, calls) in jobs.items():
            key = (d['id'], which)
            if d.get(which):
                out[which] = 'ready'
            elif not self.config.analysis or not contract or not play:
                out[which] = None
            elif key in self.analysing or any(t.board and t.board.db_id == d['id'] and getattr(t.board, which) == 'pending'
                                              for t in self.tables.values()):
                out[which] = 'pending'
            elif time.time() - self.failed.get(key, 0) < 600:
                out[which] = 'error'
            else:
                hands = [[parse_card(c) for c in h] for h in d['hands']]
                moves = [(SEATS.index(seat), parse_card(c)) for seat, c in play]
                self.analysing.add(key)            # before the task starts, so a second request does not start another
                auction = dict(calls=list(calls or []), dealer=SEATS.index(d['dealer']), vul=d['vulnerability'])
                task = asyncio.ensure_future(self.run_analysis(d['id'], which, hands, contract, SEATS.index(declarer), moves, names,
                                                               auction))
                self.tasks.add(task)
                task.add_done_callback(self.tasks.discard)
                out[which] = 'pending'
        return out

    def open_count(self):
        return sum(t.status != 'closed' for t in self.tables.values())

    def get(self, table_id):
        t = self.tables.get(table_id)
        if t is None:
            raise TableError('That table has closed.')
        return t

    def current(self, viewer):
        tid = self.owner.get(viewer.key)
        t = self.tables.get(tid) if tid else None
        return t if t is not None and t.status != 'closed' else None

    def _release(self, viewer):
        old = self.current(viewer)
        if old is not None:
            self.close(old, 'left')

    def _capacity(self):
        if self.open_count() >= self.config.max_tables:
            raise TableError('All of Sid\'s tables are busy. Try again in a few minutes.')

    def human_seat(self, viewer):
        return Seat(HUMAN, viewer.user_id, viewer.anon if viewer.user_id is None else None, viewer.name or 'Guest')

    def create_solo(self, viewer, replay=None):
        """A new table: the person South, Sid at the other seats. replay: a deal from the person's history to play
        again first (dict from Store.replay_source)."""
        if replay is not None:
            replay = dict(replay, hands=tuple(tuple(sorted(parse_card(c) for c in h)) for h in replay['hands']))
        self._release(viewer)
        self._capacity()
        seats = [Seat(BOT), Seat(BOT), self.human_seat(viewer), Seat(BOT)]
        t = Table(self, seats, replay=replay)
        self.tables[t.id] = t
        self.owner[viewer.key] = t.id
        t.start_board()
        return t

    def adopt(self, old, new):
        """A guest signed in: their open table (if any) is now the account's."""
        t = self.current(old)
        if t is None:
            return
        if self.current(new) is not None:
            self._release(new)          # the account's own open table, from another browser
        for i, s in t.humans():
            if s.matches(old):
                t.seats[i] = self.human_seat(new)
        self.owner.pop(old.key, None)
        self.owner[new.key] = t.id
        t.bump()

    def close(self, t, reason):
        t.close(reason)
        for k in [k for k, v in self.owner.items() if v == t.id]:
            del self.owner[k]

    def leave(self, viewer, table_id):
        t = self.get(table_id)
        if t.seat_of(viewer) is None:
            raise TableError('You are not at this table.')
        self.close(t, 'left')

    def reap(self, now=None):
        """Close idle tables; forget closed ones after a while (their viewers have been told)."""
        now = now or time.time()
        for t in list(self.tables.values()):
            if t.status == 'playing' and now - t.last_action > 60 * self.config.idle_minutes and t.thinking is None:
                self.close(t, 'idle')
            if t.status == 'closed' and now - t.last_action > 3600 and not t.tasks:
                del self.tables[t.id]
