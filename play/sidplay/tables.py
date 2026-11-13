"""Live tables: seating, the auction and the play, Sid's turns, claims, and what each viewer may see.

Seats are N=0, E=1, S=2, W=3. Humans always sit North-South: a solo player at South with Sid at the other three
seats, or two account holders at North and South against Sid East-West. When North-South win the contract the
human side declares: in a pair the human at the declarer's seat plays both hands; solo, the human plays both
hands even when Sid-North won the auction (as robot tables on BBO do).

Hidden information: `view` sends a viewer only the hands that viewer may see. A bot gets only the Observation
the game gives the seat controlling the card. The full deal leaves this module only to the claim referee and to
Sid's own table, and to viewers once the board is over.
"""
import asyncio
from dataclasses import dataclass
import logging
import random
import secrets
import time

from .rules import (SEATS, Board, Contract, Game, auction_state, board_meta, contract_text, imps, legal_calls, new_deal,
                    parse_call, result_text, score, symbol, vulnerable, winner, card as parse_card)

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
    def __init__(self, number, hands):
        self.number = number
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
        self.error = None


class Table:
    def __init__(self, registry, mode, seats, invite=None):
        self.registry = registry
        self.id = secrets.token_urlsafe(9)
        self.mode = mode
        self.seats = seats
        self.invite = invite
        self.status = 'waiting' if any(s is None for s in seats) else 'playing'
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
        """Declared systems (NS, EW). A solo player bids Sid's system with Sid; a human pair declares nothing."""
        own = self.config.bot_system
        return (own if self.mode == 'solo' else None, own)

    def bot_kind(self, seat):
        """Which of the worker's two Sid instances plays this seat: the one facing humans, or the one facing Sid."""
        opponents = (self.seats[(seat + 1) % 4], self.seats[(seat + 3) % 4])
        return 'human' if any(s is not None and s.kind == HUMAN for s in opponents) else 'sid'

    # ---- whose turn ----------------------------------------------------------------------
    def declaring_controller(self):
        """The seat whose owner plays declarer's and dummy's cards."""
        c = self.board.contract
        if c.declarer % 2 == 0 and self.mode == 'solo':
            return 2
        return c.declarer

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
        self.number += 1
        self.board = BoardState(self.number, new_deal())
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
                      bot=self.config.bot, bot_identity=self.config.bot_identity)
        try:
            b.db_id = self.registry.store.save_board(record, [(SEATS[i], s.user_id, s.anon) for i, s in self.humans()])
        except Exception:
            log.exception('Could not save board %s-%s', self.id, b.number)
        self.scores.append(dict(number=b.number, **b.result, sid=None, imps=None, board_id=b.db_id))
        if self.config.sid_tables:
            b.sid = 'pending'
            self.spawn(self.play_sid_table(b, self.scores[-1]))

    async def play_sid_table(self, b, row):
        try:
            sid = await self.registry.bots.sid_table(b.hands, b.dealer, b.vul, f'{self.id}-{b.number}-sid',
                                                     self.rng.getrandbits(64), (self.config.bot_system, self.config.bot_system))
        except Exception:
            log.exception('Sid table failed on %s-%s', self.id, b.number)
            b.sid = 'error'
            self.bump()
            return
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
                    job = self.registry.bots.bid(b.hands[actor], actor, b.dealer, b.vul, list(b.calls))
                else:
                    job = self.registry.bots.play(b.game.observation(), self.bot_kind(controller), self.systems(), seed)
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
                raise TableError('Waiting for your partner.')
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
        out = dict(id=self.id, mode=self.mode, status=self.status, version=self.version, me=SEATS[me],
                   seats=[dict(seat=SEATS[i], kind=s.kind if s else 'empty', name=(s.name if s else 'waiting for partner'))
                          for i, s in enumerate(self.seats)],
                   invite=self.invite if self.status == 'waiting' else None,
                   bot=dict(label=self.config.bot_label, system=self.config.bot_system, stand_in=self.config.bot_stand_in), scores=self.scores,
                   totals=dict(boards=len(self.scores), imps=sum(r['imps'] or 0 for r in self.scores),
                               compared=sum(r['imps'] is not None for r in self.scores)),
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
                     contract=contract_text(b.contract) if b.contract else None,
                     declarer=SEATS[b.contract.declarer] if b.contract else None,
                     dummy=SEATS[b.contract.dummy] if b.contract else None,
                     turn=turn, legal=legal, thinking=self.thinking, claim=b.claim, error=b.error,
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
        out['board'] = board
        return out


class Registry:
    def __init__(self, config, store, bots):
        self.config, self.store, self.bots = config, store, bots
        self.tables = {}
        self.owner = {}           # viewer key -> table id (one open table each)
        self.invites = {}         # invite code -> table id

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

    def create_solo(self, viewer):
        self._release(viewer)
        self._capacity()
        seats = [Seat(BOT), Seat(BOT), self.human_seat(viewer), Seat(BOT)]
        t = Table(self, 'solo', seats)
        self.tables[t.id] = t
        self.owner[viewer.key] = t.id
        t.start_board()
        return t

    def create_pair(self, viewer):
        if viewer.user_id is None:
            raise TableError('Sign in to play with a partner.')
        self._release(viewer)
        self._capacity()
        code = secrets.token_urlsafe(8)
        seats = [None, Seat(BOT), self.human_seat(viewer), Seat(BOT)]
        t = Table(self, 'pair', seats, invite=code)
        self.tables[t.id] = t
        self.owner[viewer.key] = t.id
        self.invites[code] = t.id
        return t

    def join(self, viewer, code):
        if viewer.user_id is None:
            raise TableError('Sign in to join your partner.')
        tid = self.invites.get(code)
        t = self.tables.get(tid) if tid else None
        if t is None or t.status == 'closed':
            raise TableError('That invitation has expired.')
        if t.seat_of(viewer) is not None:
            return t
        if t.status != 'waiting':
            raise TableError('That table is full.')
        self._release(viewer)
        t.seats[0] = self.human_seat(viewer)
        t.status = 'playing'
        t.invite = None
        self.invites.pop(code, None)
        self.owner[viewer.key] = t.id
        t.last_action = time.time()
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
        for k in [k for k, v in self.invites.items() if v == t.id]:
            del self.invites[k]

    def leave(self, viewer, table_id):
        t = self.get(table_id)
        if t.seat_of(viewer) is None:
            raise TableError('You are not at this table.')
        self.close(t, 'left')

    def reap(self, now=None):
        """Close idle tables; forget closed ones after a while (their viewers have been told)."""
        now = now or time.time()
        for t in list(self.tables.values()):
            if t.status == 'waiting' and now - t.created > 60 * self.config.invite_minutes:
                self.close(t, 'expired')
            elif t.status == 'playing' and now - t.last_action > 60 * self.config.idle_minutes and t.thinking is None:
                self.close(t, 'idle')
            if t.status == 'closed' and now - t.last_action > 3600 and not t.tasks:
                del self.tables[t.id]
