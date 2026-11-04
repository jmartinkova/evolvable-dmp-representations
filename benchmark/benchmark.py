#!/usr/bin/env python3
"""Run beside datasets/. Python standard library only; requires a Java JDK."""
from pathlib import Path
import argparse
import csv
import hashlib
import io
import json
import os
import platform
import random
import re
import shutil
import statistics
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
FORMATS = {'.ttl': 'TURTLE', '.ttlstar': 'TURTLE', '.nt': 'NTRIPLES',
           '.trig': 'TRIG', '.nq': 'NQUADS'}

def capture(command):
    r = subprocess.run([str(x) for x in command], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"Command failed: {command}\n{r.stdout}\n{r.stderr}")
    return r.stdout + r.stderr

def find_modern_jena():
    riot = shutil.which('riot')
    if riot:
        home = Path(riot).resolve().parent.parent
        if (home / 'lib').is_dir():
            return home
    brew = shutil.which('brew')
    if brew:
        prefix = Path(capture([brew, '--prefix', 'jena']).strip())
        for home in (prefix / 'libexec', prefix):
            if (home / 'lib').is_dir():
                return home
    return None

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--jena53', type=Path, default=ROOT / 'apache-jena-5.3.0')
    p.add_argument('--jena62', type=Path)
    p.add_argument('--warmups', type=int, default=10)
    p.add_argument('--warmup-seconds', type=float, default=5.0)
    p.add_argument('--measurements', type=int, default=20)
    p.add_argument('--forks', type=int, default=3)
    p.add_argument('--seed', type=int, default=20261020)
    args = p.parse_args()
    if not __import__('math').isfinite(args.warmup_seconds) or args.warmup_seconds < 0 or args.warmups < 0 or min(args.measurements, args.forks) < 1:
        p.error('Invalid iteration counts')
    java, javac = shutil.which('java'), shutil.which('javac')
    if not java or not javac:
        raise SystemExit('Java JDK required (java and javac). On Mac: brew install openjdk')
    modern = args.jena62 or find_modern_jena()
    if modern is None:
        p.error('Cannot locate Jena 6.2.0. Use --jena62 /path/to/apache-jena-6.2.0')
    homes = {'5.3.0': args.jena53.resolve(), '6.2.0': modern.resolve()}
    files = sorted(f for f in (ROOT / 'datasets').iterdir()
                   if f.is_file() and f.suffix.lower() in FORMATS)
    if not files:
        p.error('No supported files in datasets/')
    out = ROOT / ('benchmark-results-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    out.mkdir()
    (out / 'logs').mkdir()
    java_info = capture([java, '-version'])
    metadata = {'utc': datetime.now(timezone.utc).isoformat(),
        'platform': platform.platform(), 'machine': platform.machine(),
        'processor': platform.processor(), 'logical_cpus': os.cpu_count(),
        'python': platform.python_version(), 'java': java_info,
        'javac': capture([javac, '-version']), 'java_executable': java,
        'parameters': vars(args).copy(), 'jena_homes': homes,
        'java_options_environment': {k: os.environ.get(k) for k in
            ('JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS')},
        'warmup_method': 'minimum warmup count AND minimum accumulated timed parsing duration; timings buffered before CSV output',
        'method': 'in-memory streaming parse, fresh parser each iteration; no graph storage',
        'count_method': 'parser triple/quad events in separate untimed validation parse'}
    classpaths = {}
    for version, home in homes.items():
        lib = home / 'lib'
        if not list(lib.glob('*.jar')):
            raise SystemExit(f'No Jena jars: {lib}')
        build = out / ('classes-' + version)
        build.mkdir()
        jars = str(lib / '*')
        capture([javac, '-cp', jars, '-d', build, ROOT / 'ParseBenchmark.java'])
        classpaths[version] = str(build) + os.pathsep + jars
        version_text = capture([java, '-cp', jars, 'riotcmd.riot', '--version'])
        if not re.search(r'\b' + re.escape(version) + r'\b', version_text):
            raise SystemExit(f'Unexpected Jena version at {home}: {version_text}')
        metadata['jena_' + version] = version_text
    tasks = []
    inventory = []
    for file in files:
        match = re.search(r'_(\d+)$', file.stem)
        if not match or int(match[1]) < 1:
            raise SystemExit(f'Expected filename ending _N: {file.name}')
        versions = (['5.3.0'] if file.name.startswith('rdf-star_') else
                    ['6.2.0'] if file.name.startswith('rdf12_') else list(homes))
        inventory.append({'file': file.name, 'bytes': file.stat().st_size,
            'sha256': hashlib.sha256(file.read_bytes()).hexdigest(), 'versions': versions})
        for version in versions:
            for fork in range(1, args.forks + 1):
                tasks.append((file, int(match[1]), version, fork))
    random.Random(args.seed).shuffle(tasks)
    metadata['files'] = inventory
    metadata['task_order'] = [(f.name, v, fork) for f, n, v, fork in tasks]
    (out / 'metadata.json').write_text(json.dumps(metadata, indent=2, default=str))
    rows, errors = [], []
    fields = ['file','syntax','jena_version','fork','phase','iteration','statements',
              'size_bytes','triples','quads','records','records_per_statement','elapsed_ns','parse_ms']
    with (out / 'runs.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for idx, (file, n, version, fork) in enumerate(tasks, 1):
            print(f'[{idx}/{len(tasks)}] {file.name} | Jena {version} | JVM {fork}', flush=True)
            result = subprocess.run([java, '-Xms256m', '-Xmx1g', '-cp', classpaths[version],
                'ParseBenchmark', str(file), FORMATS[file.suffix.lower()],
                str(args.warmups), str(args.measurements), str(args.warmup_seconds)], capture_output=True, text=True)
            log_base = out / 'logs' / f'{file.name}.jena-{version}.fork-{fork}'
            Path(str(log_base) + '.stdout.csv').write_text(result.stdout)
            Path(str(log_base) + '.stderr.log').write_text(result.stderr)
            try:
                if result.returncode:
                    raise RuntimeError(f'Java exit {result.returncode}')
                parsed = list(csv.DictReader(io.StringIO(result.stdout)))
                if (sum(x['phase'] == 'measurement' for x in parsed) != args.measurements
                    or sum(x['phase'] == 'warmup' for x in parsed) < args.warmups):
                    raise ValueError('Unexpected iteration count')
                task_rows = []
                for item in parsed:
                    t, q, ns = int(item['triples']), int(item['quads']), int(item['elapsed_ns'])
                    if item['phase'] not in ('warmup', 'measurement') or ns <= 0:
                        raise ValueError('Invalid timing row')
                    task_rows.append(dict(file=file.name, syntax=FORMATS[file.suffix.lower()],
                        jena_version=version, fork=fork, phase=item['phase'],
                        iteration=int(item['iteration']), statements=n, size_bytes=file.stat().st_size,
                        triples=t, quads=q, records=t+q, records_per_statement=(t+q)/n,
                        elapsed_ns=ns, parse_ms=ns/1e6))
                writer.writerows(task_rows)
                handle.flush()
                rows.extend(task_rows)
            except (ValueError, KeyError, RuntimeError) as exc:
                errors.append({'file': file.name, 'jena_version': version, 'fork': fork, 'error': str(exc)})
                print(f'  ERROR: {exc}; see logs', flush=True)
    groups = {}
    for row in rows:
        if row['phase'] == 'measurement':
            groups.setdefault((row['file'], row['jena_version']), []).append(row)
    summary = []
    for (name, version), group in sorted(groups.items()):
        times = [r['parse_ms'] for r in group]
        q1, _, q3 = statistics.quantiles(times, n=4, method='inclusive') if len(times)>1 else [times[0]]*3
        first = group[0]
        consistent = len({r['records'] for r in group}) == 1
        complete = len(group) == args.forks * args.measurements and consistent
        summary.append(dict(file=name, jena_version=version, statements=first['statements'],
            size_bytes=first['size_bytes'], records=first['records'],
            records_per_statement=first['records_per_statement'], measured_runs=len(times),
            median_ms=statistics.median(times), q1_ms=q1, q3_ms=q3, iqr_ms=q3-q1,
            min_ms=min(times), max_ms=max(times),
            median_ms_per_statement=statistics.median(times)/first['statements'],
            status='ok' if complete else 'incomplete_or_inconsistent'))
    if summary:
        with (out / 'summary.csv').open('w', newline='') as h:
            w=csv.DictWriter(h, fieldnames=list(summary[0])); w.writeheader(); w.writerows(summary)
    (out / 'errors.json').write_text(json.dumps(errors, indent=2))
    print(f'Results: {out}')
    if errors:
        raise SystemExit('Some tasks failed; see errors.json. Do not report incomplete groups.')

if __name__ == '__main__':
    main()
