"""One command for CLI fixtures, spec programs and host lifecycle checks."""
import argparse
import json
from pathlib import Path
import platform
import sys
import time
import unittest

from zzy import __version__
from zzy.resources import ResourcePolicy


def execute(suite, stream=None):
    collected = suite.countTestCases()
    started = time.monotonic()
    result = unittest.TextTestRunner(verbosity=1, stream=stream).run(suite)
    passed = (collected > 0 and result.testsRun == collected and result.wasSuccessful()
              and not result.skipped and not result.expectedFailures)
    return passed, {"collected":collected,"tests_run":result.testsRun,
        "failures":len(result.failures),"errors":len(result.errors),
        "skipped":len(result.skipped),"expected_failures":len(result.expectedFailures),
        "passed":passed,"seconds":round(time.monotonic()-started,3)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args(argv)
    try:
        suite=unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent),top_level_dir=str(Path(__file__).resolve().parents[1]))
        passed,report=execute(suite)
        policy=ResourcePolicy()
        report.update(zzy_version=__version__,python=sys.version,platform=platform.platform(),
                      resource_policy=policy.effective_record(),resource_fingerprint=policy.fingerprint)
        if args.report:args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,separators=(',',':')))
        return 0 if passed else 1
    except KeyboardInterrupt:
        print('Cancelled; suite did not pass',file=sys.stderr)
        return 1
    except (OSError,ValueError,ImportError) as error:
        print(f'Collection/report failed: {error}',file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())
