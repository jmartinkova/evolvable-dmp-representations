#!/usr/bin/env python3
"""Calculate benchmark metrics from summary.csv; Python standard library only."""
import argparse
import csv
import math
import re
from collections import defaultdict
from pathlib import Path


def number(row, key):
    value = float(row[key])
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"Invalid {key} for {row.get('file')}: {row[key]}")
    return value


def calculate(rows):
    groups = defaultdict(list)
    seen = set()
    for row in rows:
        if row.get('status') != 'ok':
            raise ValueError(f"Non-ok result: {row.get('file')} ({row.get('status')})")
        file = Path(row['file'])
        match = re.fullmatch(r'(.+)_(\d+)', file.stem)
        if not match:
            raise ValueError(f"Expected filename ending _N: {file.name}")
        n_value = number(row, 'statements')
        if not n_value.is_integer():
            raise ValueError('Statements must be integer')
        n = int(n_value)
        if n != int(match[2]):
            raise ValueError(f"Statement count disagrees with filename: {file.name}")
        records = number(row, 'records')
        size = number(row, 'size_bytes')
        if not records.is_integer() or not size.is_integer():
            raise ValueError('Counts and file sizes must be integers')
        time = number(row, 'median_ms')
        q1, q3 = float(row['q1_ms']), float(row['q3_ms'])
        if not (math.isfinite(q1) and math.isfinite(q3) and 0 <= q1 <= time <= q3):
            raise ValueError(f"Invalid quartiles: {file.name}")
        key = (match[1], file.suffix.lower(), row['jena_version'])
        identity = (*key, n)
        if identity in seen:
            raise ValueError(f"Duplicate result: {identity}")
        seen.add(identity)
        groups[key].append(dict(file=file.name, encoding=key[0], syntax=key[1].lstrip('.'),
            jena_version=key[2], statements=n, records=int(records), size_bytes=int(size),
            inflation=records/n, median_ms=time, q1_ms=q1, q3_ms=q3,
            iqr_ms=q3-q1, median_ms_per_statement=time/n,
            measured_runs=int(number(row, 'measured_runs'))))
    if not groups:
        raise ValueError('No input results')
    output = []
    for key in sorted(groups):
        previous = None
        for item in sorted(groups[key], key=lambda x: x['statements']):
            item.update(previous_statements='', size_ratio='', time_ratio='', scaling_factor='')
            if previous is not None:
                size_ratio = item['statements']/previous['statements']
                time_ratio = item['median_ms']/previous['median_ms']
                item.update(previous_statements=previous['statements'], size_ratio=size_ratio,
                            time_ratio=time_ratio, scaling_factor=time_ratio/size_ratio)
            output.append(item)
            previous = item
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('summary', nargs='?', type=Path, default=Path('summary.csv'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = args.output or args.summary.with_name('metrics.csv')
    if output.resolve() == args.summary.resolve():
        parser.error('Output must differ from input')
    with args.summary.open(encoding='utf-8-sig', newline='') as handle:
        rows = calculate(list(csv.DictReader(handle)))
    with output.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Done: {output} ({len(rows)} rows; "
          f"{sum(x['scaling_factor'] != '' for x in rows)} scaling factors)")


if __name__ == '__main__':
    main()
