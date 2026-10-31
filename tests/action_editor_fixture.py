"""Real assets/preview API on disposable data; no Studio lifecycle and no MQTT.

Mount an action repository at /fixture-source, test PNG at /fixture/reference.png.
This server never starts brokers, discovery or Action subscription loops.
"""
import base64
import json
import os
from pathlib import Path
import tempfile
from aiohttp import web
from app.actions import Studio
from app.server import create_app

async def main():
    os.environ['HA_AI_STUDIO_DEV']='1';os.environ['HA_AI_STUDIO_LOCAL_ACTIONS']='/fixture-source'
    root=tempfile.mkdtemp(prefix='studio-editor-fixture-')
    app=create_app(root,dev=True);app.cleanup_ctx.clear()
    studio=next(v for v in app.values() if isinstance(v,Studio))
    async def fixture_entities(domains,query):
        rows=[{'entity_id':'camera.fixture_meter','name':'Meter camera','state':'idle','available':True},
              {'entity_id':'light.fixture_meter','name':'Meter illumination','state':'off','available':True},
              {'entity_id':'camera.fixture_offline','name':'Offline camera','state':'unavailable','available':False}]
        rows=[r for r in rows if r['entity_id'].split('.')[0] in domains and query.lower() in (r['name']+' '+r['entity_id']).lower()]
        return {'entities':rows,'total':len(rows)}
    studio.home_assistant.search=fixture_entities
    illumination='off'
    async def fixture_request(method,path,data=None,image=False):
        nonlocal illumination
        if path=='states/camera.fixture_meter':return {'state':'idle'}
        if path=='states/light.fixture_meter':return {'state':illumination}
        if path=='camera_proxy/camera.fixture_meter':return Path('/fixture/reference.png').read_bytes()
        if path.startswith('services/light/') and data=={'entity_id':'light.fixture_meter'}:
            illumination='on' if path.endswith('turn_on') else 'off';return []
        raise RuntimeError('Only synthetic fixture devices are allowed')
    studio.home_assistant.request=fixture_request
    result=await studio.repositories.save({'kind':'local','path':'.'})
    ident=result['repositories'][0]['id'];await studio.repositories.tasks[ident]
    plugin=next(p for p in studio.repositories.types().values() if p.manifest['id']=='analog-meter-reading')
    await studio.create({'id':'meter-editor','name':'Analog Meter Reader','type':plugin.record['type']})
    service=studio.get('meter-editor');await service.environment.task
    if not service.environment.ready:raise RuntimeError('Fixture environment failed')
    if Path('/fixture/reference.png').is_file():
        image=await service.assets.upload({'base64':base64.b64encode(Path('/fixture/reference.png').read_bytes()).decode()})
        settings=json.loads(Path('/fixture/settings.json').read_text());settings['reference']={'asset_id':image['id'],'width':image['width'],'height':image['height']}
        settings['capture']={'camera_entity':'camera.fixture_meter','light_entity':'light.fixture_meter','settle_seconds':0,'count':1}
        draft={**service.config['draft'],'settings':settings}
        await service.save(draft,False,set_enabled=False)
    async def cleanup(app):await studio.close()
    app.on_cleanup.append(cleanup)
    outer=web.Application();outer.add_subapp('/api/hassio_ingress/editor-check',app)
    return outer

web.run_app(main(),host='0.0.0.0',port=8099,access_log=None)
