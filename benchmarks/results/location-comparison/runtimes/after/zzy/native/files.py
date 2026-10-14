"""Bounded UTF-8 file operations; only expected I/O failures become Result."""
import os
import sys
from pathlib import Path
import tempfile

from .json_codec import utf8_size, InvalidJSON
from ..values import NULL


def invoke(runtime, name, args, node):
    path=args[0].data
    temporary=None
    try:
        if name=='io.read_text':
            chunks,owners=[],[]
            size=codepoints=0
            try:
                with open(path,'rb') as stream:
                    while True:
                        runtime.meter.cancellation.check()
                        chunk=stream.read(min(65536,runtime.meter.policy.limits['io_payload_bytes']-size+1))
                        if not chunk:break
                        size+=len(chunk);runtime.check('io_payload_bytes',size,node)
                        codepoints+=sum(b & 0xc0 != 0x80 for b in chunk)
                        runtime.check('text_codepoints',codepoints,node)
                        owners.append(runtime.reserve(node,runtime_payload_bytes=len(chunk)))
                        chunks.append(chunk)
                with runtime.reserve(node,runtime_payload_bytes=size+4*codepoints):
                    text=b''.join(chunks).decode('utf-8',errors='strict')
                    value=runtime.scalar('String',text,node)
                return runtime.result(True,value,node)
            finally:
                for owner in owners:owner.release()
        if name=='io.replace_file':
            # Prepare the success value before the irreversible filesystem change.
            result=runtime.result(True,NULL,node)
            os.replace(path,args[1].data)
            return result
        content=args[1].data
        size=utf8_size(runtime,content,node)
        runtime.check('io_payload_bytes',size,node)
        with runtime.reserve(node,runtime_payload_bytes=size):
            raw=content.encode('utf-8',errors='strict')
            result=runtime.result(True,NULL,node)
            if name=='io.write_atomic':
                target=Path(path)
                descriptor,temporary=tempfile.mkstemp(prefix='.zzy-',suffix='.tmp',dir=target.parent)
                try: stream=os.fdopen(descriptor,'wb')
                except BaseException:
                    os.close(descriptor);raise
                with stream:
                    stream.write(raw)
                runtime.meter.cancellation.check()
                os.replace(temporary,path)
                temporary=None
            else:
                with open(path,'wb') as stream:stream.write(raw)
            return result
    except (OSError,UnicodeError,InvalidJSON,ValueError) as error:
        return runtime.result(False,runtime.scalar('String',f'I/O failed: {error}',node),node)
    finally:
        if temporary is not None:
            pending=sys.exception()
            try:os.unlink(temporary)
            except FileNotFoundError:pass
            except OSError as error:
                # Cleanup failure must not replace cancellation/resource aborts.
                if pending is None:
                    return runtime.result(False,runtime.scalar('String',f'I/O cleanup failed: {error}',node),node)
