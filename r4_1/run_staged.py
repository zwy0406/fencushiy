"""Run only the approved R4-1 matrix, gated after each result."""
import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from analysis import analyze, load_and_check

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SEED = 2025
PY = ['/root/miniconda3/bin/conda', 'run', '-n', 'fc', 'python']


def status(size, state, detail=''):
    path = OUT / f'n{size}_stage.json'
    path.write_text(json.dumps(dict(size=size, state=state, detail=detail,
                                   utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())), indent=2) + '\n')


def run_logged(command, log):
    with log.open('w') as f:
        return subprocess.run(command, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode


def validate(size):
    run = OUT / f'n{size}'
    name = f'r4_1_proposed_n{size}_seed{SEED}'
    snap = run / 'cluster_snapshot_logs' / name
    manifest, times, groups, roles, bb, checks = load_and_check(snap)
    assert manifest['seed'] == SEED and manifest['N_UAV'] == size
    assert manifest['simulation_duration_s'] == 300 and manifest['cluster_interval_us'] == 1e6
    assert manifest['effective_configuration']['routing_protocol'] == 'MWMP_DCA'
    assert manifest['effective_configuration']['data_packet_rate'] == 2.0
    assert manifest['effective_configuration']['communication_range'] == 250.0
    assert manifest['effective_configuration']['mobility_trace_mode'] == 'replay'
    assert manifest['record_error_count'] == 0
    metric = run / 'metrics'
    required = ['packet_outcomes.csv', 'packet_hops.csv', 'cluster_round_timeseries.csv']
    assert all((metric / x).is_file() for x in required)
    with next(metric.glob('*_summary.csv')).open(newline='') as f:
        row = next(csv.DictReader(f))
    assert int(row['seed']) == SEED and int(row['number_of_drones']) == size
    assert row['method'] == 'PROPOSED'
    assert abs(float(row['network_lifetime_s']) - 300.0) <= 1e-5
    assert abs(float(row['energy_accounting_error_j'])) < 1e-5
    assert int(row['datapacket_generated']) >= int(row['datapacket_arrived']) >= 0
    assert int(row['packet_diag_generated']) == int(row['datapacket_generated'])
    assert int(row['packet_diag_delivered']) == int(row['datapacket_arrived'])
    with (metric / 'packet_outcomes.csv').open() as f:
        packet_count = sum(1 for _ in f) - 1
    assert packet_count == int(row['datapacket_generated'])
    assert float(row['packet_diag_max_delay_error_us']) < 1e-6
    checks.update(size=size, packet_count=packet_count,
                  energy_error_j=float(row['energy_accounting_error_j']),
                  network_lifetime_s=float(row['network_lifetime_s']),
                  wall_clock_s=float(row.get('wall_clock_s') or 0) if 'wall_clock_s' in row else 'see log',
                  git_commit=manifest['git_commit'])
    (OUT / f'n{size}_validation.json').write_text(json.dumps(checks, indent=2) + '\n')
    analyze(snap, OUT / f'n{size}_analysis')
    return checks


def main():
    # N60 was started explicitly before this monitor. Wait for its launcher.
    while Path('/proc/717091').exists():
        time.sleep(30)
    try:
        status(60, 'validating')
        validate(60)
        status(60, 'passed')
        for size in (80, 100):
            trace = OUT / 'mobility_traces' / f'seed{SEED}_n{size}_v15.json'
            assert not trace.exists(), f'output exists: {trace}'
            assert not (OUT / f'n{size}').exists(), f'output exists: n{size}'
            (OUT / f'n{size}').mkdir()
            status(size, 'generating_trace')
            cmd = PY + ['-m', 'experiments.generate_mobility_trace', '--seed', str(SEED),
                        '--n-drones', str(size), '--speed', '15', '--sim-time-s', '300',
                        '--output', str(trace)]
            assert run_logged(cmd, OUT / f'n{size}_trace.log') == 0
            assert trace.is_file()
            status(size, 'running')
            name = f'r4_1_proposed_n{size}_seed{SEED}'
            cmd = PY + ['-m', 'experiments.run_experiment', '--method', 'PROPOSED',
                        '--seed', str(SEED), '--n-drones', str(size), '--speed', '15',
                        '--traffic-rate', '2', '--comm-range', '250', '--sim-time-s', '300',
                        '--mobility-trace-mode', 'replay', '--mobility-trace-file', str(trace),
                        '--packet-diagnostics', '--cluster-snapshot-logging',
                        '--output-dir', str(OUT / f'n{size}'), '--experiment-name', name]
            assert run_logged(cmd, OUT / f'n{size}.log') == 0
            status(size, 'validating')
            validate(size)
            status(size, 'passed')
    except Exception as exc:
        size = locals().get('size', 60)
        status(size, 'failed', repr(exc))
        raise


if __name__ == '__main__':
    main()
