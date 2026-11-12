"""Build an isolated original DDS library with the production compiler flags."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import time

REVISION='0f969b86a4841f438fd0cdff2924c4f2404abf6a'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--git-repo',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--compiler',default='c++')
    a=p.parse_args();root=a.out.resolve();root.mkdir(parents=True,exist_ok=True)
    lib=root/'libdds-upstream.so'
    if lib.exists():raise ValueError('Refusing to overwrite an existing baseline library')
    srcroot=root/'upstream';srcroot.mkdir(exist_ok=True)
    data=subprocess.check_output(['git','-C',str(a.git_repo),'archive',REVISION,'library/src','LICENSE'])
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:tar.extractall(srcroot,filter='data')
    src=srcroot/'library/src';obj=root/'build-upstream';obj.mkdir(exist_ok=True)
    objects=[];start=time.time();flags=['-std=c++20','-O3','-fPIC','-pthread']
    # Serial compilation leaves the active arena's other CPUs available.
    for path in sorted(src.rglob('*.cpp')):
        dest=obj/(str(path.relative_to(src)).replace('/','_')+'.o')
        subprocess.run([a.compiler,*flags,'-I',str(src),'-c',str(path),'-o',str(dest)],check=True)
        objects.append(str(dest))
    subprocess.run([a.compiler,'-shared','-pthread',*objects,'-o',str(lib)],check=True)
    record=dict(upstream_revision=REVISION,library=str(lib),
        sha256=hashlib.sha256(lib.read_bytes()).hexdigest(),flags=flags,
        compiler=subprocess.check_output([a.compiler,'--version'],text=True).splitlines()[0],
        source_files=len(objects),seconds=time.time()-start)
    (root/'upstream-build.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
