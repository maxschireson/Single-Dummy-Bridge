"""Freeze clean play outcomes plus reconstructed existing DDS labels."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.bidding_refresh import prepare_play, recover_dds, sha
from bridge_harness.bidding_loop import atomic_json


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--export', required=True)
    p.add_argument('--local-run', action='append', default=[])
    p.add_argument('--dds-checkpoint', required=True)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    play, counts, sources = prepare_play(a.export, a.local_run)
    dds = recover_dds(a.dds_checkpoint)
    trained = {r['family'] for r in dds if r['split'] == 'train'}
    # A family previously seen by the starting bidder cannot become held out.
    excluded = [r for r in play if r['family'] in trained and r['split'] != 'train']
    play = [r for r in play if r not in excluded]
    # Prefer clean play on overlapping training boards, avoiding double sampling.
    play_families = {r['family'] for r in play}
    dds = [r for r in dds if r['family'] not in play_families]
    rows = play+dds
    families = {}
    for r in rows:
        if r['family'] in families and families[r['family']] != r['split']:
            raise ValueError('Family crosses data partitions')
        families[r['family']] = r['split']
    atomic_json(a.out/'dataset.json', rows)
    atomic_json(a.out/'sources.json', sources)
    summary = dict(schema='clean-bidding-refresh-data-v1', clean_play=counts,
        excluded_pretrained_holdout=len(excluded),
        counts=dict(Counter(r['source']+'/'+r['split'] for r in rows)),
        dataset_sha256=sha(a.out/'dataset.json'), sources_sha256=sha(a.out/'sources.json'),
        additional_dds_solves=0, original_ben_training_corpus_available=False,
        dds_note='40k prior training families and prior 1k development cache; no virgin DDS test claimed',
        reward_note='Same-strain/same-declarer clean trick reuse; new auctions change information and incentives; partial support',
        export_sha256=sha(Path(a.export)/'export.json'),
        checkpoint_manifest_sha256=sha(Path(a.dds_checkpoint)/'run/manifest.json'))
    atomic_json(a.out/'summary.json', summary)
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
