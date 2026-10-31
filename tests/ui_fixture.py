"""Synthetic UI transport for embedded-browser checks; never opens MQTT or real storage.

Run in the built image with tests mounted read-only and port 8101 bound to loopback.
The frontend assets and legacy module are the exact files from the runtime image.
Every API endpoint is handled here; unknown endpoints fail closed.
"""
import copy
import json
import re
from pathlib import Path
from aiohttp import web
from app.server import STATIC

PREFIX = '/api/hassio_ingress/ui-check/'
PLUGIN = {'type': 'git-fixture', 'name': 'Fixture Echo', 'dynamic': True, 'version': '1.0.0', 'commit': 'a'*40,
          'example': {'request_id': 'example', 'data': 0}, 'input_schema': {'type': 'object'}, 'output_schema': {'type': 'object'},
          'settings_schema': {'type': 'object', 'additionalProperties': False, 'properties': {'limit': {'type': 'integer', 'title': 'Limit'}, 'enabled': {'type': 'boolean', 'title': 'Enabled setting'}}}}

def state(id, name, dynamic=True):
    plugin=copy.deepcopy(PLUGIN)
    if not dynamic:plugin.update(type='echo', name='Legacy Echo', dynamic=False)
    return {'definition': {'id': id, 'name': name, 'type': plugin['type']}, 'supported': True, 'enabled': False, 'busy': False, 'mqtt': 'Disabled',
            'config': {'draft': {'name': name, 'input': {'broker_id': 'fixture-broker', 'topic': 'fixture/request'}, 'output': {'broker_id': None, 'topic': 'fixture/result'}, 'settings': {}}, 'active': None},
            'plugin': plugin, 'environment': {'status': 'Ready', 'logs': ['Synthetic environment ready.', 'Log line with a long unwrapped value: '+('0123456789'*15)]}, 'issues': []}

states={'legacy-fixture':state('legacy-fixture','Compatibility fixture',False), 'git-fixture':state('git-fixture','Git fixture')}
BROKER={'id':'fixture-broker','name':'Isolated fixture broker','host':'broker.invalid','port':1883,'tls':False,'source':'manual','editable':True,'secrets':{'username':False,'password':False}}
brokers=[BROKER]
discovery={'config':{'enabled':False,'broker_id':None,'prefix':'homeassistant','ha_status_topic':'homeassistant/status'},'status':'Disabled','pending_cleanup':0,'legacy_pending':False}
repositories=[]

async def handle(request):
    path=request.path
    path=path[len(PREFIX):] if path.startswith(PREFIX) else path.lstrip('/')
    if path=='':return web.FileResponse(STATIC/'index.html')
    if path.startswith('static/'):
        name=path.removeprefix('static/')
        if not re.fullmatch(r'[A-Za-z0-9_-]+\.(js|css)',name):raise web.HTTPNotFound()
        return web.FileResponse(STATIC/'static'/name)
    if path=='action-types/echo/editor.js':return web.FileResponse(Path('/app/app/action_types/legacy_echo/editor.js'))
    if not path.startswith('api/'):raise web.HTTPNotFound()
    body=await request.json() if request.method=='POST' else None
    if body is not None and request.headers.get('X-HA-AI-Studio-Request')!='1':raise web.HTTPForbidden()
    endpoint=path[4:];id=request.query.get('id')
    if endpoint=='actions':
        if body:states[body['id']]=state(body['id'],body['name'])
        return web.json_response({'actions':list(states.values()),'types':[PLUGIN]})
    if endpoint=='action':
        value=states[id]
        if body:
            value['config']['draft']=body['config'];value['definition']['name']=body['config']['name'];value['enabled']=body['enabled']
            if body['enabled']:value['config']['active']=copy.deepcopy(body['config'])
        return web.json_response(value)
    if endpoint=='delete-action':states.pop(body['id']);return web.json_response({'deleted':True})
    if endpoint=='brokers':
        if body:
            value=next((b for b in brokers if b['id']==body['id']),None)
            if value is None:value=copy.deepcopy(BROKER);value['id']='created-broker';brokers.append(value)
            value.update({k:body[k] for k in ('name','host','port','tls')})
        return web.json_response({'brokers':brokers,'default_id':None})
    if endpoint=='discovery':
        if body:discovery['config']=body
        return web.json_response(discovery)
    if endpoint=='repositories':return web.json_response({'repositories':repositories})
    if endpoint=='environment':return web.json_response(states[id])
    if endpoint=='live':return web.json_response({'epoch':'fixture','cursor':0,'mqtt':'Disabled','gap':False,'events':[]})
    if endpoint=='test':return web.json_response({'mode':'test','delivery':'not_sent','result':{'status':'success','data':json.loads(body['payload'])['data']}})
    if endpoint=='broker-test':return web.json_response({'ok':True,'message':'Synthetic diagnostic complete.','scope':'Fixture only. No network connection or MQTT publication.','logs':[{'elapsed_ms':0,'message':'Synthetic connection check.'}]})
    raise web.HTTPNotFound(text='Unexpected fixture endpoint')

@web.middleware
async def headers(request,handler):
    response=await handler(request)
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'"
    response.headers['Cache-Control']='no-store'
    return response

app=web.Application(middlewares=[headers]);app.router.add_route('*','/{tail:.*}',handle)
web.run_app(app,host='0.0.0.0',port=8101,access_log=None)
