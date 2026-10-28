"""Explicit service-owned module snapshots; no global cache or runtime fallback."""
import io
from types import MappingProxyType
from .interpreter import Interpreter
from .output import Output
from .resources import ResourceMeter
from .diagnostics import Phase
from .values import Binding, Cell, Closure, Value


class Snapshot:
    def __init__(self, bindings, modules, natives, owners, meter):
        self.bindings = MappingProxyType(bindings)
        self.modules = MappingProxyType(modules)
        self.natives = MappingProxyType(natives)
        self.owners, self.meter = owners, meter
        self.closed = False

    def attach(self, runtime):
        if self.closed:
            raise RuntimeError('shared module is closed')
        runtime.slots.append(runtime.reserve(runtime.program.root, runtime_slots=len(self.bindings)+len(self.modules)))
        runtime.bindings.update({key: Binding(value, False, annotation) for key,(value,annotation) in self.bindings.items()})
        runtime.modules.update(self.modules)
        for key,(name,members) in self.natives.items():
            value = Value('Namespace',dict(members),runtime.reserve(runtime.program.root,runtime_objects=1,runtime_slots=len(members)+1))
            value.namespace = name
            runtime.bindings[key] = Binding(value,False)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.bindings = MappingProxyType({})
        self.modules = MappingProxyType({})
        self.natives = MappingProxyType({})
        for owner in self.owners:
            owner.release()
        self.owners.clear()


class Initializer(Interpreter):
    def execute_program(self):
        yield from super().execute_program()
        node = self.program.root
        pending, seen, frozen = [], set(), []
        bindings, natives = {}, {}
        for key,binding in self.bindings.items():
            if isinstance(key,str):
                if binding.value.kind == 'Namespace':
                    value = binding.value
                    natives[key] = (value.namespace,MappingProxyType(dict(value.data)))
                    pending.extend((member,0) for member in value.data.values())
                continue  # Preserve nominal identities, clone cache dictionaries per request.
            if binding.mutable or isinstance(binding,Cell):
                self.error(node,'E303','共享模块拒绝可变绑定')
            bindings[key] = (binding.value,binding.annotation)
            pending.extend(((binding.value,0),(binding.annotation,0)))
        while pending:
            self.meter.cancellation.check()
            item,depth = pending.pop()
            if item is None or isinstance(item,str) or id(item) in seen:
                continue
            seen.add(id(item))
            self.check('value_depth',depth+1,node)
            if isinstance(item,Cell) or not isinstance(item,Value):
                self.error(node,'E303','共享闭包拒绝可变捕获')
            kind,data = item.kind,item.data
            if kind in {'Lazy','Namespace','NativeType'} or getattr(item,'native_type',None) is not None:
                self.error(node,'E303','共享模块不支持 '+kind)
            children = ()
            if kind in {'Map','Module'}:
                children = data.values()
            elif kind in {'Array','Range','Machine'}:
                children = data
            elif kind == 'Shape':
                children = (data[0],*data[1].values())
            elif kind == 'Definition':
                children = data[1].values()  # Default AST references all validated globals.
            elif kind == 'Function' and isinstance(data,Closure):
                children = (*data.captures,*data.parameter_types,data.return_type)
            elif kind == 'Result':
                children = (data[1],)
            elif kind not in {'Function','MachineDefinition','Null','Bool','Int','Float','String','Quantity'}:
                self.error(node,'E303','共享模块不支持 '+kind)
            if kind in {'Array','Map','Shape','Machine'}:
                frozen.append(item)
            pending.extend((child,depth+1) for child in children)
        # Publish only after complete validation; transfer logical reservations.
        for item in frozen:
            item.frozen = True
        owners = list(self.reservations)
        self.snapshot = Snapshot(bindings,dict(self.modules),natives,owners,self.meter)
        self.reservations.clear()
        self.slots.clear()


def initialize(program, policy, token):
    output = Output(io.StringIO(),io.StringIO(),ResourceMeter(policy,Phase.EXECUTION,token))
    runtime = Initializer(program,output,io.StringIO())
    runtime.run()
    return runtime.snapshot
