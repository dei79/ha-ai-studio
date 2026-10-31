"""Local sources use disposable directories and never connect to MQTT."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from aiohttp.test_utils import TestClient, TestServer
from app.actions import Studio
from app.domain import Invalid
from app.plugins import Repositories, manifest
from app.server import create_app


class LocalActions(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.source=self.root/'local';self.action=self.source/'actions'/'sample';self.action.mkdir(parents=True)
        self.env=patch.dict(os.environ,{'HA_AI_STUDIO_DEV':'1','HA_AI_STUDIO_LOCAL_ACTIONS':str(self.source)})
        self.env.start();self.studio=Studio(self.root/'data')
        self.data={'id':'sample','name':'Local sample','description':'Synthetic fixture','version':'1',
                   'python':f'{sys.version_info.major}.{sys.version_info.minor}','entrypoint':'action.py',
                   'settings_schema':{'type':'object'},'editor':'ui/editor.js'}
        (self.action/'action.json').write_text(json.dumps(self.data));(self.action/'requirements.lock').write_text('')
        (self.action/'action.py').write_text('def execute(data, settings):\n return data\n')
        (self.action/'ui').mkdir();(self.action/'ui/editor.js').write_text("import './fields.js'; export function render(h,s,c){return ()=>s}")
        (self.action/'ui/fields.js').write_text('export const field = 1;')
    async def asyncTearDown(self):
        await self.studio.close();self.env.stop();self.tmp.cleanup()
    async def seed(self):
        result=await self.studio.repositories.save({'kind':'local','path':'.'})
        self.repo_id=result['repositories'][0]['id'];await self.studio.repositories.tasks[self.repo_id]
        self.assertEqual(self.studio.repositories.state['repositories'][0]['status'],'Ready')
        kind=next(iter(self.studio.repositories.types()))
        await self.studio.create({'id':'sample','name':'Sample','type':kind})
        service=self.studio.get('sample');await service.environment.task
        self.assertTrue(service.environment.ready,service.environment.state)
        return service
    async def test_reload_keeps_identity_config_jobs_and_old_source(self):
        service=await self.seed();identity=copy.deepcopy(service.identity);config=copy.deepcopy(service.config)
        old=copy.deepcopy(service.plugin.record);service.config['active']=copy.deepcopy(config['draft'])
        first,_=await service.request('{"request_id":"one","data":false}')
        config=copy.deepcopy(service.config)
        (self.action/'action.py').write_text('def execute(data, settings):\n return {"updated":data}\n')
        self.assertEqual(await service.execute(False,{}),False)
        await self.studio.reload_source('sample');await service.environment.task
        self.assertEqual(await service.execute(0,{}),{'updated':0})
        self.assertEqual(service.identity,identity);self.assertEqual(service.config,config)
        self.assertEqual((await service.request('{"request_id":"one","data":false}'))[0],first)
        self.assertEqual(service.jobs['one']['plugin'],old)
        self.assertTrue((self.studio.repositories.store.root/'sources'/old['snapshot']).is_dir())
        await self.studio.repositories.prune_sources()
        self.assertTrue((self.studio.repositories.store.root/'sources'/old['snapshot']).is_dir())
        restored=Studio(self.root/'data')
        try:
            self.assertTrue(restored.get('sample').environment.ready)
            self.assertEqual(await restored.get('sample').execute([],{}),{'updated':[]})
        finally:await restored.close()
    async def test_reload_guards_invalid_source_and_settings(self):
        s=await self.seed();old=s.plugin.record
        s.config['active']=copy.deepcopy(s.config['draft']);s.config['enabled']=True
        with self.assertRaisesRegex(Invalid,'Deactivate'):await self.studio.reload_source('sample')
        s.config['enabled']=False
        async with s.lock:
            with self.assertRaisesRegex(Invalid,'busy'):await self.studio.reload_source('sample')
        (self.action/'action.json').write_text('{}')
        with self.assertRaisesRegex(Invalid,'refresh failed'):await self.studio.reload_source('sample')
        self.assertEqual(s.plugin.record,old);self.assertTrue(s.environment.ready)
        self.data['settings_schema']={'type':'object','required':['new_setting']}
        (self.action/'action.json').write_text(json.dumps(self.data))
        with self.assertRaisesRegex(Invalid,'Settings'):await self.studio.reload_source('sample')
        self.assertEqual(s.plugin.record,old)
    async def test_local_boundaries_and_excluded_private_files(self):
        for path in ('../secret','/tmp','missing'):
            with self.assertRaises(Invalid):await self.studio.repositories.save({'kind':'local','path':path})
        with patch.dict(os.environ,{'HA_AI_STUDIO_DEV':'0'}):
            other=Repositories(self.root/'other')
            with self.assertRaises(Invalid):await other.save({'kind':'local','path':'.'})
        (self.action/'.env').write_text('secret');(self.action/'.git').mkdir();(self.action/'.git/config').write_text('private')
        s=await self.seed()
        self.assertFalse((s.plugin.source/'.env').exists());self.assertFalse((s.plugin.source/'.git').exists())
        (self.action/'escape').symlink_to(self.root)
        with self.assertRaisesRegex(Invalid,'refresh failed'):await self.studio.reload_source('sample')
    async def test_manifest_editor_validation(self):
        for editor in ('../editor.js','action.py','ui/../../action.py','ui/missing.js'):
            (self.action/'action.json').write_text(json.dumps({**self.data,'editor':editor}))
            with self.assertRaises(Invalid):await manifest(self.action)
    async def test_registry_write_failure_preserves_instance(self):
        s=await self.seed();old=copy.deepcopy(s.plugin.record)
        (self.action/'action.py').write_text('def execute(data, settings):\n return None\n')
        with patch.object(self.studio.store,'write',side_effect=OSError('synthetic failure')):
            with self.assertRaises(OSError):await self.studio.reload_source('sample')
        self.assertEqual(s.plugin.record,old);self.assertTrue(s.environment.ready)
    async def test_asset_allowlist_and_relative_modules(self):
        s=await self.seed()
        app=create_app(self.root/'data',dev=True)
        # Start HTTP only, never the Studio lifecycle or MQTT.
        app.cleanup_ctx.clear()
        server_studio=next(v for v in app.values() if isinstance(v,Studio))
        client=TestClient(TestServer(app));await client.start_server()
        try:
            url='/'+s.plugin.metadata['editor']
            response=await client.get(url);self.assertEqual(response.status,200)
            self.assertIn("./fields.js",await response.text())
            response=await client.get(url.replace('editor.js','fields.js'));self.assertEqual(response.status,200)
            for tail in ('action.py','requirements.lock','ui/.env','ui/missing.js'):
                response=await client.get(url.rsplit('/ui/',1)[0]+'/'+tail);self.assertEqual(response.status,404)
            response=await client.get(url.replace(s.plugin.record['snapshot'],'unknown'));self.assertEqual(response.status,404)
        finally:await client.close();await server_studio.close()
    async def test_actions_root_symlink_is_rejected(self):
        import shutil
        outside=self.root/'outside';outside.mkdir()
        shutil.move(self.source/'actions',outside/'actions')
        (self.source/'actions').symlink_to(outside/'actions',target_is_directory=True)
        result=await self.studio.repositories.save({'kind':'local','path':'.'})
        await self.studio.repositories.tasks[result['repositories'][0]['id']]
        self.assertEqual(self.studio.repositories.state['repositories'][0]['status'],'Failed')
        self.assertFalse(self.studio.repositories.types())
    async def test_refresh_during_reload_keeps_selected_snapshot(self):
        import asyncio
        from app.plugins import GitPlugin
        s=await self.seed();entered=asyncio.Event();release=asyncio.Event();selected=[]
        original=GitPlugin.validate
        async def paused(plugin,value):
            selected.append(plugin.source);entered.set();await release.wait()
            return await original(plugin,value)
        with patch.object(GitPlugin,'validate',paused):
            task=asyncio.create_task(self.studio.reload_source('sample'))
            await asyncio.wait_for(entered.wait(),5)
            self.studio.repositories.refresh(self.repo_id)
            await self.studio.repositories.tasks[self.repo_id]
            self.assertTrue(selected[0].is_dir())
            release.set();await task
        await s.environment.task;self.assertTrue(s.environment.ready,s.environment.state)
    async def test_queue_write_failure_blocks_changed_code_and_recovers(self):
        s=await self.seed();(self.action/'action.py').write_text('def execute(data, settings):\n return 42\n')
        original=s.store.write
        def fail(name,value):
            if name=='environment.json':raise OSError('synthetic failure')
            return original(name,value)
        with patch.object(s.store,'write',fail):
            with self.assertRaises(OSError):await self.studio.reload_source('sample')
        self.assertFalse(s.environment.ready)
        with self.assertRaises(Invalid):await s.execute(None,{})
        restored=Studio(self.root/'data')
        try:
            service=restored.get('sample');self.assertFalse(service.environment.ready)
            service.environment.start();await service.environment.task
            self.assertEqual(await service.execute(None,{}),42)
        finally:await restored.close()
