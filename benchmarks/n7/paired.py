"""Summarize paired relative times for two variants without pooling rounds."""
import argparse
import gzip
import json
from pathlib import Path

from benchmarks.n7.run import stat


def ratios(path, baseline, comparison):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        rows = [json.loads(line) for line in stream]
    records = {}
    for row in rows:
        if row['warmup'] or row['variant'] not in (baseline, comparison):
            continue
        if row['status'] != 'ok':
            raise ValueError('cannot report complete pairs with failed samples')
        key = row['case'], row['scope'], row['sequence']
        pair = records.setdefault(key, {})
        if row['variant'] in pair:
            raise ValueError('duplicate paired sample')
        pair[row['variant']] = (row['stages']['execute_ns'] if key[1] == 'staged' else row['wall_ns'])
    if not records:
        raise ValueError('empty paired sample set')
    groups = {}
    for (case, scope, _), pair in records.items():
        groups.setdefault((case, scope), []).append(pair[comparison] / pair[baseline])
    if any(len(values) != 15 for values in groups.values()):
        raise ValueError('missing paired samples')
    return [dict(case=case, scope=scope, pair_count=len(values),
                 comparison_over_baseline=stat(values)) for (case, scope), values in sorted(groups.items())]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data', type=Path)
    parser.add_argument('baseline')
    parser.add_argument('comparison')
    args = parser.parse_args()
    print(json.dumps(ratios(args.data, args.baseline, args.comparison), indent=2))
