"""Preserve newly completed full episodes without duplicating older archives."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--previous', required=True, action='append', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('Refusing to overwrite checkpoint')
    prior = set()
    archive_info = []
    for archive in args.previous:
        with zipfile.ZipFile(archive) as z:
            names = {Path(name).name for name in z.namelist()
                     if re.fullmatch(r'\d{6}\.json\.gz', Path(name).name)}
        prior.update(names)
        archive_info.append(dict(path=str(archive), episode_count=len(names)))
    files = sorted((args.run/'episodes').glob('*.json.gz'))
    added = [p for p in files if p.name not in prior]
    manifest = json.loads((args.run/'manifest.json').read_text())
    index = dict(schema='arena-full-episode-delta-v1', created_epoch=time.time(),
                 manifest_identity=manifest['identity'], total_completed_at_snapshot=len(files),
                 previous_archives=archive_info, previous_episode_count=len(prior),
                 new_episode_count=len(added), new_episodes=[],
                 completed_indices=[int(p.name.split('.')[0]) for p in files],
                 restore='Overlay run/ on the exact prior recovery run. Keep original frozen models and runtime; do not replace full episodes with public replays.')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        for name in ('manifest.json','status.json','progress.jsonl','publisher-status.json','created_epoch.json','families.json','boards.jsonl','collection-plan.json'):
            path = args.run/name
            if path.exists():
                z.write(path, 'run/'+name)
        for path in added:
            raw = path.read_bytes()
            z.writestr('run/episodes/'+path.name, raw, compress_type=zipfile.ZIP_STORED)
            index['new_episodes'].append(dict(file=path.name, sha256=hashlib.sha256(raw).hexdigest()))
        z.writestr('delta-index.json', json.dumps(index, separators=(',',':')))
    with zipfile.ZipFile(args.out) as z:
        if z.testzip() is not None:
            raise ValueError('Checkpoint integrity failure')
    print(json.dumps(dict(file=str(args.out), bytes=args.out.stat().st_size,
                         total_completed=len(files), new_episodes=len(added), prior_episodes=len(prior))))


if __name__ == '__main__':
    main()
