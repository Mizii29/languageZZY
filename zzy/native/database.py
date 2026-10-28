"""SQLite connections belong to a single synchronous transaction callback."""
import sqlite3
import time
from ..diagnostics import Cancelled
from ..values import Array, Closure, CallRequest
from .json_codec import utf8_size


def invoke(r, name, args, node):
    if name == 'db.transaction':
        path, callback = args
        if getattr(r, '_database', None) is not None:
            r.error(node, 'E401', '不支持嵌套事务')
        if not isinstance(callback.data, Closure) or callback.data.parameters:
            r.error(node, 'E201', '事务需要零参数ZZY函数')
        r.check('io_payload_bytes', utf8_size(r,path.data,node), node)
        connection = None
        with r.reserve(node,runtime_objects=1,runtime_slots=1):
            try:
                connection = sqlite3.connect(path.data,timeout=.25,isolation_level=None)
                connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH,min(1000000000,r.meter.policy.limits['io_payload_bytes']))
                connection.execute('BEGIN IMMEDIATE')
                r._database = connection
                result = (yield CallRequest(callback,[],node))[0]
                if result.kind != 'Result':
                    r.error(node,'E201','事务回调必须返回Result')
                r.meter.cancellation.check()
                connection.set_authorizer(None)
                connection.set_progress_handler(None,0)
                if result.data[0]:connection.commit()
                return result
            except (sqlite3.Error, ValueError):
                r.meter.cancellation.check()
                r.error(node,'E401','SQLite事务失败')
            finally:
                r._database = None
                if connection is not None:
                    connection.set_authorizer(None)
                    connection.set_progress_handler(None,0)
                    try:connection.rollback()
                    finally:connection.close()
    else:
        connection = getattr(r,'_database',None)
        if connection is None:r.error(node,'E401','query需要活动事务')
        sql, params = args
        r.check('io_payload_bytes',utf8_size(r,sql.data,node),node)
        denied={sqlite3.SQLITE_TRANSACTION,sqlite3.SQLITE_SAVEPOINT,sqlite3.SQLITE_ATTACH,
                sqlite3.SQLITE_DETACH,sqlite3.SQLITE_PRAGMA}
        def authorize(action,a,b,*rest):
            return sqlite3.SQLITE_DENY if action in denied or (action==sqlite3.SQLITE_FUNCTION and b=='load_extension') else sqlite3.SQLITE_OK
        deadline=time.monotonic()+1
        def progress():
            try:r.meter.cancellation.check()
            except Cancelled:return 1
            return int(time.monotonic()>deadline)
        from ..embedding import _Converter, ConversionError
        cursor=None
        with r.reserve(node,runtime_slots=len(params.data)):
            values=[]
            for value in params.data:
                r.meter.cancellation.check()
                if value.kind not in {'Null','Int','Float','String'}:r.error(node,'E201','不支持SQLite参数类型')
                if value.kind=='Int' and not -(2**63)<=value.data<2**63:r.error(node,'E208','SQLite Int超出64位')
                if value.kind=='String':r.check('io_payload_bytes',utf8_size(r,value.data,node),node)
                values.append(value.data)
            try:
                connection.set_authorizer(authorize)
                connection.set_progress_handler(progress,1000)
                cursor=connection.execute(sql.data,values)
                result=Array(r,node)
                converter=_Converter(r,node)
                while True:
                    r.meter.cancellation.check()
                    if time.monotonic()>deadline:r.error(node,'E401','SQLite执行超时')
                    row=cursor.fetchone()
                    if row is None:break
                    result.push(converter.from_python(list(row)),r,node)
                return result
            except ConversionError:
                r.error(node,'E201','不支持SQLite结果类型')
            except (sqlite3.Error,UnicodeError,ValueError):
                r.meter.cancellation.check()
                r.error(node,'E401','SQLite查询失败')
            finally:
                if cursor is not None:cursor.close()
                connection.set_authorizer(None)
                connection.set_progress_handler(None,0)
