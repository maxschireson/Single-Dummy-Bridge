"""Freeze one latest bidder for ALL versions in a play-only arena generation."""
import configparser
from pathlib import Path
import shutil
from bridge_harness.improvement import read
from bridge_harness.loop_registry import sha
from bridge_harness.training import digest


def prepare_shared_bidder(root, config):
    root=Path(root).resolve();registry=read(config['bidding_registry'])
    source=Path(registry['model']).resolve()
    if sha(source)!=registry['sha256']:raise ValueError('Latest bidding checkpoint changed')
    target=root/'bidding'/source.name;target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        if sha(target)!=registry['sha256']:raise ValueError('Frozen shared bidder changed')
    else:shutil.copy2(source,target)
    path=root/'ben-bid-config.conf'
    parser=configparser.ConfigParser();parser.read(config['ben_config'])
    parser.set('bidding','bidder',str(target));parser.set('bidding','alert_supported','False')
    if path.exists():
        old=configparser.ConfigParser();old.read(path)
        if dict(old['bidding'])!=dict(parser['bidding']):raise ValueError('Existing auction configuration differs')
    else:
        with path.open('w') as f:parser.write(f)
    if parser.getfloat('bidding','search_threshold')!=-1 or parser.getboolean('bidding','check_final_contract'):
        raise ValueError('Shared arena bidder must be neural-only, without rescue')
    return dict(model=str(target.relative_to(root)),sha256=registry['sha256'],
        config=str(path.relative_to(root)),config_sha256=sha(path),trained_pairs=registry['trained_pairs'],
        scope='One latest bidding network shared by ALL current and historical cardplay versions.',
        promotion_metric='Paired cardplay IMPs under identical frozen common auctions; bidding is not separately scored here.')


def bind_shared_bidder(bots, shared):
    for spec in bots.values():
        spec['bidding']=shared['model'];spec['artifact_sha256']['bidding']=shared['sha256']
        spec.pop('identity',None);spec['identity']=digest(spec)
