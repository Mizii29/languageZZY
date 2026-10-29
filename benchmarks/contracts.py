"""P10 preparation/generation/normalization measurement; no speedup baseline claim."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
from time import perf_counter_ns

from zzy.contracts import compile_contracts, convert, openapi, route_registry
from zzy.diagnostics import Phase
from zzy.embedding import _Converter
from zzy.interpreter import Interpreter
from zzy.output import Output
from zzy.prepare import prepare
from zzy.resources import ResourceMeter, ResourcePolicy
from zzy.source import SourceLoader


class MeasureRuntime(Interpreter):
    def execute_program(self):
        node=self.program.root
        converter=_Converter(self,node)
        value=converter.from_python(self.payload)
        started=perf_counter_ns()
        normalized=convert(self,self.contract,value,node)
        self.elapsed=perf_counter_ns()-started
        assert converter.to_python(normalized)==self.payload
        if False: yield


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--repeats',type=int,default=30)
    args=parser.parse_args()
    if args.repeats<2:parser.error('at least 2 repetitions required')
    if args.output.exists():parser.error('use a new output path')
    policy=ResourcePolicy({'io_payload_bytes':65536})
    records=[]
    with tempfile.TemporaryDirectory() as directory:
        for count in (4,32,128):
            source='(shape) Input {'+''.join('f'+str(i)+':(String);' for i in range(count))+'}(addnew) handle(r){(return)r;}'
            path=Path(directory)/'app.zzy';path.write_text(source,encoding='utf-8')
            payload={'f'+str(i):'x'*16 for i in range(count)}
            samples={name:[] for name in ('prepare_ns','contract_generation_ns','validation_ns')}
            for _ in range(args.repeats):
                meter=ResourceMeter(policy,Phase.FRONTEND)
                started=perf_counter_ns()
                with SourceLoader(meter) as loader:program=prepare(loader.read(path),meter,loader)
                samples['prepare_ns'].append(perf_counter_ns()-started)
                registry=route_registry(program,[('POST','/api/test','handle')])
                started=perf_counter_ns()
                table=compile_contracts(program,registry,{'POST /api/test':{'request':'Input'}},meter)
                document=openapi(registry,table,meter)
                samples['contract_generation_ns'].append(perf_counter_ns()-started)
                assert len(next(iter(document['components']['schemas'].values()))['required'])==count
                runtime=MeasureRuntime(program,Output(io.StringIO(),io.StringIO(),ResourceMeter(policy,Phase.EXECUTION)),io.StringIO())
                runtime.contract=table['POST','/api/test'].request;runtime.payload=payload
                runtime.run()
                samples['validation_ns'].append(runtime.elapsed)
                assert all(runtime.meter.used(k)==0 for k in ('runtime_slots','runtime_objects','runtime_payload_bytes'))
            records.append({'fields':count,'payload_utf8_bytes':len(json.dumps(payload).encode()),'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
                            'samples':samples,'summary':{key:{'median_ns':statistics.median(values),'min_ns':min(values),'max_ns':max(values),
                                                          'pstdev_ns':statistics.pstdev(values)} for key,values in samples.items()}})
    root=Path(__file__).resolve().parents[1]
    files=['zzy/contracts.py','benchmarks/contracts.py']
    report={'python':sys.version,'platform':platform.platform(),'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
            'source_sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files},
            'resource_policy':policy.effective_record(),'repeats':args.repeats,'records':records,'failures':[],
            'scope':'prepare includes source read/front-end; generation includes IR and OpenAPI encoding on prepared Program; validation includes Map normalization/allocation, excludes JSON parse, business, HTTP and cleanup; no speedup claim'}
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':True,'scales':len(records),'repeats':args.repeats}))


if __name__=='__main__':main()
