#!/usr/bin/env python3
"""Save a hot, resumable checkpoint without blocking an active bidding worker.

The atomic state file chooses the committed model/optimizer checkpoint. DDS is
copied with SQLite's backup API. Evaluation shards are deliberately omitted: on
restore, any pending evaluation is recomputed using the committed model, rather
than risking shards from a newer snapshot. Source is retrieved from GitHub.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import zipfile


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--source-commit', help='Published commit, when the checkout was pushed through the GitHub API')
    args = p.parse_args()
    root = args.run.resolve()
    manifest = json.loads((root/'manifest.json').read_text())
    with tempfile.TemporaryDirectory() as directory:
        staging = Path(directory)
        for _ in range(3):
            state = json.loads((root/'state.json').read_text())
            if not state['checkpoint']:
                raise RuntimeError('No committed optimizer checkpoint yet')
            prefix = Path(state['checkpoint'])
            files = list(prefix.parent.glob(prefix.name+'.*'))
            if len(files) < 2:
                continue
            try:
                for source in files:
                    target = staging/'run'/source.relative_to(root)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
            except FileNotFoundError:
                continue
            break
        else:
            raise RuntimeError('Checkpoint changed during snapshot; retry')
        (staging/'run/state.json').write_text(json.dumps(state, indent=2))
        shutil.copy2(root/'manifest.json', staging/'run/manifest.json')
        for champion in state['champions'][1:]:
            source = Path(champion)
            target = staging/'run'/source.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        # Keep exact baseline bytes for the frozen opponent and KL anchor.
        for key in ('origin', 'dds_library'):
            source = Path(manifest[key]); target = staging/'dependencies'/source.name
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(source, target)
        with sqlite3.connect(root/'dds.sqlite') as src, sqlite3.connect(staging/'run/dds.sqlite') as dst:
            src.backup(dst)
        repo = Path(__file__).resolve().parents[1]
        revision = args.source_commit or subprocess.check_output(['git','rev-parse','HEAD'], cwd=repo, text=True).strip()
        recovery = dict(source_repository='maxschireson/Single-Dummy-Bridge',
                        source_branch='research/dds-bidding-loop', source_commit=revision,
                        original_run_path=str(root), training_pairs=state['total_train_pairs'],
                        note='Restore source at this revision. Remap run/checkpoint/champion and dependency paths '
                             'in state/manifest to their restored locations; keep all hashes and config unchanged. '
                             'Recreate config from manifest.config. Resume with run_bidding_loop.py.')
        (staging/'RECOVERY.json').write_text(json.dumps(recovery, indent=2))
        hashes = {str(f.relative_to(staging)): hashlib.sha256(f.read_bytes()).hexdigest()
                  for f in staging.rglob('*') if f.is_file()}
        (staging/'SHA256.json').write_text(json.dumps(hashes, indent=2))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.out, 'w', zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
            for f in staging.rglob('*'):
                if f.is_file():
                    archive.write(f, f.relative_to(staging))
        with zipfile.ZipFile(args.out) as archive:
            if archive.testzip() is not None:
                raise RuntimeError('Archive CRC verification failed')
        print(json.dumps(dict(path=str(args.out.resolve()), bytes=args.out.stat().st_size,
                              training_pairs=state['total_train_pairs'], source_commit=revision)))


if __name__ == '__main__':
    main()
