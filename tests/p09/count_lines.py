"""Count actual application lines using the language lexer, never comment regexes."""
import argparse
import hashlib
import json
from pathlib import Path
from tests.blackbox import ROOT
from zzy.diagnostics import Phase
from zzy.lexer import Lexer
from zzy.resources import ResourceMeter, ResourcePolicy
from zzy.source import Source


def measure():
    rows=[]
    for path in sorted((ROOT/'apps/zzy-campus').glob('*.zzy')):
        raw=path.read_bytes()
        source=Source.from_bytes(path,raw)
        tokens=Lexer(source,ResourceMeter(ResourcePolicy(),Phase.FRONTEND)).scan()
        live={token.span.start.line for token in tokens if token.kind!='EOF'}
        substantive={token.span.start.line for token in tokens
                     if token.kind!='EOF' and token.lexeme not in {'{','}',';',',','(',')'}}
        rows.append(dict(file=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(raw).hexdigest(),
                         total_lines=len(source.text.splitlines()),effective_lines=len(live),
                         substantive_lines=len(substantive)))
    if not rows: raise ValueError('no application source')
    return dict(rule='physical lines; effective contains non-comment tokens; substantive excludes punctuation-only lines',
                files=rows,total_lines=sum(r['total_lines'] for r in rows),
                effective_lines=sum(r['effective_lines'] for r in rows),
                substantive_lines=sum(r['substantive_lines'] for r in rows))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    result=measure()
    path=ROOT/'apps/zzy-campus/line-count.json'
    if args.check:
        if json.loads(path.read_text(encoding='utf-8'))!=result: raise ValueError('stale line count report')
    else: path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if result['substantive_lines']<200: raise ValueError('fewer than 200 substantive application lines')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},ensure_ascii=False))


if __name__=='__main__': main()
