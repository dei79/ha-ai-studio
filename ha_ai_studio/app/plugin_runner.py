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
        # Bind the exact positional call without executing action code.
        capabilities=request.get('capabilities',[])
        kwargs={'context':{}} if capabilities else {}
        inspect.signature(module.execute).bind(None,{},**kwargs)
        if 'preview' in capabilities:
            inspect.signature(module.preview).bind(None,{},context={})
        if request['mode']=='check':response={'ready':True}
        else:
            handler=module.preview if request['mode']=='preview' else module.execute
            if request['mode'] in ('execute','camera_test','reference_capture') and 'home_assistant' in request.get('context',{}):
                # Load Studio's own client, never a similarly named repository module.
                client_spec=importlib.util.spec_from_file_location('studio_ha_client',Path(__file__).with_name('ha_action_client.py'))
                client=importlib.util.module_from_spec(client_spec);client_spec.loader.exec_module(client)
                request['context']['home_assistant']=client.HomeAssistantClient(request['context']['home_assistant'])
            kwargs={'context':request['context']} if 'context' in request else {}
            result=handler(request['data'],request['settings'],**kwargs)
            if inspect.isawaitable(result):result=asyncio.run(result)
            response={'data':result}
    sys.stdout.write(json.dumps(response,allow_nan=False))

if __name__=='__main__':
    try:main()
    except BaseException:sys.exit(1)
