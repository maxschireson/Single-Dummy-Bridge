"""Settings, all from the environment (the systemd unit's EnvironmentFile on a box)."""
from dataclasses import dataclass
import json
import os
from pathlib import Path


def _scorer(bundle, meta):
    """The bot's hand-fit scorer (its spec's `scorer`, inside the bundle), or SIDPLAY_SCORER; None if neither exists."""
    if os.environ.get('SIDPLAY_SCORER'):
        return os.environ['SIDPLAY_SCORER']
    rel = (meta.get('spec') or {}).get('scorer')
    if bundle is not None and rel and (bundle / rel).is_file():
        return str(bundle / rel)
    return None


def _int(name, default):
    return int(os.environ.get(name, default))


def _float(name, default):
    return float(os.environ.get(name, default))


@dataclass
class Config:
    engine: str             # 'bundle' (Sid) or 'fake' (no models)
    bundle: Path | None
    data: Path              # where the SQLite file lives
    interactive_workers: int
    background_workers: int
    background_nice: int
    max_tables: int         # open tables at once, all users together
    idle_minutes: float     # a table with no human action for this long is closed
    sid_tables: bool        # play Sid's own table on every deal for the IMP comparison
    analysis: bool          # analyse each finished board (yours and Sid's table): double dummy and sure tricks
    analysis_workers: int   # processes for the analysis (no models loaded)
    analysis_limits: dict   # overrides for sidplay.analysis.DEFAULTS
    scorer: str | None      # the bot's hand-fit scorer file: the analysis reads the auction with it
    pace: float             # seconds between bot cards, so people can follow
    trick_pause: float      # seconds a finished trick stays before a bot leads to the next
    secure_cookies: bool
    trusted_proxy: str      # address whose X-Forwarded-For is believed
    bot: str                # the bot key in the bundle, for display and records
    bot_label: str
    bot_identity: str | None
    bot_system: str | None
    bot_stand_in: bool      # the installed bot is standing in until Sid itself exists
    bot_description: str | None
    source: str | None      # path of the source checkout providing bridge_harness
    personas: bool          # each board the Sids get personas (sidplay/personas.py), where the source has them
    variable_id: str | None # the identifier every Sid has when personas are on ('SidVariable'); None when off

    @classmethod
    def from_env(cls):
        engine = os.environ.get('SIDPLAY_ENGINE', 'bundle')
        bundle = Path(os.environ['SIDPLAY_BUNDLE']).expanduser() if os.environ.get('SIDPLAY_BUNDLE') else None
        meta = {}
        if engine == 'bundle':
            if bundle is None:
                raise SystemExit('SIDPLAY_BUNDLE is required (or SIDPLAY_ENGINE=fake)')
            meta = json.loads((bundle / 'bundle.json').read_text())
        source = meta.get('source', {}).get('path') or os.environ.get('SIDPLAY_SOURCE') or str(Path(__file__).resolve().parents[2])
        return cls(
            engine=engine, bundle=bundle,
            data=Path(os.environ.get('SIDPLAY_DATA', '~/sidplay-data')).expanduser(),
            interactive_workers=_int('SIDPLAY_WORKERS', 2),
            background_workers=_int('SIDPLAY_BACKGROUND_WORKERS', 1),
            background_nice=_int('SIDPLAY_BACKGROUND_NICE', 10),
            max_tables=_int('SIDPLAY_MAX_TABLES', 12),
            idle_minutes=_float('SIDPLAY_IDLE_MINUTES', 30),
            sid_tables=os.environ.get('SIDPLAY_SID_TABLES', '1') == '1',
            analysis=os.environ.get('SIDPLAY_ANALYSIS', '1') == '1',
            analysis_workers=_int('SIDPLAY_ANALYSIS_WORKERS', 1),
            analysis_limits={k: float(os.environ[f'SIDPLAY_{k.upper()}']) for k in
                             ('sure_cards', 'sure_need_cards', 'sure_budget', 'swap_budget', 'auction_cards', 'auction_budget')
                             if os.environ.get(f'SIDPLAY_{k.upper()}')},
            scorer=_scorer(bundle, meta),
            pace=_float('SIDPLAY_PACE', 0.5),
            trick_pause=_float('SIDPLAY_TRICK_PAUSE', 1.2),
            secure_cookies=os.environ.get('SIDPLAY_SECURE_COOKIES', '0') == '1',
            trusted_proxy=os.environ.get('SIDPLAY_TRUSTED_PROXY', '127.0.0.1'),
            bot=meta.get('bot', 'fake'),
            bot_label=meta.get('label', meta.get('bot', 'fake bot')),
            bot_identity=meta.get('spec', {}).get('identity'),
            bot_system=meta.get('system'),
            bot_stand_in=bool(meta.get('stand_in', engine == 'fake')),
            bot_description=meta.get('description'),
            source=source,
            personas=os.environ.get('SIDPLAY_PERSONAS', '1') == '1',
            variable_id=None,
        )

    def __post_init__(self):
        """Personas need the source's bridge_harness/persona.py; without it the server plays plain Sid."""
        if self.personas:
            import sys
            if self.source and self.source not in sys.path:
                sys.path.insert(0, self.source)
            from . import personas
            self.personas = personas.available()
        self.variable_id = os.environ.get('SIDPLAY_VARIABLE_ID', 'SidVariable') if self.personas else None
