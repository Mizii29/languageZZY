"""Run from the repository root: python -m examples.web.embed"""
import json
from pathlib import Path
from zzy.embedding import load_module


def main():
    with load_module(Path(__file__).with_name('app.zzy')) as module:
        result = module.call('greet', {'body': {'name': 'Ada'}})
        print(json.dumps(result.value, ensure_ascii=False))


if __name__ == '__main__':
    main()
