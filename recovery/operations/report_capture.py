"""Derive this stream's first capture report without changing frozen play data."""
import fcntl
import json
import os
from pathlib import Path
import sys
import time

BASE = Path(__file__).resolve().parent
CONFIG = json.loads((BASE / 'stream.json').read_text())
RUN = Path(CONFIG['run'])
RUNTIME = Path(CONFIG['runtime'])
sys.path.insert(0, str(RUNTIME))
from bridge_harness.loop_registry import sha
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from ops.report_gen7_capture import report


def main():
    with (RUN / '.capture-report.lock').open('a+') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        m = json.loads((RUN / 'manifest.json').read_text())
        verify_generation(RUN, m)
        manifest_hash = sha(RUN / 'manifest.json')
        assert m['pair_weights'] == {'6-32~6-32': 1}
        atomic_json(RUN / 'capture-report-process.json', dict(pid=os.getpid(), epoch=time.time()))
        paths = sorted((RUN / 'receipts').glob('*.json'))
        originals = [(p, sha(p), json.loads(p.read_text())) for p in paths]
        for p, checksum, receipt in originals:
            assert receipt['manifest_identity'] == m['identity']
        # There is no pre-capture cohort for this independently launched stream.
        # The frozen kernel accepts a path for that cohort; this absent path yields
        # no observations. Replace that placeholder with explicit null metadata below.
        absent_baseline = BASE / 'no-pre-capture-cohort-available'
        assert not absent_baseline.exists()
        result = report(RUN, absent_baseline, threshold=2000, force=False)
        if result['status'] != 'completed':
            print(json.dumps(result), flush=True)
            return
        assert result['root_tables'] == 2000
        assert result['gap_forks'] == sum(b['forks'] for b in result['bands'].values())
        assert result['residual_within_table_correlation']['forks'] == result['gap_forks']
        assert result['gap_forks_per_root'] == result['gap_forks'] / 2000
        assert abs(result['added_cpu_share'] - result['gap_cpu'] / result['root_cpu']) < 1e-12
        inputs = []
        scanned = result['episodes_scanned']
        assert scanned <= len(originals)
        for path, checksum, receipt in originals[:scanned]:
            assert sha(path) == checksum, 'A receipt changed during read-only analysis'
            episode = RUN / 'episodes' / f"{receipt['index']:06d}.json.gz"
            assert sha(episode) == receipt['episode_sha256']
            inputs.append(dict(index=receipt['index'], family=receipt['family'],
                               receipt_sha256=checksum, episode_sha256=receipt['episode_sha256']))
        assert len({x['family'] for x in inputs}) == len(inputs)
        assert sha(RUN / 'manifest.json') == manifest_hash
        verify_generation(RUN, m)
        atomic_json(RUN / 'gen7-capture-inputs.json', dict(manifest=m['identity'],
            selection='Frozen corpus index order; first 2000 eligible non-passed-out root tables',
            inputs=inputs))
        result.update(rate_before=None,
            rate_comparison=dict(available=False,
                reason='This stream began with capture enabled; no matching pre-capture cohort exists. '
                       'The observed after rate cannot establish a capture-induced throughput change.'),
            uncertainty='Means and standard errors cluster by deal family. Descriptive first-window '
                        'capture diagnostics, not an independent strength estimate. '
                        'No matched before/after rate comparison is available.',
            provenance=dict(manifest=m['identity'], manifest_file_sha256=manifest_hash,
                runtime_source_sha256=m['source_sha256'], kernel_sha256=sha(RUNTIME / 'ops/report_gen7_capture.py'),
                driver_sha256=sha(Path(__file__)), inputs_sha256=sha(RUN / 'gen7-capture-inputs.json'),
                actor_identities={k: s['identity'] for k, s in m['bots'].items()},
                source_feed_branch=CONFIG['branch'], source_input_receipts=scanned,
                episodes_and_receipts_unchanged=True, frozen_generation_verified=True))
        result['rate_after']['method'] = ('Completion-span rate for this all-fast self-play stream, '
            'including cache drains and process initialization; not active-compute-only throughput')
        atomic_json(RUN / 'gen7-capture-report.json', result)
        print(json.dumps(dict(status=result['status'], root_tables=result['root_tables'],
            episodes_scanned=scanned, gap_forks=result['gap_forks'],
            gap_forks_per_root=result['gap_forks_per_root'], added_cpu_share=result['added_cpu_share'],
            residual_icc=result['residual_within_table_correlation']['icc'],
            observed_deals_per_hour=result['rate_after']['deals_per_hour'],
            before_rate_available=False, report_sha256=sha(RUN / 'gen7-capture-report.json'))), flush=True)


if __name__ == '__main__':
    main()
