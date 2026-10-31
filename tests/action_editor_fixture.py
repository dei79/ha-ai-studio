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
    result=await studio.repositories.save({'kind':'local','path':'.'})
    ident=result['repositories'][0]['id'];await studio.repositories.tasks[ident]
    plugin=next(p for p in studio.repositories.types().values() if p.manifest['id']=='analog-meter-reading')
    await studio.create({'id':'meter-editor','name':'Analog Meter Reader','type':plugin.record['type']})
    service=studio.get('meter-editor');await service.environment.task
    if not service.environment.ready:raise RuntimeError('Fixture environment failed')
    if Path('/fixture/reference.png').is_file():
        image=await service.assets.upload({'base64':base64.b64encode(Path('/fixture/reference.png').read_bytes()).decode()})
        settings=json.loads(Path('/fixture/settings.json').read_text());settings['reference']={'asset_id':image['id'],'width':image['width'],'height':image['height']}
        draft={**service.config['draft'],'settings':settings}
        await service.save(draft,False,set_enabled=False)
    async def cleanup(app):await studio.close()
    app.on_cleanup.append(cleanup)
    outer=web.Application();outer.add_subapp('/api/hassio_ingress/editor-check',app)
    return outer

web.run_app(main(),host='0.0.0.0',port=8099,access_log=None)
