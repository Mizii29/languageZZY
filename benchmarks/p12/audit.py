"""Reject missing, over-budget or mismatched X00-X03 benchmark samples."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from benchmarks.p12.run import SIZES, SAMPLES, TIMEOUT_SECONDS


def read_rows(folder):
    return [json.loads(line) for line in (folder/'raw.jsonl').read_text(encoding='utf-8').splitlines()]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(cli, stages):
    cli_rows, stage_rows = read_rows(cli), read_rows(stages)
    require(len(cli_rows) == len(stage_rows) == 286, 'record count')
    for kind, folder, rows in [('cli', cli, cli_rows), ('stages', stages, stage_rows)]:
        require(all(row['order'] == i for i, row in enumerate(rows)), f'{kind}: order')
        require(all(row['status'] == 'ok' for row in rows), f'{kind}: failed row')
        for case, sizes in SIZES.items():
            for n in sizes:
                for language in ('zzy', 'python'):
                    suffix = 'zzy' if language == 'zzy' else 'py'
                    path = folder/'inputs'/f'{case}-{n}.{suffix}'
                    digest = sha256(path.read_bytes()).hexdigest()
                    selected = [row for row in rows if row['case'] == case and row['n'] == n
                                and row['language'] == language and row['phase'] == 'sample']
                    require(len(selected) == SAMPLES, f'{kind}/{case}/{n}/{language}: samples')
                    require({row['index'] for row in selected} == set(range(SAMPLES)), 'sample indices')
                    for row in selected:
                        elapsed = row['elapsed_ns'] if kind == 'cli' else row['parent_elapsed_ns']
                        require(0 < elapsed <= TIMEOUT_SECONDS*1_000_000_000, 'wall budget')
                        if kind == 'stages':
                            require(row['source_sha256'] == digest, 'stage source hash')
                            require(row['batch'] > 0 and row['timings']['execute_ns'] > 0, 'stage timing')
                    other = stages if kind == 'cli' else cli
                    require(digest == sha256((other/'inputs'/path.name).read_bytes()).hexdigest(), 'paired source')
        report = json.loads((folder/'summary.json').read_text(encoding='utf-8'))
        require(report['total_records'] == len(rows) and not report['failures'], 'summary status')
        require(all(item['valid'] == SAMPLES for item in report['statistics']), 'summary samples')
    return dict(cli_records=len(cli_rows), stage_records=len(stage_rows),
                formal_per_runtime_case=SAMPLES, result='ok')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', type=Path, required=True)
    parser.add_argument('--stages', type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(audit(args.cli, args.stages)))


if __name__ == '__main__':
    main()
