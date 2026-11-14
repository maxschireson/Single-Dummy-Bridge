"""Build a Sid bundle: one bot's spec, its artifacts (verified by sha256) and the source checkout that runs it.

The play server loads exactly one bundle. Swapping Sid for another bot is building another bundle and
pointing SIDPLAY_BUNDLE at it; nothing in the server names a generation.

  # on a box, from a prepared arena run (artifacts copied from the run, checked against the manifest's hashes)
  python play/bundle.py from-run --run ~/work/runs/gen8-s7-azure1 --bot 8s-32 --source ~/sid/source --out ~/sid/bundles/8s-32

  # anywhere, from a recipe (play/bundles/*.json) and the model releases in a source checkout
  python play/bundle.py from-models --recipe play/bundles/8s-32.json --source /path/to/checkout --out /tmp/bundle

bundle.json records the bot key, its spec, its declared bidding system, the source path and commit, where the
artifacts came from, the entry point that builds the bot (see sidplay/engine.py, "The Sid contract") and whether
the bot is a stand-in until Sid itself exists. The source checkout must be the commit the bot was frozen with (or one that plays it
identically); the builder records the commit it finds and refuses a mismatch with the recipe unless --allow-commit.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import time

SCHEMA = 'sid-bundle-v1'


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def git_commit(source):
    try:
        return subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def artifact_paths(spec):
    """{key: relative path} for every artifact the spec hashes."""
    out = {}
    for key, digest in spec['artifact_sha256'].items():
        rel = spec.get(key)
        if not isinstance(rel, str) or rel.startswith('/') or '..' in Path(rel).parts:
            raise ValueError(f'Artifact {key} has no safe relative path in the spec')
        out[key] = (rel, digest)
    return out


def write_bundle(out, bot, spec, system, source, origin, label=None, provenance=None, entry=None, stand_in=False, description=None):
    out = Path(out)
    meta = dict(schema=SCHEMA, bot=bot, label=label or bot, system=system, spec=spec, entry=entry, stand_in=bool(stand_in),
                description=description,
                source=dict(path=str(Path(source).resolve()), commit=git_commit(source)),
                origin=origin, provenance=provenance or {}, created_epoch=time.time())
    (out / 'bundle.json').write_text(json.dumps(meta, indent=1, sort_keys=True))
    return meta


def from_run(run, bot, source, out, allow_commit=False, label=None, entry=None, stand_in=False):
    run, out = Path(run).expanduser().resolve(), Path(out).expanduser()
    manifest = json.loads((run / 'manifest.json').read_text())
    spec = manifest['bots'][bot]
    commit = git_commit(source)
    wanted = manifest.get('source_commit')
    if wanted and commit and not commit.startswith(wanted) and not wanted.startswith(commit) and not allow_commit:
        raise SystemExit(f'Source checkout is at {commit}, the run was frozen at {wanted} (use --allow-commit to override)')
    out.mkdir(parents=True, exist_ok=False)
    for key, (rel, digest) in artifact_paths(spec).items():
        src, dst = run / rel, out / rel
        if sha256(src) != digest:
            raise SystemExit(f'{key}: {src} does not match the manifest hash')
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    system = (manifest.get('systems') or {}).get(bot)
    return write_bundle(out, bot, spec, system, source, origin=dict(kind='run', run=str(run), manifest_identity=manifest.get('identity'),
                        run_source_commit=wanted), label=label, entry=entry, stand_in=stand_in)


PART = re.compile(r'^(?P<stem>.+)\.part-?(?P<n>\d+)$')


def model_index(source):
    """sha256 -> callable writing that file, for every whole file and every part group under models/."""
    groups, whole = defaultdict(list), []
    for path in sorted(Path(source, 'models').rglob('*')):
        if not path.is_file():
            continue
        m = PART.match(path.name)
        if m:
            groups[path.with_name(m['stem'])].append((int(m['n']), path))
        elif path.suffix in ('.npz', '.keras', '.h5'):
            whole.append(path)
    index = {}
    for path in whole:
        index[sha256(path)] = ('file', [path])
    for stem, parts in groups.items():
        parts = [p for _, p in sorted(parts)]
        h = hashlib.sha256()
        for p in parts:
            h.update(p.read_bytes())
        index[h.hexdigest()] = ('parts', parts)
    return index


def from_models(recipe, source, out, allow_commit=False, restore=False):
    recipe = json.loads(Path(recipe).read_text())
    spec, out = recipe['spec'], Path(out).expanduser()
    commit, wanted = git_commit(source), recipe.get('provenance', {}).get('source_commit')
    if wanted and commit and not commit.startswith(wanted) and not wanted.startswith(commit) and not allow_commit:
        raise SystemExit(f'Source checkout is at {commit}, the recipe names {wanted} (use --allow-commit to override)')
    if restore:                 # models not kept in git (a loop round's net): the recipe's own commands fetch and check them
        for command in recipe.get('restore', []):
            subprocess.run(shlex.split(command), cwd=source, check=True)
    index = model_index(source)
    out.mkdir(parents=True, exist_ok=False)
    for key, (rel, digest) in artifact_paths(spec).items():
        if digest not in index:
            raise SystemExit(f'{key}: no model release in {source}/models has sha256 {digest}')
        _, parts = index[digest]
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(dst, 'wb') as f:
            for p in parts:
                f.write(p.read_bytes())
        if sha256(dst) != digest:
            raise SystemExit(f'{key}: restored file does not match {digest}')
    return write_bundle(out, recipe['bot'], spec, recipe.get('system'), source, origin=dict(kind='models', recipe=recipe),
                        label=recipe.get('label'), provenance=recipe.get('provenance'), entry=recipe.get('entry'),
                        stand_in=recipe.get('stand_in', False), description=recipe.get('description'))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('from-run')
    a.add_argument('--run', required=True)
    a.add_argument('--bot', required=True)
    a.add_argument('--source', required=True)
    a.add_argument('--out', required=True)
    a.add_argument('--allow-commit', action='store_true')
    a.add_argument('--label')
    a.add_argument('--entry', help='module:callable building the bot (default: the arena-runtime adapter)')
    a.add_argument('--stand-in', action='store_true', help='this bot plays until Sid itself exists')
    b = sub.add_parser('from-models')
    b.add_argument('--recipe', required=True)
    b.add_argument('--source', required=True)
    b.add_argument('--out', required=True)
    b.add_argument('--allow-commit', action='store_true')
    b.add_argument('--restore', action='store_true', help="first run the recipe's restore commands in the source checkout")
    args = p.parse_args()
    if args.cmd == 'from-run':
        meta = from_run(args.run, args.bot, args.source, args.out, args.allow_commit, args.label, args.entry, args.stand_in)
    else:
        meta = from_models(args.recipe, args.source, args.out, args.allow_commit, args.restore)
    print(json.dumps(dict(bot=meta['bot'], label=meta['label'], stand_in=meta['stand_in'], entry=meta['entry'], system=meta['system'],
                          source=meta['source'], artifacts=sorted(meta['spec']['artifact_sha256']))))
