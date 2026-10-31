"""Run liveness probes under an external watchdog, including on regressions."""
import asyncio
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from aiohttp.test_utils import TestClient, TestServer
from app.actions import Studio
from app.domain import Invalid
from app.plugins import CommandProtocol, Environment, manifest, schema_valid
from app.server import create_app

BAD = 'a' * 32 + '!'
SCHEMA = {'type': 'string', 'pattern': '^(a+)+$'}


async def probe():
    with tempfile.TemporaryDirectory() as root:
        app = create_app(root, dev=True)
        # No startup discovery, repository fetch, subscriptions or real brokers.
        app.cleanup_ctx.clear()
        studio = next(value for value in app.values() if isinstance(value, Studio))
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            source = Path(root) / 'fixture'
            source.mkdir()
            data = {'id':'sample','name':'Sample','description':'Synthetic','version':'1',
                    'python':f'{sys.version_info.major}.{sys.version_info.minor}',
                    'entrypoint':'action.py','settings_schema':{'type':'object'}}
            (source/'action.py').write_text('def execute(data, settings): return data\n')
            (source/'requirements.lock').write_text('')
            (source/'action.json').write_text(json.dumps(data))
            record = {'type':'git-test-sample','repository_id':'test','commit':'synthetic',
                      'snapshot':'synthetic','directory':'actions/sample','manifest':await manifest(source)}
            studio.repositories.state = {'repositories':[{'id':'test','actions':[record]}]}
            with patch.object(Environment, 'start'):
                await studio.create({'id':'sample','name':'Sample','type':record['type']})
            service = studio.get('sample')
            service.config['active'] = copy.deepcopy(service.config['draft'])

            async def responsive(task):
                await asyncio.sleep(.1)
                assert not task.done(), 'Probe must overlap ongoing validation'
                for _ in range(3):
                    response = await asyncio.wait_for(client.get('/api/actions'), .5)
                    assert response.status == 200
                    await response.read()
                    response = await asyncio.wait_for(client.get('/'), .5)
                    assert response.status == 200
                    await response.read()
                return await asyncio.wait_for(task, 5)

            # Settings through the actual HTTP save route, preserving the draft.
            service.plugin.manifest['settings_schema'] = {'type':'object','properties':{'text':SCHEMA}}
            draft = copy.deepcopy(service.config['draft'])
            draft['settings'] = {'text':BAD}
            task = asyncio.create_task(client.post('/api/action?id=sample',
                json={'config':draft,'activate':False},headers={'X-HA-AI-Studio-Request':'1'}))
            response = await responsive(task)
            assert response.status == 400
            assert 'resource limits' in (await response.json())['error']
            assert service.config['draft']['settings'] == {}
            service.plugin.manifest['settings_schema'] = {'type':'object'}
            await service.save(service.config['draft'],False)

            # MQTT request parsing must fail without executing or persisting a job.
            service.plugin.manifest['input_schema'] = SCHEMA
            task = asyncio.create_task(service.request(json.dumps({'request_id':'bad','data':BAD})))
            result,_ = await responsive(task)
            assert result['error']['code'] == 'invalid_request'
            assert 'bad' not in service.jobs
            service.plugin.manifest['input_schema'] = {}

            # Runner output is validated after the runner exits, still in isolation.
            service.plugin.manifest['output_schema'] = SCHEMA
            with patch.object(Environment,'require'), patch('app.plugins.process', return_value=json.dumps({'data':BAD}).encode()) as mocked:
                # Mock only runner execution; keep the real schema worker process.
                from app import plugins
                original = real_process
                async def dispatch(args, **kwargs):
                    if Path(args[2]) == plugins.SCHEMA_WORKER:
                        return await original(args, **kwargs)
                    return json.dumps({'data':BAD}).encode()
                mocked.side_effect = dispatch
                task = asyncio.create_task(service.execute(None,{}))
                try:
                    await responsive(task)
                    raise AssertionError('Output validation must fail')
                except Invalid:
                    pass
            service.plugin.manifest['output_schema'] = {}

            # Manifest examples and schema checks also run outside the event loop.
            (source/'action.json').write_text(json.dumps({**data,'input_schema':SCHEMA,
                'example':{'request_id':'example','data':BAD}}))
            task = asyncio.create_task(manifest(source))
            try:
                await responsive(task)
                raise AssertionError('Example validation must fail')
            except Invalid:
                pass
            assert await schema_valid({'type':'integer'},42)
            assert not await schema_valid({'type':'integer'},'wrong')
            assert not await schema_valid({'$ref':'https://example.invalid/private'},42)
            assert not await schema_valid({'type':'unknown'},check=True)
            for value in [None,False,0,1.5,'text',[],{}]:
                assert await schema_valid({},value)

            # Reading saved examples never evaluates their schema on the server.
            record['manifest'].update(input_schema=SCHEMA, example={'request_id':'stored','data':BAD})
            response = await asyncio.wait_for(client.get('/api/actions'),.5)
            assert response.status == 200
            await response.read()

            # At most two workers; cancellation must kill/reap both and free slots.
            pids = []
            connected = CommandProtocol.connection_made
            def track(protocol, transport):
                pids.append(transport.get_pid())
                connected(protocol, transport)
            with patch.object(CommandProtocol,'connection_made',track):
                tasks = [asyncio.create_task(schema_valid(SCHEMA,BAD)) for _ in range(4)]
                try:
                    for _ in range(100):
                        if len(pids) == 2:break
                        await asyncio.sleep(.01)
                    assert len(pids) == 2
                    await asyncio.sleep(.1)
                    assert len(pids) == 2
                finally:
                    for task in tasks:task.cancel()
                    await asyncio.gather(*tasks,return_exceptions=True)
            for pid in pids:
                try:os.kill(pid,0)
                except ProcessLookupError:pass
                else:raise AssertionError('Cancelled schema worker is still alive')
            assert await schema_valid({},None)

            # A shorter wall deadline must fail closed independently of the CPU limit.
            with patch('app.plugins.SCHEMA_TIMEOUT',.1):
                try:
                    await schema_valid(SCHEMA,BAD)
                    raise AssertionError('Wall deadline must fail closed')
                except Invalid:
                    pass
        finally:
            await client.close()
            await studio.close()


from app.plugins import process as real_process


class SchemaIsolation(unittest.TestCase):
    def test_studio_remains_reachable_and_workers_are_bounded_and_reaped(self):
        result = subprocess.run([sys.executable,__file__,'--probe'],
                                capture_output=True,text=True,timeout=45,
                                env={**os.environ,'PYTHONPATH':str(Path(sys.modules['app'].__file__).resolve().parent.parent) } )
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__ == '__main__' and '--probe' in sys.argv:
    asyncio.run(probe())
