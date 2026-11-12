#!/usr/bin/env python3
"""Build DDS + compact ranks + related/all-moves batch adapters (Linux/macOS)."""
import os
from pathlib import Path
import platform
import subprocess
from concurrent.futures import ThreadPoolExecutor

root = Path(__file__).resolve().parents[1]
src = root / "vendor/dds/library/src"
build = root / "build/dds"
build.mkdir(parents=True, exist_ok=True)
compiler = os.environ.get("CXX", "c++")
sources = sorted(src.rglob("*.cpp")) + sorted((root / "native").glob("*.cpp"))

def compile_one(path):
    obj = build / (str(path.relative_to(root)).replace("/", "_") + ".o")
    subprocess.run([compiler, "-std=c++20", "-O3", "-fPIC", "-pthread", "-I", str(src),
                    "-c", str(path), "-o", str(obj)], check=True)
    return str(obj)

with ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as pool:
    objects = list(pool.map(compile_one, sources))
dest = root / "bridge_harness" / ("libbridge_dds.dylib" if platform.system() == "Darwin" else "libbridge_dds.so")
subprocess.run([compiler, "-dynamiclib" if platform.system() == "Darwin" else "-shared",
                "-pthread", *objects, "-o", str(dest)], check=True)
print(dest)
