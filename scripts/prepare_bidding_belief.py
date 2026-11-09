#!/usr/bin/env python3
"""Export committed bidding TRAIN auctions for belief learning without DDS/play."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.bidding_belief_data import export


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bidding-run', type=Path, required=True)
    p.add_argument('--legacy-data', type=Path, required=True)
    p.add_argument('--exclude-groups', type=Path, action='append', default=[])
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    result = export(a.bidding_run, a.legacy_data, a.out, a.exclude_groups)
    print(json.dumps({k: result[k] for k in ('counts','splits','additional_dds_calls','additional_play_games')}, indent=2))


if __name__ == '__main__':
    main()
