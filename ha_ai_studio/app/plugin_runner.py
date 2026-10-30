"""Minimal stdlib-only process contract, executed by the action's interpreter."""
import asyncio
import contextlib
import importlib.util
import inspect
import json
from pathlib import Path
import sys

def main():
    source=Path(sys.argv[1]).resolve();entry=source/sys.argv[2]
    sys.path.insert(0,str(source))
    raw=sys.stdin.buffer.read(131073)
    if len(raw)>131072:raise ValueError('Runner input too large')
    request=json.loads(raw)
    # Plugin prints must never corrupt the result channel or enter application logs.
    with open('/dev/null','w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        spec=importlib.util.spec_from_file_location('studio_action',entry)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        if not callable(getattr(module,'execute',None)):raise ValueError('Missing execute')
        if request['mode']=='check':response={'ready':True}
        else:
            result=module.execute(request['data'],request['settings'])
            if inspect.isawaitable(result):result=asyncio.run(result)
            response={'data':result}
    sys.stdout.write(json.dumps(response,allow_nan=False))

if __name__=='__main__':
    try:main()
    except BaseException:sys.exit(1)
