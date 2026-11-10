#!/bin/bash
set -euo pipefail
cd /workspace/scratch/832d665e0384/bidding-structure
exec /workspace/scratch/bbe90ba77a68/venv/bin/python ops/persistent_bidding_structure.py
