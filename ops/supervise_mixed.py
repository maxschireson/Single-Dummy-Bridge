"""Versioned training handoff without modifying a frozen collection runtime.

The generation pins play/collection code. training-config.json independently
pins the boundary implementation, which cannot influence current board play.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.improvement import read
from bridge_harness.loop_registry import sha
import ops.mixed_generation as runtime

original=runtime.supervised_command


def command(args,root,timeout):
    if len(args)>1 and args[1]=='ops/finish_mixed_generation.py':
        config=read(root/'training-config.json')
        transition=config['transition']
        if sha(ROOT/transition['path'])!=transition['sha256']:
            raise ValueError('Pinned training transition changed')
        args=[args[0],transition['path'],*args[2:]]
    return original(args,root,timeout)


if __name__=='__main__':
    runtime.supervised_command=command
    runtime.main()
