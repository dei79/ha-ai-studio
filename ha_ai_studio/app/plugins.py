"""Trusted Git action catalog and per-instance Python environments.

Repository code is never imported into the server. A venv is dependency isolation,
not a security sandbox; only install repositories you trust.
"""
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sys
from urllib.parse import urlsplit
import uuid
from jsonschema import Draft202012Validator
from .domain import Invalid, stamp
from .store import Store

RUNNER = Path(__file__).with_name('plugin_runner.py')
SCHEMA = {'type':'object','required':['request_id','data'],'additionalProperties':False,
          'properties':{'request_id':{'type':'string','minLength':1,'maxLength':128},'data':{}}}
OUTPUT = {'type':'object','required':['request_id','status','data'],'additionalProperties':False,
          'properties':{'request_id':{'type':'string'},'status':{'const':'success'},'data':{}}}

async def process(args, *, cwd=None, payload=None, timeout=120, capture=False):
    # Deliberately exclude Supervisor tokens, dev broker credentials and Git helpers.
    env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':str(cwd or '/tmp'),
         'LANG':'C.UTF-8','GIT_TERMINAL_PROMPT':'0','GIT_CONFIG_NOSYSTEM':'1',
         'GIT_CONFIG_GLOBAL':'/dev/null','PIP_CONFIG_FILE':os.devnull,'PYTHONUNBUFFERED':'1'}
    proc=await asyncio.create_subprocess_exec(*map(str,args),cwd=cwd,env=env,
        stdin=asyncio.subprocess.PIPE if payload is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE if capture else asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,start_new_session=True)
    async def communicate():
        if payload is not None:
            proc.stdin.write(payload);await proc.stdin.drain();proc.stdin.close()
        chunks=[];size=0
        if capture:
            while chunk:=await proc.stdout.read(8192):
                size+=len(chunk)
                if size>65536:raise Invalid('Action response exceeds 65536 bytes.')
                chunks.append(chunk)
        await proc.wait()
        if proc.returncode:raise Invalid('Process failed. Check the repository contract and dependencies.')
        return b''.join(chunks)
    try:return await asyncio.wait_for(communicate(),timeout)
    finally:
        # Also stop descendants left behind by a timed-out or completed plugin.
        try:os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        await proc.wait()


def local_file(root, relative):
    if not isinstance(relative,str) or not relative or Path(relative).is_absolute():raise Invalid('Invalid action file path.')
    path=root/relative
    if any(part=='..' for part in Path(relative).parts) or not path.resolve().is_relative_to(root.resolve()):raise Invalid('Action files must stay inside their action directory.')
    if not path.is_file():raise Invalid('Required action file is missing.')
    return path


def manifest(root):
    path=local_file(root,'action.json')
    if path.stat().st_size>32768:raise Invalid('Action manifest is too large.')
    try:
        value=json.loads(path.read_text())
        if set(value)-{'id','name','description','version','python','entrypoint','settings_schema','input_schema','output_schema','example'}:raise ValueError()
        for key in ('id','name','description','version','python','entrypoint','settings_schema'):
            if key not in value:raise ValueError()
        if not re.fullmatch('[a-z][a-z0-9-]{0,47}',value['id']):raise ValueError()
        for key,limit in [('name',80),('description',500),('version',80)]:
            if not isinstance(value[key],str) or not 1<=len(value[key])<=limit or any(ord(c)<32 for c in value[key]):raise ValueError()
        if value['python']!=f'{sys.version_info.major}.{sys.version_info.minor}':raise Invalid('Action requires a different Python version.')
        if not re.fullmatch(r'[a-zA-Z_][\w/]*\.py',value['entrypoint']):raise ValueError()
        local_file(root,value['entrypoint']);local_file(root,'requirements.lock')
        for key in ('settings_schema','input_schema','output_schema'):
            schema=value.get(key,{})
            # External references could cause server-side network/file access.
            if '"$ref"' in json.dumps(schema) or '"$dynamicRef"' in json.dumps(schema):raise ValueError()
            Draft202012Validator.check_schema(schema)
        if value['settings_schema'].get('type')!='object':raise ValueError()
        json.dumps(value.get('example'),allow_nan=False)
        return value
    except Invalid:raise
    except Exception:raise Invalid('Invalid action manifest.') from None

class GitPlugin:
    def __init__(self,record,source):
        self.record=copy.deepcopy(record);self.source=Path(source);self.manifest=record['manifest']
        self.metadata={'type':record['type'],'name':self.manifest['name'],'description':self.manifest['description'],
            'input_schema':SCHEMA,'output_schema':OUTPUT,'settings_schema':self.manifest['settings_schema'],
            'example':self.manifest.get('example',{'request_id':'example-001','data':{}}),
            'source':record['repository_id'],'version':self.manifest['version'],'commit':record['commit'],'dynamic':True}
    def validate(self,value):
        if not isinstance(value,dict) or not Draft202012Validator(self.manifest['settings_schema']).is_valid(value):raise Invalid('Settings do not match the action schema.')
        if len(json.dumps(value,allow_nan=False).encode())>100000:raise Invalid('Action settings exceed 100000 bytes.')
    def validate_input(self,value):
        if not Draft202012Validator(SCHEMA).is_valid(value) or not Draft202012Validator(self.manifest.get('input_schema',{})).is_valid(value.get('data')):raise Invalid('Input does not match the action schema.')

class Repositories:
    def __init__(self,root):
        self.store=Store(Path(root)/'repositories');self.state=self.store.read('catalog.json',{'repositories':[]})
        self.lock=asyncio.Lock();self.tasks={};self.active_snapshots=set()
        for repo in self.state['repositories']:
            if repo['status']=='Syncing':repo.update(status='Failed',logs=['Repository sync interrupted. Refresh to retry.'])
    def public(self):
        value=copy.deepcopy(self.state)
        for repo in value['repositories']:
            if repo['status']=='Syncing' and (repo['id'] not in self.tasks or self.tasks[repo['id']].done()):repo.update(status='Failed',logs=['Sync stopped. Refresh to retry.'])
        return value
    def types(self):
        return {r['type']:GitPlugin(r,self.store.root/'sources'/r['snapshot']/r['directory']) for repo in self.state['repositories'] for r in repo['actions']}
    def bound(self,record):return GitPlugin(record,self.store.root/'sources'/record['snapshot']/record['directory'])
    async def save(self,value):
        if not isinstance(value,dict) or set(value)!={'url','ref'}:raise Invalid('Provide repository URL and Git ref.')
        url=value['url'];ref=value['ref']
        if not isinstance(url,str) or len(url)>512:raise Invalid('Provide an HTTPS Git URL without credentials.')
        parsed=urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or any(c.isspace() for c in url):raise Invalid('Provide an HTTPS Git URL without credentials.')
        if not isinstance(ref,str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._/\-]{0,127}',ref) or '..' in ref:raise Invalid('Provide a branch, tag or commit.')
        async with self.lock:
            if any(r['url']==url and r['ref']==ref for r in self.state['repositories']):raise Invalid('Repository and ref already configured.')
            if len(self.state['repositories'])>=16:raise Invalid('Maximum of 16 repositories.')
            repo={'id':uuid.uuid4().hex[:16],'url':url,'ref':ref,'status':'Not synced','actions':[],'logs':[]}
            candidate=copy.deepcopy(self.state);candidate['repositories'].append(repo);self.store.write('catalog.json',candidate);self.state=candidate
        self.refresh(repo['id']);return self.public()
    def refresh(self,id):
        if id in self.tasks and not self.tasks[id].done():raise Invalid('Repository refresh is already running.')
        if not any(r['id']==id for r in self.state['repositories']):raise Invalid('Repository not found.')
        self.tasks[id]=asyncio.create_task(self.sync(id))
    async def update(self,id,**fields):
        async with self.lock:
            candidate=copy.deepcopy(self.state);repo=next(r for r in candidate['repositories'] if r['id']==id);repo.update(fields)
            self.store.write('catalog.json',candidate);self.state=candidate
    async def prune_sources(self):
        protected={r['snapshot'] for repo in self.state['repositories'] for r in repo['actions']}|self.active_snapshots
        registry=Store(self.store.root.parent).read('agents.json',{})
        for definition in registry.get('agents',[])+registry.get('deleted',[]):
            if definition.get('plugin'):protected.add(definition['plugin']['snapshot'])
        sources=self.store.root/'sources'
        if sources.exists():
            for path in sources.iterdir():
                if path.name not in protected and path.is_dir():shutil.rmtree(path,ignore_errors=True)
    async def sync(self,id):
        snapshot=uuid.uuid4().hex;self.active_snapshots.add(snapshot);target=self.store.root/'sources'/snapshot
        target.parent.mkdir(exist_ok=True);target.mkdir()
        repo=next(r for r in self.state['repositories'] if r['id']==id)
        try:
            await self.update(id,status='Syncing',logs=['Fetching repository metadata.'])
            await process(['git','init','--quiet',target])
            await process(['git','-C',target,'-c','protocol.file.allow=never','fetch','--depth=1','--no-tags','--',repo['url'],repo['ref']])
            commit=(await process(['git','-C',target,'rev-parse','FETCH_HEAD'],capture=True)).decode().strip()
            await process(['git','-C',target,'-c','core.hooksPath=/dev/null','checkout','--detach','--quiet',commit])
            if any(p.is_symlink() for p in target.rglob('*')):raise Invalid('Repository symlinks are unsupported.')
            actions=[];base=target/'actions'
            if not base.is_dir() or base.is_symlink():raise Invalid('Repository must contain an actions directory.')
            for directory in sorted(base.iterdir()):
                if directory.is_symlink():raise Invalid('Symlink action directories are unsupported.')
                if not directory.is_dir():continue
                data=manifest(directory)
                if any(a['manifest']['id']==data['id'] for a in actions):raise Invalid('Duplicate action ID in repository.')
                actions.append({'type':f"git-{id}-{data['id']}",'repository_id':id,'commit':commit,'snapshot':snapshot,'directory':str(directory.relative_to(target)),'manifest':data})
            if not actions or len(actions)>64:raise Invalid('Repository must contain 1 to 64 actions.')
            shutil.rmtree(target/'.git')
            await self.update(id,status='Ready',actions=actions,commit=commit,logs=['Repository validated. No action code was executed.'],updated=stamp())
        except asyncio.CancelledError:
            shutil.rmtree(target,ignore_errors=True);raise
        except Exception:
            shutil.rmtree(target,ignore_errors=True)
            await self.update(id,status='Failed',logs=['Repository sync failed. Check HTTPS access, Git ref and action manifests. Previous catalog remains available.'])
        finally:
            self.active_snapshots.discard(snapshot)
            await self.prune_sources()
    async def close(self):
        for task in self.tasks.values():
            if not task.done():task.cancel()
        await asyncio.gather(*self.tasks.values(),return_exceptions=True)

class Environment:
    def __init__(self,store,plugin):
        self.store=store;self.plugin=plugin;self.task=None
        self.state=store.read('environment.json',{'status':'Not installed','logs':[]})
        if self.state['status'] in ('Queued','Installing','Verifying'):
            self.set('Failed','Installation interrupted. Rebuild the environment.')
        if self.state['status']=='Ready' and not self.ready:
            self.set('Failed','Environment is missing or incompatible. Rebuild the environment.')
    def public(self):
        value=copy.deepcopy(self.state)
        if value['status'] in ('Queued','Installing','Verifying') and (self.task is None or self.task.done()):
            value.update(status='Failed',logs=value['logs']+['Installation stopped. Rebuild to retry.'])
        return value
    @property
    def ready(self):
        return self.state['status']=='Ready' and self.state.get('python')==sys.version and self.state.get('commit')==self.plugin.record['commit'] and (self.path/'bin/python').is_file()
    @property
    def path(self):return self.store.root/'environments'/self.state.get('generation','missing')
    def set(self,status,message,**fields):
        value={**self.state,**fields,'status':status,'logs':(self.state.get('logs',[])+[message])[-30:]}
        self.store.write('environment.json',value);self.state=value
    def require(self):
        if not self.ready:raise Invalid('Action environment is not ready. Install or rebuild it first.')
    def start(self):
        if self.task and not self.task.done():raise Invalid('Environment installation is already running.')
        self.set('Queued','Environment installation queued.')
        self.task=asyncio.create_task(self.install())
    async def install(self):
        generation=uuid.uuid4().hex;path=self.store.root/'environments'/generation
        # Inactive instances cannot execute during rebuild; discard obsolete generations.
        previous=self.store.root/'environments'
        if previous.exists():
            for old in previous.iterdir():
                if old.is_dir():await asyncio.to_thread(shutil.rmtree,old,True)
        try:
            self.set('Installing','Creating isolated Python environment.',generation=generation)
            path.parent.mkdir(exist_ok=True);path.mkdir()
            source=path/'source';shutil.copytree(self.plugin.source,source,symlinks=False)
            # Require a complete wheel-only, hashed lock. Never run dependency build hooks.
            lock=(source/'requirements.lock').read_text()
            logical=lock.replace('\\\n',' ')
            for line in logical.splitlines():
                line=line.strip()
                if not line or line.startswith('#'):continue
                if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*==[A-Za-z0-9][A-Za-z0-9.!+_-]*(?:\s+--hash=sha256:[a-f0-9]{64})+',line):raise Invalid('Use exact registry versions with SHA256 hashes in requirements.lock.')
            self.set('Installing','Installing locked dependencies. Repository code is trusted.')
            await process([sys.executable,'-m','venv',path],timeout=120)
            await process([path/'bin/python','-m','pip','install','--isolated','--disable-pip-version-check','--no-input','--require-hashes','--only-binary=:all:','-r',source/'requirements.lock'],cwd=source,timeout=300)
            self.set('Verifying','Checking action entrypoint and runner protocol.')
            response=await process([path/'bin/python','-I',RUNNER,source,self.plugin.manifest['entrypoint']],cwd=source,payload=b'{"mode":"check"}',capture=True,timeout=30)
            if json.loads(response)!={'ready':True}:raise Invalid('Invalid runner response.')
            self.set('Ready','Environment is ready.',python=sys.version,commit=self.plugin.record['commit'])
        except asyncio.CancelledError:
            shutil.rmtree(path,ignore_errors=True)
            self.set('Failed','Installation interrupted. Rebuild the environment.');raise
        except Exception:
            shutil.rmtree(path,ignore_errors=True)
            self.set('Failed','Environment setup failed. Check the entrypoint and hashed wheel dependencies, then rebuild.')
    async def execute(self,data,settings):
        self.require();source=self.path/'source'
        response=await process([self.path/'bin/python','-I',RUNNER,source,self.plugin.manifest['entrypoint']],cwd=source,
            payload=json.dumps({'mode':'execute','data':data,'settings':settings},allow_nan=False).encode(),capture=True,timeout=30)
        try:
            value=json.loads(response,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
            if not isinstance(value,dict) or set(value)!={'data'} or not Draft202012Validator(self.plugin.manifest.get('output_schema',{})).is_valid(value['data']):raise ValueError()
            json.dumps(value,allow_nan=False,ensure_ascii=False).encode('utf-8')
            return value['data']
        except Exception:raise Invalid('Action returned an invalid JSON result.') from None
    async def close(self):
        if self.task and not self.task.done():self.task.cancel()
        if self.task:await asyncio.gather(self.task,return_exceptions=True)
