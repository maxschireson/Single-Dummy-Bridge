"""Exercise the frozen production path and retain evidence of actual capture."""
import gzip
import hashlib
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
RUNTIME = BASE / 'runtime'
RUN = BASE / 'run'
sys.path.insert(0, str(RUNTIME))
from ops import smoke_gen7 as smoke


def fields(value, counts):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in counts and child is not None:
                counts[key] += 1
            fields(child, counts)
    elif isinstance(value, list):
        for child in value:
            fields(child, counts)


def main():
    folder = BASE / 'preflight-episodes'
    folder.mkdir(exist_ok=True)
    evidence = []
    original = smoke.gen5_runtime.play

    def observed(*args, **kwargs):
        record = original(*args, **kwargs)
        counts = dict(guess_size=0, best_share=0)
        fields(record, counts)
        sources = sorted({table['board']['auction_source'] for table in record['unique_tables'].values()})
        assert all(source.startswith('systems:') for source in sources), sources
        if record['pair'] == '8c-32~8s-32':
            assert record['regimes']['common']['imps'] == 0, 'Identical Gen8 engines under house bidding must tie'
        raw = gzip.compress((json.dumps(record, sort_keys=True) + '\n').encode(), mtime=0)
        path = folder / f"{record['index']:06d}.json.gz"
        path.write_bytes(raw)
        evidence.append(dict(index=record['index'], pair=record['pair'], gap_forks=record['gap_fork_count'],
            episode_sha256=hashlib.sha256(raw).hexdigest(), auction_sources=sources,
            root_tables={key: len(row['tables']) for key, row in record['regimes'].items()}, **counts))
        print(json.dumps(dict(capture=evidence[-1])), flush=True)
        return record

    smoke.gen5_runtime.play = observed
    report = smoke.smoke(RUN, RUN / 'preflight.json', deals=2)
    assert len(evidence) == 10
    assert sum(row['gap_forks'] for row in evidence) > 0
    assert all(sum(row[key] for row in evidence) > 0 for key in ('guess_size', 'best_share'))
    result = dict(manifest=report['manifest'], deals=evidence,
        gap_forks=sum(row['gap_forks'] for row in evidence),
        guess_size=sum(row['guess_size'] for row in evidence),
        best_share=sum(row['best_share'] for row in evidence),
        scientific_runtime_used=True, replay_score_and_systems_verified=True)
    (RUN / 'preflight-capture.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(preflight_complete=True, deals=len(evidence), gap_forks=result['gap_forks'],
        guess_size=result['guess_size'], best_share=result['best_share'], tree=report['tree'])), flush=True)


if __name__ == '__main__':
    main()
