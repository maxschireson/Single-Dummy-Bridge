#!/usr/bin/env python3
"""scripts/gen8_match.py with the plan engine: duplicate matches, fresh random deals, no forks.

  python scripts/plan_match.py --source CAPSULE/recovery --bots configs/plan-bots.json --pair pm-32~7f-32-v41 \\
      --deals 600 --seed 91 --workers 8 --out DIR

Every argument is gen8_match.py's. The only difference is the player factory: a bot whose spec says
`engine: plan` is a bridge_harness.plan_player.PlanPlayer (Gen 7 with playouts to trick 13 where Gen 7 has its
tree; settings under the bot's `plan` key), and every other bot is built as gen8_match builds it.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import gen8_match  # noqa: E402
from bridge_harness import plan_player  # noqa: E402

_start = gen8_match.start


def start(*args):
    gen8_match.player = plan_player.player
    _start(*args)


gen8_match.start = start
gen8_match.player = plan_player.player

if __name__ == '__main__':
    gen8_match.main()
