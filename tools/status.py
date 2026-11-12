#!/usr/bin/env python3
"""Regenerate STATUS.md from tasks/*.md and experiments/*.md.

    python3 tools/status.py            # rewrites STATUS.md in the branch root
    python3 tools/status.py --check    # exit 1 if a header is malformed; writes nothing

A task or experiment file starts with a header of `key: value` lines between two `---`
lines (README.md). This script reads only the header and the first line under `## Result`.
"""
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
STATES = ('leased', 'submitted', 'blocked', 'open', 'proposed', 'resolved')
REQUIRED = ('id', 'title', 'area', 'kind', 'owner', 'state', 'priority')


def header(path):
    lines = path.read_text().splitlines()
    if not lines or lines[0].strip() != '---':
        raise ValueError(f'{path.name}: no header')
    out = {}
    for line in lines[1:]:
        if line.strip() == '---':
            break
        if ':' not in line:
            raise ValueError(f'{path.name}: bad header line {line!r}')
        key, _, value = line.partition(':')
        out[key.strip()] = value.split(' #')[0].strip()
    else:
        raise ValueError(f'{path.name}: header is not closed')
    for key in REQUIRED:
        if not out.get(key):
            raise ValueError(f'{path.name}: header has no {key}')
    if out['state'] not in STATES:
        raise ValueError(f'{path.name}: unknown state {out["state"]!r}')
    if out['id'] != path.stem:
        raise ValueError(f'{path.name}: id {out["id"]!r} differs from the file name')
    return out


def result_line(path):
    lines = path.read_text().splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower() == '## result':
            for nxt in lines[i + 1:]:
                if nxt.strip():
                    return nxt.strip()
    return ''


def late(h, now):
    for key in ('lease_until', 'due'):
        value = h.get(key)
        if value and (key == 'lease_until') == (h['state'] == 'leased') and h['state'] not in ('resolved', 'submitted'):
            try:
                when = datetime.strptime(value.replace('Z', '+0000'), '%Y-%m-%dT%H:%M%z')
            except ValueError:
                continue
            if when < now:
                return 'lease expired' if key == 'lease_until' else 'past due'
    return ''


def table(rows, now, with_result=False):
    head = '| Id | Title | Owner | Holder | State | Priority | Due | Note |\n| --- | --- | --- | --- | --- | --- | --- | --- |\n'
    body = ''
    for h, path in rows:
        note = late(h, now)
        if with_result and h['state'] == 'resolved':
            note = (h.get('resolution', '') + '. ' + result_line(path)).strip('. ')
        elif h['state'] == 'resolved':
            note = h.get('resolution', '')
        folder = path.parent.name
        body += (f"| [{h['id']}]({folder}/{path.name}) | {h['title']} | {h['owner']} | {h.get('holder', '')} | {h['state']} | "
                 f"{h['priority']} | {h.get('due', '')} | {note} |\n")
    return head + body if body else '_none_\n'


def main():
    check = '--check' in sys.argv
    now = datetime.now(timezone.utc)
    loaded, errors = {}, []
    for folder in ('tasks', 'experiments'):
        rows = []
        for path in sorted((ROOT / folder).glob('*.md')):
            try:
                rows.append((header(path), path))
            except ValueError as e:
                errors.append(str(e))
        loaded[folder] = rows
    if errors:
        print('\n'.join(errors), file=sys.stderr)
    if check:
        return 1 if errors else 0
    order = {s: i for i, s in enumerate(STATES)}
    rank = {'high': 0, 'medium': 1, 'low': 2}
    key = lambda r: (order[r[0]['state']], rank.get(r[0]['priority'], 3), r[0]['id'])
    tasks, experiments = sorted(loaded['tasks'], key=key), sorted(loaded['experiments'], key=key)
    counts = {}
    for h, _ in tasks:
        counts.setdefault(h['owner'], {}).setdefault(h['state'], 0)
        counts[h['owner']][h['state']] += 1
    text = ['# Gen 9 status', '',
            f'Generated {now:%Y-%m-%d %H:%M} UTC by `tools/status.py` from the task and experiment files. Do not edit by hand.', '',
            '## Tasks by owner', '', '| Owner | ' + ' | '.join(STATES) + ' |', '| --- |' + ' ---: |' * len(STATES)]
    for owner in sorted(counts):
        text.append(f'| {owner} | ' + ' | '.join(str(counts[owner].get(s, 0)) for s in STATES) + ' |')
    text += ['', '## Tasks', '', table(tasks, now), '## Experiments', '', table(experiments, now, with_result=True)]
    if errors:
        text += ['## Files with a malformed header', ''] + [f'- {e}' for e in errors] + ['']
    (ROOT / 'STATUS.md').write_text('\n'.join(text))
    return 0


if __name__ == '__main__':
    sys.exit(main())
