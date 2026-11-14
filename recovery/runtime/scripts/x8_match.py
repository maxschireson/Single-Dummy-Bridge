#!/usr/bin/env python3
"""scripts/gen8_match.py with the 8X engine: duplicate matches, fresh random deals, no forks.

  SURE_BIN=/path/to/sure_cpp python scripts/x8_match.py --source CAPSULE/recovery --bots configs/x8-bots.json \\
      --pair 8xr0-v41~8p-32-v41 --deals 600 --seed 141 --workers 8 --out DIR [--episodes]

Every argument is gen8_match.py's. A bot whose spec says `engine: gen8x` is a bridge_harness.x8_player.X8Player
(settings under the bot's `x8` key; `rollout_policy` names the rollout net, relative to the repository like
`gen7_policy`), one that says `engine: plan` is the plan session's PlanPlayer, and every other bot is built as
gen8_match builds it. Bots with claims need the claim solver: SURE_BIN (see bridge_harness/x8_claims.py).

Each board's row in results.jsonl carries, per role, what the 8X decisions did (`x8`): decisions by mode, cards
moved by the rollouts, by the guarantee and by the hand-over odds, rollouts and net rows, claim questions, forks
recorded and seconds. With --episodes the full records keep every decision's `x8` note (x8_capture.py).

--feature-forks: wherever an 8X feature changed the first-named bot's card, the card plain Gen 8 would have played is
played out too, from the same position with the same bots (the collector's audit forks at probability 1, one level
deep; X8Player names that card only where a feature changed the card, capture.audit 'features'). The match's IMPs are
still the root tables'. Each fork is listed in the row (`search.x8_forks`: features, contract class, trick, IMPs to the
deciding side of the 8X card over plain Gen 8's); scripts/x8_forks.py pools them.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import gen8_match  # noqa: E402
from bridge_harness import plan_player, x8_player  # noqa: E402

_start = gen8_match.start
_summarise = gen8_match.summarise_actions
_build = gen8_match.build_manifest


def player(spec, root, reference=None):
    if spec.get('engine') == x8_player.ENGINE:
        return x8_player.X8Player(spec, root, reference)
    return plan_player.player(spec, root, reference)


FEATURE_FORKS = dict(probability=1., multiplier=60., max_depth=1, max_forks=96)


def build_manifest(source, bots_file, pair, seed):
    """gen8_match's manifest, with the 8X bots' extra model paths made absolute as it does for `gen7_policy`, and with
    --feature-forks the audit budget that forks every changed decision."""
    m = _build(source, bots_file, pair, seed)
    changed = FORKS
    if FORKS:
        m['audit'], m['ben_audit'] = dict(FEATURE_FORKS), dict(FEATURE_FORKS)
    for spec in m['bots'].values():
        paths = [('rollout_policy', spec)] + [('policy', other) for other in (spec.get('x8') or {}).get('others') or ()]
        for key, holder in paths:
            if holder.get(key) and not Path(holder[key]).is_absolute():
                path = (ROOT / holder[key]).resolve()
                if not path.exists():
                    import subprocess
                    for restore in sorted(path.parent.glob('restore*.py')):
                        subprocess.run([sys.executable, restore.name], cwd=path.parent, check=True, stdout=subprocess.DEVNULL)
                holder[key] = str(path)
                changed = True
        if changed:
            spec.pop('identity', None)
            spec['identity'] = gen8_match.digest(spec)
    if changed:
        m.pop('identity', None)
        m['identity'] = gen8_match.digest(m)
    return m


def contract_class(text):
    """'partscore' (undoubled, below game), 'game' (games and slams), 'doubled', or None for a passed-out board."""
    if not text:
        return None
    level, strain = int(text[0]), text[1]
    if 'X' in text:
        return 'doubled'
    return 'game' if level >= {'N': 3, 'S': 4, 'H': 4, 'D': 5, 'C': 5}[strain] else 'partscore'


def feature_forks(record):
    """[features, contract class, trick, IMPs] for every fork the audits played (identical cards are not forks)."""
    out = []
    for table in record.values():
        if 'audits' not in table:
            continue
        cls = contract_class(table['board'].get('contract'))
        for a in table['audits']:
            if a.get('identical_action'):
                continue
            act = table['tables'][a['parent_table']]['actions'][a['ply']]
            out.append(['+'.join(act.get('x8_features') or ['?']), cls, a['ply'] // 4 + 1, a['gain_imps']])
    return out


def summarise_actions(record, roles):
    out = _summarise(record, roles)
    for r in roles:
        out[r]['x8'] = dict(rollout=0, blend=0, search=0, claim=0, consulted=0, moved=0, guaranteed=0, guarantee_moved=0, odds=0, odds_split=0,
                            mixed=0, rollouts=0, net_rows=0, asked=0, floored=0., ended=0, forks=0, seconds=0.)
    for table in record.values():
        for t in table['tables'][:1]:
            for a in t['actions']:
                role = a.get('role') or a.get('player')
                note = a.get('x8')
                if role not in out or not note:
                    continue
                s = out[role]['x8']
                s[note['mode']] += 1
                s['guaranteed'] += note.get('claim') == 'guaranteed'
                s['guarantee_moved'] += bool(note.get('moved'))
                s['mixed'] += bool(note.get('mixed'))
                if note.get('n'):
                    s['consulted'] += 1
                    s['rollouts'] += sum(note['n'])
                    s['net_rows'] += note.get('net_rows', 0)
                    s['asked'] += note.get('asked', 0)
                    s['floored'] += note.get('floored', 0.)
                    s['ended'] += note.get('ended', 0)
                    s['forks'] += len(note.get('forks') or ())
                    s['seconds'] += sum((note.get('seconds') or {}).values())
                    if note['mode'] == 'rollout':           # did the rollouts play another card than the net's likeliest candidate?
                        s['moved'] += note['chosen'] not in note['runs'][0]
                        if note.get('lead'):                # an opening lead from rollouts (counted under 'rollout' too)
                            s['lead'] = s.get('lead', 0) + 1
                            s['lead_moved'] = s.get('lead_moved', 0) + (note['chosen'] not in note['runs'][0])
                            s['lead_seconds'] = round(s.get('lead_seconds', 0.) + sum((note.get('seconds') or {}).values()), 3)
                    else:
                        s['moved'] += a.get('selected_pimc_gap', 0.) > 1e-9
                    if note.get('odds'):
                        s['odds'] += 1
                        s['odds_split'] += max(note['odds']) - min(note['odds']) > 1e-9
    for r in roles:
        for k in ('floored', 'seconds'):
            out[r]['x8'][k] = round(out[r]['x8'][k], 3)
    if FORKS:
        out['x8_forks'] = feature_forks(record)
    return out


def start(*args):
    gen8_match.player = player
    gen8_match.summarise_actions = summarise_actions
    _start(*args)


FORKS = '--feature-forks' in sys.argv
if FORKS:
    sys.argv.remove('--feature-forks')

gen8_match.start = start
gen8_match.player = player
gen8_match.summarise_actions = summarise_actions
gen8_match.build_manifest = build_manifest

if __name__ == '__main__':
    gen8_match.main()
