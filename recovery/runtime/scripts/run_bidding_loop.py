#!/usr/bin/env python3
"""Launch/resume the DDS-only bidding improvement campaign."""
import os
from pathlib import Path
import sys

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
os.environ.setdefault('OMP_NUM_THREADS', '2')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == '__main__':
    from bridge_harness.bidding_loop import main
    main()
