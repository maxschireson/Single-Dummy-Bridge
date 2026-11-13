"""Immutable bot manifests and verified artifacts for weight-only generations."""
from copy import deepcopy
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import re
import shutil

from .training import digest
from .selfplay import atomic_json


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def resolve_factory(name):
    module, attr = name.split(':', 1)
    return getattr(importlib.import_module(module), attr)


def source_hash():
    root = Path(__file__).resolve().parents[1]
    h = hashlib.sha256()
    paths = sorted((root / 'bridge_harness').rglob('*.py')) + sorted((root / 'scripts').glob('*.py'))
    paths += sorted((root / 'native').rglob('*.cpp'))
    paths += sorted((root / 'bridge_harness').glob('libbridge_dds.*'))
    for p in paths:
        h.update(str(p.relative_to(root)).encode()); h.update(p.read_bytes())
    return h.hexdigest()


def behavior_identity(spec):
    return digest({k:v for k,v in spec.items() if k != 'training'})


def freeze_bot(root, name, spec):
    """Copy weights/configs; refuse rebinding names or silently changing code."""
    if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
        raise ValueError('Unsafe bot name')
    spec = deepcopy(spec)
    for key in ('factory', 'kwargs', 'budget'):
        if key not in spec:
            raise ValueError(f'Missing bot field: {key}')
    factory_path = Path(inspect.getfile(resolve_factory(spec['factory']))).resolve()
    spec['factory_sha256'] = sha(factory_path)
    spec['source_sha256'] = source_hash()
    sources = {}
    for key, path in spec.get('artifacts', {}).items():
        if not re.fullmatch(r'[A-Za-z0-9_-]+', key):
            raise ValueError('Unsafe artifact key')
        sources[key] = Path(path).resolve()
    spec['artifacts'] = {k: dict(file=f'artifacts/{k}{p.suffix}', sha256=sha(p)) for k, p in sources.items()}
    identity = digest(spec)
    dest = Path(root) / 'bots' / name
    manifest = dict(schema=1, name=name, identity=identity, behavior_identity=behavior_identity(spec), spec=spec)
    if (dest / 'bot.json').exists():
        if json.loads((dest / 'bot.json').read_text()) != manifest:
            raise ValueError(f'Immutable bot name already used: {name}')
        verify_bot(dest / 'bot.json')
        return dest / 'bot.json'
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'artifacts').mkdir(exist_ok=True)
    for key, p in sources.items():
        target = dest / spec['artifacts'][key]['file']
        shutil.copyfile(p, target)
        if sha(target) != spec['artifacts'][key]['sha256']:
            raise ValueError('Artifact changed during copy')
    atomic_json(dest / 'bot.json', manifest)
    return dest / 'bot.json'


def verify_bot(path, check_source=True):
    path = Path(path)
    m = json.loads(path.read_text()); spec = m['spec']
    if digest(spec) != m['identity']:
        raise ValueError('Bot manifest was altered')
    if behavior_identity(spec) != m['behavior_identity']:
        raise ValueError('Bot behavior identity was altered')
    if check_source and spec['source_sha256'] != source_hash():
        raise ValueError('Campaign code/solver changed; use its pinned checkout')
    if sha(inspect.getfile(resolve_factory(spec['factory']))) != spec['factory_sha256']:
        raise ValueError('Factory source changed')
    for item in spec['artifacts'].values():
        artifact = (path.parent / item['file']).resolve()
        if not artifact.is_relative_to(path.parent.resolve()) or sha(artifact) != item['sha256']:
            raise ValueError('Artifact missing, changed, or outside bot directory')
    return m


def build_player(path):
    m = verify_bot(path, check_source=False)
    def expand(value):
        if isinstance(value, str) and value.startswith('$artifact:'):
            return str(Path(path).parent / m['spec']['artifacts'][value.split(':', 1)[1]]['file'])
        if isinstance(value, dict): return {k: expand(v) for k, v in value.items()}
        if isinstance(value, list): return [expand(v) for v in value]
        return value
    return resolve_factory(m['spec']['factory'])(**expand(m['spec']['kwargs']))


def auction_pimc(weights, samples=32, objective='tricks', batch=True, near_tie=.125, strength=1.):
    from .bidding_sampling import AuctionWeights, WeightedSampler
    from .players import PIMCPlayer
    net = AuctionWeights(weights)
    return PIMCPlayer(samples, objective, batch, near_tie,
                      sampler_factory=lambda o: WeightedSampler(o, net.logits(o), strength))
