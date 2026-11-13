"""The Sid contract: a bundle whose entry point is not the arena adapter plugs in without server changes."""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT.parent)]

from bridge_harness.core import Board, Contract, Game   # noqa: E402
from sidplay import engine   # noqa: E402
from sidplay.rules import new_deal   # noqa: E402


def test_custom_entry(tmp_path):
    (tmp_path / 'bundle.json').write_text(json.dumps(dict(
        schema='sid-bundle-v1', bot='toy', label='Toy', system=None, spec={}, entry='tests.toy_sid:ToySid', stand_in=True,
        source=dict(path=str(ROOT.parent), commit=None))))
    engine.init_worker(str(tmp_path))
    assert engine.info()['bot'] == 'toy'
    hands = new_deal(random.Random(3))
    assert engine.bid(hands[0], 0, 0, 'None', [])[0] == '1C'
    game = Game(Board('t', hands, Contract.parse('1C', 0), 0, 'None', ('1C', 'PASS', 'PASS', 'PASS')))
    card, _ = engine.play(game.observation(), 'human', (None, None), 7)
    assert card in game.observation().legal
    record = engine.sid_table(hands, 0, 'None', 'x', 5, (None, None))
    assert record['calls'] == ['1C', 'PASS', 'PASS', 'PASS'] and record['contract'] == '1C' and len(record['play']) == 52


def test_illegal_call_is_refused(tmp_path, monkeypatch):
    test_custom_entry(tmp_path)
    monkeypatch.setattr(engine._S['sid'], 'bid', lambda *a: '1C')
    try:
        engine.bid(new_deal()[1], 1, 0, 'None', ['1C'])
    except RuntimeError as e:
        assert 'illegal call' in str(e)
    else:
        raise AssertionError('an insufficient bid was accepted')
