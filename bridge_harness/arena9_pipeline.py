"""Experience and arrival for the Gen 9 population arena (tasks G9-D7 and G9-D6).

Gen 9 design in progress (dave). Used by scripts/arena9.py's match backend; no collector uses it.

The loop the architecture is built around (docs/gen9/architecture.md sections 3 and 5):

  arrival   a package that declares a card gets its first PlayerModel from player_model.arrive, with
            the card's distance to every system we hold (bill's cards.match.card_distance; the
            matrix of reports/gen9-profile-distance-2026-11-12 where it already has the number);
            a package that declares profiles (a house bot) gets those. The model is stored in the
            registry log with the submission.
  a board   once it is finished, every hand is known and each partnership with something declared
            gets its deltas: bidding statistics (bill's cards.factor.bidding_delta, with the
            'profile' evidence of cards.match.profile_evidence) to whoever made the calls at each
            table, card statistics (sam's signal_experience.card_delta) to whoever played the cards.
            Envelopes name the occasion so that evidence seen twice counts once. The unit is g9's (07:27, E9-5
            item 5): deal family, seats, auction; the rules file's experience.occasions can add, for card
            statistics, the opponent or the whole play (see OCCASIONS). Bid statistics are a function of the
            hands, the seats and the auction, so the same deal and auction against a floor's bot and its
            control is one occasion.
  boundary  arena9.close_epoch merges every envelope of the epochs that have closed into stores and
            freezes a snapshot (experience_store); the next epoch's manifest names it.
  the table each Gen 9 bot is handed, in its spec, every rostered player's model with that
            snapshot's statistics; the shell resolves them in meet(opponent) and auction_by(bidders)
            and moves the profile probabilities by the 'profile' statistic (player_model.believed).

Nothing about a board reaches a snapshot before the epoch in which it was played has closed: deltas
go to the epoch's results folder and only close_epoch reads them.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from . import experience as xp
from . import experience_store as xs
from .player_model import KINDS, PlayerModel, arrive

MATRIX = 'reports/gen9-profile-distance-2026-11-12/result.json'


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False)


# ---- what a package declares -----------------------------------------------------------------

def declared(package, root='.'):
    """{'card': card IR or None, 'carding': carding block or None, 'profiles': {system: p} or None, 'kind'} of a package."""
    d = package.get('declaration') or {}
    card = d.get('card')
    if isinstance(card, str):
        card = json.loads((Path(root) / card).read_text())
    return dict(card=card, carding=d.get('carding'), profiles=d.get('profiles'),
                kind=package['kind'] if package['kind'] in KINDS else 'unknown')


def declared_map(packages, root='.'):
    return {pid: declared(p, root) for pid, p in packages.items()}


# ---- arrival ------------------------------------------------------------------------------------

class Distances:
    """Distance of a card to every system we hold: the published matrix where it has the number, else computed with
    bill's card_distance on the matrix's deals (500, seed 5150), cached under `cache`."""

    def __init__(self, root='.', cache=None, systems=('house-gen5', 'house-gen6', 'house-dds40k')):
        self.root, self.cache, self.systems = Path(root), Path(cache) if cache else None, tuple(systems)
        path = self.root / MATRIX
        self.matrix = json.loads(path.read_text()) if path.exists() else dict(matrix={}, deals=500, seed=5150)

    def _net_path(self, system):
        from .systems import SystemRegistry
        g = SystemRegistry.load()[system].generator('ben-lstm-keras')
        return self.root / g['path'] if isinstance(g, dict) and 'path' in g else None

    def __call__(self, card):
        cid = card.get('id') or hashlib.sha256(canonical(card).encode()).hexdigest()[:16]
        cached = self.cache / f'{cid}.json' if self.cache else None
        if cached and cached.exists():
            return json.loads(cached.read_text())
        rates, source = {}, {}
        for system in self.systems:
            row = (self.matrix['matrix'].get(system) or {}).get(cid)
            if row is not None:
                rates[system], source[system] = float(row['rate']), MATRIX
                continue
            try:
                rates[system], source[system] = self._compute(card, system), 'computed'
            except Exception as e:                      # a system we cannot bid here is left out of the prior, and said so
                source[system] = f'left out: {type(e).__name__}: {e}'[:160]
        out = dict(card=cid, rates=rates, source=source, deals=self.matrix.get('deals'), seed=self.matrix.get('seed'))
        if cached:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(json.dumps(out, indent=1, sort_keys=True))
        return out

    def _compute(self, card, system):
        import importlib.util
        from .cards.match import card_distance
        spec = importlib.util.spec_from_file_location('gen9_profile_distance', self.root / 'scripts' / 'gen9_profile_distance.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        path = mod.NETS.get(system) or self._net_path(system)
        if path is None:
            raise ValueError(f'no BEN-format net for {system}')
        ds = mod.deal_list(self.matrix.get('deals', 500), self.matrix.get('seed', 5150))
        return float(card_distance(card, mod.net_bid_deal(str(self.root / path), ds), deals=len(ds), seed=self.matrix.get('seed', 5150))['rate'])


def arrival_model(package, root='.', distances=None):
    """The first PlayerModel of a package, as a dict for the registry log, with how it was made."""
    d = declared(package, root)
    if d['card'] is None:
        if d['profiles']:
            m = PlayerModel(package['id'], d['kind'], d['profiles'], None, d['carding'])
        else:
            m = PlayerModel(package['id'], d['kind'], carding=d['carding'])
        return dict(m.to_dict(), arrival=dict(source='declared profiles' if d['profiles'] else 'nothing declared'))
    dist = (distances or Distances(root))(d['card'])
    m = arrive(package['id'], kind=d['kind'], bidding=d['card'], carding=d['carding'], distances=dist['rates'])
    return dict(m.to_dict(), arrival=dict(source='player_model.arrive', distances=dist))


def table_models(epoch, snapshot):
    """{player id: PlayerModel dict with its experience from the snapshot} for every player of an epoch: what a Gen 9 bot
    is handed. The arrival record is left out (it is in the registry log)."""
    out = {}
    for pid, p in epoch['players'].items():
        m = {k: v for k, v in (p.get('model') or dict(id=pid, kind='unknown')).items() if k != 'arrival'}
        m['experience'] = xs.player_snapshot(snapshot, pid)
        out[pid] = m
    return out


# ---- deltas from a finished board ---------------------------------------------------------------

SIDES = ((0, (0, 2), 'NS'), (1, (1, 3), 'EW'))
_CACHE = {}


def _systems(root):
    if 'systems' not in _CACHE:
        from .cards.match import FlatProfile, held_systems
        systems = held_systems(root)
        _CACHE['systems'] = systems
        _CACHE['flat'] = FlatProfile(list(systems.values())) if systems else None
    return _CACHE['systems'], _CACHE['flat']


def reads_bidding(decl):
    """Whose calls we keep statistics on: a partnership that declared a card, or a guest or outside bot."""
    return decl is not None and (decl.get('card') is not None or decl.get('kind') in ('guest', 'outside'))


OCCASIONS = dict(bid='auction', card='auction')
OCCASION_CHOICES = dict(bid=('auction', 'opponent'), card=('auction', 'opponent', 'play'))


def occasion_rule(rules=None):
    """What makes two deltas the same occasion, from a rules file's experience.occasions; each value one of
      auction   deal family, seats, auction (g9's unit, the default)
      opponent  the same, and the opponent: the same deal against a floor's bot and its control counts twice
      play      cards only: the same, and every card played at the table; two plays of a deal that differ in any
                card count twice, an identical play once"""
    rule = dict(OCCASIONS, **(((rules or {}).get('experience') or {}).get('occasions') or {}))
    for k, v in rule.items():
        if v not in OCCASION_CHOICES.get(k, ()):
            raise ValueError(f'experience.occasions.{k}: {v!r} is not one of {OCCASION_CHOICES.get(k)}')
    return rule


def _occasion_seats(name, what, rule, opponent, actions):
    if rule == 'auction':
        return f'{name}/{what}'
    if rule == 'opponent':
        return f'{name}/{what}/{opponent}'
    play = hashlib.sha256(canonical([[a.get('seat'), a.get('card')] for a in actions]).encode()).hexdigest()[:16]
    return f'{name}/{what}/play:{play}'


def board_envelopes(record, key, models, decl, source, completed, root='.', occasions=None):
    """Experience envelopes for one finished board (all hands known): bidding statistics to whoever made the calls at each
    distinct table, card statistics to whoever played the cards, for partnerships with something declared.

    A table that two regimes share (the native auction equal to the common one) is credited, for each side, to every
    distinct bidder that the regimes using it seated there; the occasion removes the repeat."""
    from .cards.factor import CardFactor, bidding_delta, deviation_from
    from .cards.match import profile_evidence
    from .core import Board
    from .signal_experience import card_delta, replay_plays
    ids = dict(candidate=record['candidate'], opponent=record['opponent'])
    other = {record['candidate']: record['opponent'], record['opponent']: record['candidate']}
    rule = occasion_rule(dict(experience=dict(occasions=occasions))) if occasions else dict(OCCASIONS)
    bidders_of = {}
    for b in record['bidding'].values():
        bidders_of.setdefault(b['table'], []).append(b['bidders'])
    out = []
    for tkey, e in sorted(record['unique_tables'].items()):
        board = Board.from_dict(e['board'])
        auction = list(e['board'].get('auction') or [])
        hands = [list(h) for h in board.hands]
        family = record['family']
        actions = e['tables'][0]['actions']
        for side, seats, name in SIDES:
            credited = []
            for bs in bidders_of.get(tkey, []):
                if bs[seats[0]] not in credited:
                    credited.append(bs[seats[0]])
            for bidder in credited:
                d = decl.get(bidder)
                if bidder is None or not reads_bidding(d) or not auction:
                    continue
                model = PlayerModel.from_dict(models[bidder]) if bidder in models else PlayerModel(bidder)
                systems, flat = _systems(root)
                factor = CardFactor(dict(d['card']), deviation_from(model)) if d.get('card') is not None else None
                evidence = profile_evidence(hands, board.dealer, board.vulnerability, auction, seats, systems, factor=factor, flat=flat) if systems else None
                k = f'{key}/{tkey}/{name}/bid'
                delta = (bidding_delta(bidder, k, factor, hands, board.dealer, board.vulnerability, auction, seats, profile_loglik=evidence)
                         if factor is not None else xp.delta(bidder, k, {'profile': xp.loglik(**evidence)} if evidence else {}))
                if delta['stats']:
                    seat_text = _occasion_seats(name, 'bid', rule['bid'], other.get(bidder, ''), actions)
                    out.append(xs.envelope(delta, source, completed, xs.occasion(family, seat_text, auction)))
            player = ids[e['assignments'][seats[0]]]
            d = decl.get(player)
            if d and d.get('carding') is not None and e.get('schema_version') != 'v4-passed-out-v1':
                plays = replay_plays(board, actions)
                delta = card_delta(player, f'{key}/{tkey}/{name}/card', board, plays, d['carding'], side)
                if delta['stats']:
                    seat_text = _occasion_seats(name, 'card', rule['card'], other.get(player, ''), actions)
                    out.append(xs.envelope(delta, source, completed, xs.occasion(family, seat_text, auction)))
    return out


def trace(record):
    """A digest of what was played: each distinct table's auction and cards in order. A replay must give the same."""
    rows = []
    for tkey, e in sorted(record['unique_tables'].items()):
        rows.append([tkey, list(e['board'].get('auction') or []), [[a.get('seat'), a.get('card')] for a in e['tables'][0]['actions']]])
    return hashlib.sha256(canonical(rows).encode()).hexdigest()


# ---- what each epoch's bots were told ----------------------------------------------------------

def epoch_experience(control, n, reader_spec=None):
    """For epoch n: per player, what a Gen 9 bot is handed (the snapshot's boards) and what its readers make of it: profile
    probabilities after player_model.believed with the reader's settings, the honesty the signal reader learns, off-card
    rates by family, the play factor. And a check: the snapshot's statistics are the merge of exactly the envelopes of
    the epochs before n (nothing from epoch n or later)."""
    from .cards.factor import deviation_from
    from .gen9 import gen9_settings
    from .gen9_play import experience_honesty, signal_settings
    from .player_model import believed
    control = Path(control)
    m = json.loads((control / 'epochs' / f'{n:04d}.json').read_text())
    snap = xs.load_snapshot(control / 'snapshots' / f"{m['experience_snapshot']}.json.gz")
    g9, _ = gen9_settings((reader_spec or {}).get('gen9'))
    sg = signal_settings((reader_spec or {}).get('gen9'))
    files = sorted(control.glob('results/e*/experience-*.jsonl'))
    envs = [e for e in xs.read(files) if e.get('epoch') is not None and e['epoch'] < n]
    rebuilt, report = xs.merge(envs)
    out = dict(epoch=n, snapshot=m['experience_snapshot'], envelopes_before=len(envs), counted=report['counted'],
               occasion_repeats=len(report['occasion_repeats']), players={})
    for pid, md in table_models(m, snap).items():
        model = PlayerModel.from_dict(md)
        live = believed(model, g9.profile_temper, g9.profile_floor) if g9.profile_temper > 0 else model
        stats = (md.get('experience') or {}).get('stats') or {}
        same = canonical(stats) == canonical((rebuilt.get(pid) or {}).get('stats') or {})
        dev = deviation_from(model)
        applied = (rebuilt.get(pid) or {}).get('applied') or []
        deals = len({'/'.join(k.split('/')[:3]) for k in applied})     # key: epoch id/pair/deal index/table/side/kind
        row = dict(boards=md['experience']['boards'], deals=deals, snapshot_matches_envelopes=same,
                   profiles_declared=[[s_, round(p_, 4)] for s_, p_ in model.profiles],
                   profiles_read=[[s_, round(p_, 4)] for s_, p_ in live.profiles])
        if model.carding is not None:
            h = experience_honesty(model, sg.reader_eps)
            row['honesty_read'] = None if h is None else {k: round(v, 4) for k, v in h.items()}
        if dev.counts:
            row['off_card'] = {fam: [int(a), int(d)] for fam, (a, d) in sorted(dev.counts.items())}
        if 'play.info' in stats:
            from .signal_experience import phi
            row['play_factor'] = phi(stats['play.info'])
        out['players'][pid] = row
    return out
