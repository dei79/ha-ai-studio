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
import weakref
from .domain import Invalid, stamp
from .store import Store

DEFAULT_REPOSITORY_URL = 'https://github.com/ha-ai-studio/ha-ai-studio-actions-core.git'
DEFAULT_REPOSITORY_REF = 'main'
RUNNER = Path(__file__).with_name('plugin_runner.py')
SCHEMA_WORKER = Path(__file__).with_name('schema_worker.py')
SCHEMA_TIMEOUT = 3
_SCHEMA_SLOTS = weakref.WeakKeyDictionary()
SCHEMA = {'type':'object','required':['request_id','data'],'additionalProperties':False,
          'properties':{'request_id':{'type':'string','minLength':1,'maxLength':128},'data':{}}}
OUTPUT = {'type':'object','required':['request_id','status','data'],'additionalProperties':False,
          'properties':{'request_id':{'type':'string'},'status':{'const':'success'},'data':{}}}

def kill_group(pid):
    try:os.killpg(pid,signal.SIGKILL)
    except ProcessLookupError:pass

class CommandProtocol(asyncio.SubprocessProtocol):
    """Keep draining stdout after the quota is hit; never buffer unbounded output."""
    def __init__(self,payload,capture):
        loop=asyncio.get_running_loop()
        self.exited=loop.create_future();self.closed=loop.create_future()
        self.payload=payload;self.capture=capture;self.chunks=[];self.size=0;self.exceeded=False
    def connection_made(self,transport):
        self.transport=transport
        if self.payload is not None:
            pipe=transport.get_pipe_transport(0)
            pipe.write(self.payload);pipe.close()
            self.payload=None
    def pipe_data_received(self,fd,data):
        if fd!=1 or not self.capture or self.exceeded:return
        self.size+=len(data)
        if self.size>65536:
            self.exceeded=True;self.chunks.clear();kill_group(self.transport.get_pid())
        else:self.chunks.append(data)
    def process_exited(self):
        if not self.exited.done():self.exited.set_result(None)
    def connection_lost(self,error):
        if not self.closed.done():self.closed.set_result(None)

async def process(args, *, cwd=None, payload=None, timeout=120, capture=False, venv=None):
    # Deliberately exclude Supervisor tokens, dev broker credentials and Git helpers.
    env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':str(cwd or '/tmp'),
         'LANG':'C.UTF-8','GIT_TERMINAL_PROMPT':'0','GIT_CONFIG_NOSYSTEM':'1',
         'GIT_CONFIG_GLOBAL':'/dev/null','PIP_CONFIG_FILE':os.devnull,'PYTHONUNBUFFERED':'1'}
    if venv is not None:
        env['PATH']=str(Path(venv)/'bin')+os.pathsep+env['PATH']
        env['VIRTUAL_ENV']=str(venv)
    protocol=CommandProtocol(payload,capture)
    transport,_=await asyncio.get_running_loop().subprocess_exec(lambda:protocol,*map(str,args),cwd=cwd,env=env,
        stdin=asyncio.subprocess.PIPE if payload is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE if capture else asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,start_new_session=True)
    try:
        await asyncio.wait_for(asyncio.shield(protocol.exited),timeout)
    finally:
        # Reap the process group and drain remaining pipe data, including on timeout
        # or cancellation. Escaped descendants cannot hold cleanup open indefinitely.
        kill_group(transport.get_pid())
        try:await asyncio.wait_for(asyncio.shield(protocol.closed),2)
        except asyncio.TimeoutError:pass
        finally:transport.close()
    if protocol.exceeded:raise Invalid('Action response exceeds 65536 bytes.')
    if transport.get_returncode():raise Invalid('Process failed. Check the repository contract and dependencies.')
    return b''.join(protocol.chunks)


async def schema_valid(schema, value=None, *, check=False):
    """Bound both queueing and execution; cancellation reaps the worker group."""
    try:
        payload=json.dumps({'mode':'schema' if check else 'value','schema':schema,'value':value},allow_nan=False).encode()
        if len(payload)>200000:raise Invalid('Schema validation input exceeds 200000 bytes.')
        loop=asyncio.get_running_loop()
        slots=_SCHEMA_SLOTS.setdefault(loop,asyncio.Semaphore(2))
        async with asyncio.timeout(SCHEMA_TIMEOUT):
            async with slots:
                response=await process([sys.executable,'-I',SCHEMA_WORKER],payload=payload,capture=True,timeout=SCHEMA_TIMEOUT)
        if response not in (b'true',b'false'):raise ValueError()
        return response==b'true'
    except asyncio.CancelledError:raise
    except Exception:
        raise Invalid('Schema validation failed or exceeded its resource limits.') from None


async def valid_example(value,data_schema):
    try:
        if not isinstance(value,dict) or set(value)!={'request_id','data'}:return False
        ident=value['request_id']
        if not isinstance(ident,str) or not 1<=len(ident)<=128 or not ident.strip() or any(ord(c)<32 for c in ident):return False
        encoded=json.dumps(value,allow_nan=False,ensure_ascii=False).encode('utf-8')
        return len(encoded)<=16384 and await schema_valid(data_schema,value['data'])
    except Invalid:raise
    except (ValueError,TypeError,UnicodeError,RecursionError):return False


def local_file(root, relative):
    if not isinstance(relative,str) or not relative or Path(relative).is_absolute():raise Invalid('Invalid action file path.')
    path=root/relative
    if any(part=='..' for part in Path(relative).parts) or not path.resolve().is_relative_to(root.resolve()):raise Invalid('Action files must stay inside their action directory.')
    if not path.is_file():raise Invalid('Required action file is missing.')
    return path


async def manifest(root):
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
            if not await schema_valid(schema,check=True):raise ValueError()
        if value['settings_schema'].get('type')!='object':raise ValueError()
        if 'example' in value and not await valid_example(value['example'],value.get('input_schema',{})):
            raise Invalid('Example must be a valid request matching the input schema.')
        if 'example' not in value:
            example={'request_id':'example-001','data':{}}
            if await valid_example(example,value.get('input_schema',{})):value['example']=example
        return value
    except Invalid:raise
    except Exception:raise Invalid('Invalid action manifest.') from None

class GitPlugin:
    def __init__(self,record,source):
        self.record=copy.deepcopy(record);self.source=Path(source);self.manifest=record['manifest']
        input_schema=copy.deepcopy(SCHEMA);output_schema=copy.deepcopy(OUTPUT)
        input_schema['properties']['data']=copy.deepcopy(self.manifest.get('input_schema',{}))
        output_schema['properties']['data']=copy.deepcopy(self.manifest.get('output_schema',{}))
        # Explicit examples were validated at import. Never execute schemas while
        # constructing saved instances or rendering the catalog.
        example=self.manifest.get('example')
        if 'example' not in self.manifest and self.manifest.get('input_schema',{})=={}:
            example={'request_id':'example-001','data':{}}
        self.metadata={'type':record['type'],'name':self.manifest['name'],'description':self.manifest['description'],
            'input_schema':input_schema,'output_schema':output_schema,'settings_schema':copy.deepcopy(self.manifest['settings_schema']),
            'example':copy.deepcopy(example),
            'source':record['repository_id'],'version':self.manifest['version'],'commit':record['commit'],'dynamic':True}
    async def validate(self,value):
        if len(json.dumps(value,allow_nan=False).encode())>100000:raise Invalid('Action settings exceed 100000 bytes.')
        if not isinstance(value,dict) or not await schema_valid(self.manifest['settings_schema'],value):raise Invalid('Settings do not match the action schema.')
    async def validate_input(self,value):
        schema=copy.deepcopy(SCHEMA)
        schema['properties']['data']=self.manifest.get('input_schema',{})
        if not await schema_valid(schema,value):raise Invalid('Input does not match the action schema.')

def system_repository(url):
    return url.rstrip('/').lower().removesuffix('.git')==DEFAULT_REPOSITORY_URL.lower().removesuffix('.git')

class Repositories:
    def __init__(self,root):
        self.store=Store(Path(root)/'repositories');self.state=self.store.read('catalog.json',{'repositories':[]})
        self.lock=asyncio.Lock();self.tasks={};self.active_snapshots=set()
        for repo in self.state['repositories']:
            if repo['status']=='Syncing':repo.update(status='Failed',logs=['Repository sync interrupted. Refresh to retry.'])
    def start(self):
        # Bootstrap only metadata. Never create instances or execute repository code.
        repo=next((r for r in self.state['repositories'] if system_repository(r['url'])),None)
        if repo is None:
            repo={'id':uuid.uuid4().hex[:16],'url':DEFAULT_REPOSITORY_URL,'ref':DEFAULT_REPOSITORY_REF,
                  'status':'Not synced','actions':[],'logs':[]}
            candidate=copy.deepcopy(self.state);candidate['repositories'].append(repo)
            self.store.write('catalog.json',candidate);self.state=candidate
        if repo['status'] in ('Not synced','Failed'):self.refresh(repo['id'])
    def public(self):
        value=copy.deepcopy(self.state)
        registry=Store(self.store.root.parent).read('agents.json',{})
        used={d['plugin']['repository_id'] for d in registry.get('agents',[]) if d.get('plugin')}
        for repo in value['repositories']:
            repo['system']=system_repository(repo['url'])
            repo['in_use']=repo['id'] in used
            repo['refreshing']=repo['id'] in self.tasks and not self.tasks[repo['id']].done()
            repo['delete_reason']='System repositories cannot be deleted.' if repo['system'] else 'Repository is used by existing actions, including inactive actions.' if repo['in_use'] else 'Wait for repository refresh to finish.' if repo['refreshing'] else None
            repo['can_delete']=repo['delete_reason'] is None
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
    async def delete(self,value):
        if not isinstance(value,dict) or set(value)!={'id','confirmed'} or not isinstance(value['id'],str) or value['confirmed'] is not True:
            raise Invalid('Confirm repository deletion.')
        async with self.lock:
            repo=next((r for r in self.public()['repositories'] if r['id']==value['id']),None)
            if repo is None:raise Invalid('Repository not found.')
            if not repo['can_delete']:raise Invalid(repo['delete_reason'])
            candidate=copy.deepcopy(self.state)
            candidate['repositories']=[r for r in candidate['repositories'] if r['id']!=value['id']]
            self.store.write('catalog.json',candidate);self.state=candidate
            self.tasks.pop(value['id'],None)
        await self.prune_sources()
        return self.public()
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
                data=await manifest(directory)
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
            await process([path/'bin/python','-m','pip','install','--isolated','--disable-pip-version-check','--no-input','--require-hashes','--only-binary=:all:','-r',source/'requirements.lock'],cwd=source,timeout=300,venv=path)
            self.set('Verifying','Checking action entrypoint and runner protocol.')
            response=await process([path/'bin/python','-I',RUNNER,source,self.plugin.manifest['entrypoint']],cwd=source,payload=b'{"mode":"check"}',capture=True,timeout=30,venv=path)
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
            payload=json.dumps({'mode':'execute','data':data,'settings':settings},allow_nan=False).encode(),capture=True,timeout=30,venv=self.path)
        try:
            value=json.loads(response,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
            if not isinstance(value,dict) or set(value)!={'data'} or not await schema_valid(self.plugin.manifest.get('output_schema',{}),value['data']):raise ValueError()
            json.dumps(value,allow_nan=False,ensure_ascii=False).encode('utf-8')
            return value['data']
        except Exception:raise Invalid('Action returned an invalid JSON result.') from None
    async def close(self):
        if self.task and not self.task.done():self.task.cancel()
        if self.task:await asyncio.gather(self.task,return_exceptions=True)
