"""Write and verify the pinned BEN neural-bidding, 32-sample lead/play profile."""
import argparse
import configparser
import io
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bridge_harness.loop_registry import sha

COMMIT='9b5f43104aeac713a80b73513f2f2d6daf9f8769'
OVERRIDES={
    'bidding':{'search_threshold':'-1','check_final_contract':'False','eval_opening_bid':'False','eval_after_bid_count':'-1'},
    'sampling':{'no_samples_when_no_search':'True','sample_hands_opening_lead':'32','sample_hands_for_review':'32'},
    'cardplay':{'sample_hands_play':'32','min_sample_hands_play':'32','min_sample_hands_play_bad':'32','play_nn_only':'False','use_suitc':'False'},
    'models':{'use_bba':'False','consult_bba':'False','use_bba_rollout':'False','use_bba_to_count_aces':'False','matchpoint':'False'},
    'pimc':{'pimc_use_declaring':'False','pimc_use_defending':'False'},
    'ace':{'ace_use_declaring':'False','ace_use_defending':'False'},
    'dds':{'dds_max_threads':'1'}
}

def profile(ben,samples=16):
    config=configparser.ConfigParser(interpolation=None)
    if not config.read(ben/'src/config/default_api.conf'):raise ValueError('BEN API config missing')
    for section,values in OVERRIDES.items():
        if not config.has_section(section):config.add_section(section)
        config[section].update(values)
    for section,key in (("sampling","sample_hands_opening_lead"),("sampling","sample_hands_for_review"),("cardplay","sample_hands_play"),("cardplay","min_sample_hands_play"),("cardplay","min_sample_hands_play_bad")):
        config[section][key]=str(samples)
    return config

def validate(config,samples=16):
    for section,values in OVERRIDES.items():
        for key,expected in values.items():
            if key in {'sample_hands_opening_lead','sample_hands_for_review','sample_hands_play','min_sample_hands_play','min_sample_hands_play_bad'}:expected=str(samples)
            if config.get(section,key).lower()!=expected.lower():raise ValueError(f'BEN profile drift: {section}.{key}')

def prepare(ben,dest,samples=16):
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ben,text=True).strip()
    if revision!=COMMIT:raise ValueError('Different BEN source revision')
    config=profile(ben,samples);validate(config,samples);buffer=io.StringIO();config.write(buffer)
    if dest.exists() and dest.read_text()!=buffer.getvalue():raise ValueError('Refusing to overwrite a different BEN profile')
    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(buffer.getvalue())
    models={}
    for section in config.sections():
        for key,value in config[section].items():
            if value.endswith(('.keras','.h5','.onnx')):
                path=ben/value
                if not path.exists():raise ValueError('Missing BEN model: '+str(path))
                models[section+'.'+key]=dict(path=value,sha256=sha(path))
    result=dict(source_commit=revision,config_sha256=sha(dest),model_sha256=models,bidding='neural-only',
        opening_lead_samples=samples,play_samples=samples,dds_threads=1,
        sample_interpretation=f'{samples} retained hand samples per searched lead/play; forced moves and endings with fewer possible worlds can use fewer.',
        status='profile-and-model-files-verified')
    dest.with_suffix('.provenance.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ben',type=Path,required=True)
    p.add_argument('--out',type=Path,default=ROOT/'configs/ben-gen5-16.conf');a=p.parse_args()
    print(json.dumps(prepare(a.ben.resolve(),a.out.resolve()),indent=2))
