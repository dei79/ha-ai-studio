"""Synthetic release packages; no GitHub, MQTT or production state access."""
import copy
import hashlib
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from app.actions import Studio
from app.domain import Invalid
from app.releases import ASSET, fetch_release, unpack, repository_url, download


def package(version='1'):
    manifest = {'id':'sample','name':'Sample','description':'Synthetic','version':version,
                'python':f'{sys.version_info.major}.{sys.version_info.minor}',
                'entrypoint':'action.py','settings_schema':{'type':'object'},'editor':'ui/editor.js'}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:
        for name, value in {'action.json':json.dumps(manifest),'action.py':f'def execute(data, settings):\n return {version!r}\n',
                            'requirements.lock':'','ui/editor.js':"import './fields.js'; export function render(h,s){return ()=>s}",
                            'ui/fields.js':'export const version = 1;'}.items():
            archive.writestr('actions/sample/'+name,value)
    return stream.getvalue()


class Releases(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.studio=Studio(self.root/'data');self.version='1';self.bad=False;self.prerelease=False
        self.urls=[]
        async def fake_download(session,url,limit):
            self.urls.append(url)
            data=package(self.version)
            if url.endswith('.sha256'):
                return ((('0'*64) if self.bad else hashlib.sha256(data).hexdigest())+'  '+ASSET+'\n').encode()
            if url.endswith('.zip'):return data
            return json.dumps({'id':int(self.version),'tag_name':'v'+self.version,'draft':False,'prerelease':self.prerelease,
                'assets':[{'name':name,'state':'uploaded','browser_download_url':'https://github.com/test/repo/releases/download/v'+self.version+'/'+name}
                          for name in (ASSET,ASSET+'.sha256')]}).encode()
        self.mock=patch('app.releases.download',side_effect=fake_download);self.mock.start()
    async def asyncTearDown(self):
        self.mock.stop();await self.studio.close();self.tmp.cleanup()
    async def seed(self):
        repos=self.studio.repositories
        result=await repos.save({'kind':'release','url':'https://github.com/test/repo.git','ref':'latest'})
        self.ident=result['repositories'][0]['id'];await repos.tasks[self.ident]
        self.assertEqual(repos.state['repositories'][0]['status'],'Ready')
        return repos
    async def test_refresh_and_restart_keep_existing_instance_pinned(self):
        repos=await self.seed()
        kind=next(iter(repos.types()))
        await self.studio.create({'id':'sample','name':'Sample','type':kind})
        service=self.studio.get('sample');await service.environment.task
        self.assertTrue(service.environment.ready)
        old=copy.deepcopy(service.plugin.record)
        self.version='2';repos.refresh(self.ident);await repos.tasks[self.ident]
        self.assertEqual(repos.state['repositories'][0]['release']['tag'],'v2')
        self.assertEqual(service.plugin.record,old)
        self.assertEqual(await service.execute({},{}),'1')
        self.assertTrue(service.plugin.source.is_dir())
        restored=Studio(self.root/'data')
        try:
            self.assertEqual(restored.get('sample').plugin.record,old)
            self.assertEqual(await restored.get('sample').execute({},{}),'1')
            self.assertEqual(next(iter(restored.repositories.types().values())).manifest['version'],'2')
        finally:await restored.close()
        self.assertTrue(any(u.endswith('/releases/latest') for u in self.urls))
    async def test_failed_refresh_preserves_catalog(self):
        repos=await self.seed();old=copy.deepcopy(repos.state['repositories'][0]['actions'])
        for bad,pre in ((True,False),(False,True)):
            self.bad=bad;self.prerelease=pre
            repos.refresh(self.ident);await repos.tasks[self.ident]
            self.assertEqual(repos.state['repositories'][0]['status'],'Failed')
            self.assertEqual(repos.state['repositories'][0]['actions'],old)
    async def test_explicit_tag_and_mismatch(self):
        target=self.root/'out';target.mkdir()
        result=await fetch_release('https://github.com/test/repo','v1',target)
        self.assertEqual(result['tag'],'v1')
        self.assertTrue(any(u.endswith('/releases/tags/v1') for u in self.urls))
        with self.assertRaises(Invalid):await fetch_release('https://github.com/test/repo','v2',target)
    async def test_url_and_duplicate_validation(self):
        await self.seed()
        with self.assertRaises(Invalid):await self.studio.repositories.save({'kind':'release','url':'https://github.com/test/repo','ref':'latest'})
        for url in ('http://github.com/a/b','https://user:secret@github.com/a/b','https://example.com/a/b','https://github.com/a/../b','https://github.com/a/b?token=secret'):
            with self.assertRaises(Invalid):repository_url(url)
        with self.assertRaises(Invalid):await download(None,'http://localhost/secret',100)


class Archives(unittest.TestCase):
    def test_unsafe_archives(self):
        for name, mode, data in [('../escape',0,'x'),('/actions/a/file',0,'x'),('actions/a/../escape',0,'x'),
                ('actions/a/.env',0,'secret'),('actions/a/link',stat.S_IFLNK|0o777,'/tmp'),
                ('actions/a/large',0,'x'*(5*1024*1024+1)),('actions\\a\\x',0,'x')]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                stream=io.BytesIO()
                with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
                    info=zipfile.ZipInfo(name);info.external_attr=mode<<16;archive.writestr(info,data)
                with self.assertRaises(Invalid):unpack(stream.getvalue(),Path(tmp))


class Downloads(unittest.IsolatedAsyncioTestCase):
    async def test_redirect_validation_and_stream_limit(self):
        class Response:
            def __init__(self,status=200,location=None,chunks=()):
                self.status=status;self.headers={'Location':location};self.chunks=chunks;self.content=self
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            def raise_for_status(self):pass
            async def iter_chunked(self,size):
                for chunk in self.chunks:yield chunk
        class Session:
            def __init__(self,responses):self.responses=iter(responses);self.urls=[]
            def get(self,url,**kwargs):self.urls.append(url);return next(self.responses)
        session=Session([Response(302,'http://localhost/private')])
        with self.assertRaises(Invalid):await download(session,'https://github.com/a/b',10)
        self.assertEqual(len(session.urls),1)
        session=Session([Response(chunks=[b'12345',b'67890'])])
        with self.assertRaises(Invalid):await download(session,'https://github.com/a/b',9)
        session=Session([Response(302,'https://release-assets.githubusercontent.com/asset'),Response(chunks=[b'abc'])])
        self.assertEqual(await download(session,'https://github.com/a/b',3),b'abc')
