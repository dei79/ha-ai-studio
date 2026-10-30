import asyncio
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from app.actions import Studio
from app.plugins import Repositories, manifest, process
from app.domain import Invalid

class GitActions(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.studio=Studio(self.root/'data')
        self.fixture=self.root/'fixture';self.fixture.mkdir()
        self.data={'id':'sample','name':'Sample','description':'Synthetic test action','version':'1.0','python':f'{sys.version_info.major}.{sys.version_info.minor}',
            'entrypoint':'action.py','settings_schema':{'type':'object','properties':{'factor':{'type':'integer'}},'additionalProperties':False}}
        (self.fixture/'action.json').write_text(json.dumps(self.data));(self.fixture/'requirements.lock').write_text('')
        (self.fixture/'action.py').write_text('import os\ndef execute(data, settings):\n print("hidden-output")\n assert "DEV_MQTT_PASSWORD" not in os.environ\n assert "SUPERVISOR_TOKEN" not in os.environ\n return data\n')
    async def asyncTearDown(self):
        await self.studio.close();self.tmp.cleanup()
    async def seed(self):
        import shutil
        dest=self.studio.repositories.store.root/'sources'/'snapshot'/'actions'/'sample';dest.parent.mkdir(parents=True);shutil.copytree(self.fixture,dest)
        record={'type':'git-test-sample','repository_id':'test','commit':'a'*40,'snapshot':'snapshot','directory':'actions/sample','manifest':manifest(dest)}
        state={'repositories':[{'id':'test','url':'https://example.invalid/actions.git','ref':'main','status':'Ready','actions':[record],'logs':[]}]}
        self.studio.repositories.store.write('catalog.json',state);self.studio.repositories.state=state
        await self.studio.create({'id':'sample','name':'Sample instance','type':record['type']})
        return self.studio.get('sample')
    async def test_real_environment_json_values_restart_dedup_and_pinning(self):
        with patch.dict(os.environ,{'DEV_MQTT_PASSWORD':'secret','SUPERVISOR_TOKEN':'token'}):
            s=await self.seed();await s.environment.task
            self.assertEqual(s.environment.state['status'],'Ready',s.environment.state)
            for i,data in enumerate([None,False,0,1.5,'text',[],{},[1,{'x':True}]]):
                self.assertEqual(await s.execute(data,{}),data)
            conf=copy.deepcopy(s.config['draft']);conf['settings']={'factor':2}
            s.config['active']=conf
            first,_=await s.request('{"request_id":"one","data":{"x":1}}')
            self.assertEqual(first['status'],'success')
            self.assertEqual(s.jobs['one']['plugin']['commit'],'a'*40)
            with patch.object(s.environment,'execute',side_effect=AssertionError('must not rerun')):
                self.assertEqual((await s.request('{"request_id":"one","data":{"x":1}}'))[0],first)
                conflict,_=await s.request('{"request_id":"one","data":2}')
                self.assertEqual(conflict['error']['code'],'request_id_conflict')
            # Refresh of a catalog must not change a previously created instance.
            self.studio.repositories.state['repositories'][0]['actions'][0]['commit']='b'*40
            self.assertEqual(s.plugin.record['commit'],'a'*40)
            restored=Studio(self.root/'data')
            self.assertTrue(restored.get('sample').environment.ready)
            self.assertEqual(await restored.get('sample').execute(False,{}),False)
            await restored.close()
    async def test_activation_preview_and_rebuild_guards(self):
        s=await self.seed()
        with self.assertRaises(Invalid):s.environment.require()
        with self.assertRaises(Invalid):await s.save(s.config['draft'],True)
        with self.assertRaises(Invalid):await s.test(s.config['draft'],'{}')
        self.assertFalse(s.jobs);await s.environment.task
        s.environment.set('Installing','Synthetic interrupted install')
        restored=Studio(self.root/'data');self.assertEqual(restored.get('sample').environment.state['status'],'Failed');await restored.close()
    async def test_install_failure_and_recovery(self):
        (self.fixture/'requirements.lock').write_text('unlocked-package\n')
        s=await self.seed();await s.environment.task
        self.assertEqual(s.environment.state['status'],'Failed')
        with self.assertRaises(Invalid):await s.execute({}, {})
        (s.plugin.source/'requirements.lock').write_text('');s.environment.start();await s.environment.task
        self.assertTrue(s.environment.ready)
        (s.environment.path/'bin/python').unlink()
        restored=Studio(self.root/'data');self.assertEqual(restored.get('sample').environment.state['status'],'Failed');await restored.close()
    async def test_timeout_and_output_limit(self):
        with self.assertRaises(asyncio.TimeoutError):await process([sys.executable,'-c','import time;time.sleep(30)'],timeout=.05)
        with self.assertRaises(Invalid):await process([sys.executable,'-c','print("x"*70000)'],capture=True)
    async def test_manifest_rejects_external_references_and_path_escape(self):
        for change in [{'entrypoint':'../action.py'},{'settings_schema':{'type':'object','$ref':'https://example.invalid/schema'}},{'python':'0.0'},{'id':'../../x'}]:
            (self.fixture/'action.json').write_text(json.dumps({**self.data,**change}))
            with self.assertRaises(Invalid):manifest(self.fixture)
    async def test_sources_validate_and_refresh_failures_preserve_catalog(self):
        for url in ['file:///tmp/repo','http://example.com/repo','https://user:secret@example.com/repo','ssh://example.com/repo']:
            with self.assertRaises(Invalid):await self.studio.repositories.save({'url':url,'ref':'main'})
        s=await self.seed()
        with patch('app.plugins.process',side_effect=RuntimeError('private-secret')):
            await self.studio.repositories.sync('test')
        public=self.studio.repositories.public();self.assertEqual(public['repositories'][0]['status'],'Failed')
        self.assertEqual(len(self.studio.repositories.types()),1);self.assertNotIn('private-secret',json.dumps(public))
        await s.environment.task

    async def test_real_git_catalog_multiple_actions_no_import_and_duplicate_ids(self):
        import shutil
        repo=self.root/'git-fixture';repo.mkdir()
        for name in ('first','second'):
            dest=repo/'actions'/name;dest.parent.mkdir(exist_ok=True);shutil.copytree(self.fixture,dest)
            data={**self.data,'id':name};(dest/'action.json').write_text(json.dumps(data))
            (dest/'action.py').write_text('raise RuntimeError("catalog must not import code")')
        await process(['git','init','--quiet',repo])
        await process(['git','-C',repo,'add','.'])
        async def commit():
            await process(['git','-C',repo,'-c','user.name=Synthetic','-c','user.email=synthetic@example.invalid','commit','--quiet','-am','Synthetic fixture'])
        await commit()
        real_process=process
        async def redirect_fetch(args,**kwargs):
            args=list(args)
            if 'fetch' in args:
                args[args.index('protocol.file.allow=never')]='protocol.file.allow=always'
                args[-2]=str(repo)
            return await real_process(args,**kwargs)
        with patch('app.plugins.process',side_effect=redirect_fetch):
            result=await self.studio.repositories.save({'url':'https://example.invalid/actions.git','ref':'HEAD'})
            ident=result['repositories'][0]['id'];await self.studio.repositories.tasks[ident]
            current=self.studio.repositories.public()['repositories'][0]
            self.assertEqual(current['status'],'Ready',current)
            self.assertEqual(len(current['actions']),2)
            before=copy.deepcopy(current['actions'])
            (repo/'actions'/'second'/'action.json').write_text(json.dumps({**self.data,'id':'first'}))
            await commit();self.studio.repositories.refresh(ident);await self.studio.repositories.tasks[ident]
            current=self.studio.repositories.public()['repositories'][0]
            self.assertEqual(current['status'],'Failed');self.assertEqual(current['actions'],before)

    async def test_hashed_dependency_wheel_install_and_wrong_hash(self):
        import functools
        import hashlib
        import http.server
        import threading
        import zipfile
        index=self.root/'index';package=index/'simple'/'synthetic-dependency';package.mkdir(parents=True)
        wheel=package/'synthetic_dependency-1.0-py3-none-any.whl'
        with zipfile.ZipFile(wheel,'w') as archive:
            archive.writestr('synthetic_dependency.py','VALUE = 42\n')
            archive.writestr('synthetic_dependency-1.0.dist-info/METADATA','Metadata-Version: 2.1\nName: synthetic-dependency\nVersion: 1.0\n')
            archive.writestr('synthetic_dependency-1.0.dist-info/WHEEL','Wheel-Version: 1.0\nGenerator: synthetic-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
            archive.writestr('synthetic_dependency-1.0.dist-info/RECORD','')
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self,*args):pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(index)))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        sha=hashlib.sha256(wheel.read_bytes()).hexdigest()
        (self.fixture/'requirements.lock').write_text(f'synthetic-dependency==1.0 --hash=sha256:{sha}\n')
        (self.fixture/'action.py').write_text('from synthetic_dependency import VALUE\ndef execute(data, settings):\n return VALUE\n')
        real_process=process
        async def test_index(args,**kwargs):
            args=list(args)
            if 'pip' in args and 'install' in args:args+=['--index-url',f'http://127.0.0.1:{server.server_port}/simple/','--no-cache-dir']
            return await real_process(args,**kwargs)
        try:
            with patch('app.plugins.process',side_effect=test_index):
                s=await self.seed();await s.environment.task
                self.assertTrue(s.environment.ready,s.environment.state)
                self.assertEqual(await s.execute(None,{}),42)
                (s.plugin.source/'requirements.lock').write_text('synthetic-dependency==1.0 --hash=sha256:'+'0'*64+'\n')
                s.environment.start();await s.environment.task
                self.assertEqual(s.environment.state['status'],'Failed')
        finally:
            await asyncio.to_thread(server.shutdown);server.server_close();thread.join()

    async def test_ready_persistence_failure_prevents_execution(self):
        s=await self.seed();await s.environment.task
        original=s.environment.store.write
        def fail_ready(name,value):
            if name=='environment.json' and value['status']=='Ready':raise OSError('synthetic disk full')
            return original(name,value)
        with patch.object(s.environment.store,'write',side_effect=fail_ready):
            s.environment.start();await s.environment.task
        self.assertEqual(s.environment.state['status'],'Failed')
        with self.assertRaises(Invalid):await s.execute(None,{})
        self.assertNotIn('synthetic disk full',json.dumps(s.status()))

    async def test_output_schema_and_interrupted_job_never_rerun(self):
        self.data['output_schema']={'type':'integer'}
        (self.fixture/'action.json').write_text(json.dumps(self.data))
        s=await self.seed();await s.environment.task;s.config['active']=copy.deepcopy(s.config['draft'])
        result,_=await s.request('{"request_id":"bad-output","data":{}}')
        self.assertEqual(result['error']['code'],'execution_failed')
        from app.actions import digest
        body={'request_id':'interrupted','data':42}
        s.jobs['interrupted']={'digest':digest(body),'config':s.config['active'],'execution':'processing','delivery':'not_sent','result':None,'plugin':s.plugin.record}
        s.store.write('action-jobs.json',s.jobs)
        restored=Studio(self.root/'data');service=restored.get('sample')
        with patch.object(service.environment,'execute',side_effect=AssertionError('must not rerun')):
            result,_=await service.request(json.dumps(body))
        self.assertEqual(result['error']['code'],'interrupted');await restored.close()
