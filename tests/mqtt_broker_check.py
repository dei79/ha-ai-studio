"""Real MQTT checks on two isolated brokers. No personal credentials or HA access."""
import asyncio
import json
import tempfile
import threading
import uuid
from unittest.mock import patch
import paho.mqtt.client as mqtt
from app.actions import Studio
from test_actions import broker

async def main():
    loop=asyncio.get_running_loop();clients=[];events=asyncio.Queue();seen=[]
    async def observe(host):
        ready=threading.Event();client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='test-'+uuid.uuid4().hex)
        client.on_connect=lambda c,*args:c.subscribe('#',qos=1)
        client.on_subscribe=lambda *args:ready.set()
        def receive(c,u,msg):
            try:value=json.loads(msg.payload)
            except ValueError:return
            event=(host,msg.topic,value,msg.retain)
            loop.call_soon_threadsafe(events.put_nowait,event);loop.call_soon_threadsafe(seen.append,event)
        client.on_message=receive
        await asyncio.to_thread(client.connect,host,1883);client.loop_start();assert await asyncio.to_thread(ready.wait,5)
        clients.append(client);return client
    async def send(client,topic,body,retain=False,raw=False):
        info=client.publish(topic,body if raw else json.dumps(body),qos=1,retain=retain);await asyncio.to_thread(info.wait_for_publish,5)
    async def response(id):
        while True:
            host,topic,body,retained=await asyncio.wait_for(events.get(),15)
            if host=='broker2' and topic=='echo/result' and body.get('request_id')==id:return body
    async def idle(service):
        for _ in range(500):
            if not service.busy:return
            await asyncio.sleep(.01)
        raise AssertionError('Service remained busy')
    a_client=await observe('broker');b_client=await observe('broker2')
    with tempfile.TemporaryDirectory() as root:
        studio=Studio(root)
        a=(await studio.brokers.save(broker()))['brokers'][0]['id'];before=set(studio.brokers.all());await studio.brokers.save(broker('broker2'));b=next(iter(set(studio.brokers.all())-before))
        await studio.create({'id':'echo','name':'Echo','type':'echo'});service=studio.get('echo');config=service.config['draft']
        config['input']={'broker_id':a,'topic':'echo/request'};config['output']={'broker_id':b,'topic':'echo/result'}
        await service.save(config,False);await service.publish();assert service.mqtt is None
        await service.test(config,'{"request_id":"test-only","data":0}');assert not service.jobs
        await service.save(config,True);await service.publish();await studio.start();await idle(service)
        await send(a_client,'echo/request',{'request_id':'live-retained','data':0},True)
        await asyncio.sleep(.2);assert 'live-retained' not in service.jobs
        for n,data in enumerate([None,False,0,[],[1,False],{'message':'Hello','value':42}]):
            request={'request_id':str(n),'data':data};await send(a_client,'echo/request',request)
            assert await response(str(n))=={'request_id':str(n),'status':'success','data':data}
        await idle(service)
        await send(a_client,'echo/request',{'request_id':'5','data':{'message':'Hello','value':42}});assert (await response('5'))['status']=='success'
        await send(a_client,'echo/request',{'request_id':'5','data':'different'});assert (await response('5'))['error']['code']=='request_id_conflict'
        await send(a_client,'echo/request','{',raw=True);assert (await response(None))['error']['code']=='invalid_request'
        await send(a_client,'echo/request',{'request_id':'invalid'});assert (await response('invalid'))['error']['code']=='invalid_request'
        await idle(service);await studio.close()
        await send(a_client,'echo/request',{'request_id':'retained','data':1},True)
        studio=Studio(root);service=studio.get('echo');await service.publish();await studio.start();await idle(service)
        await send(a_client,'echo/request',{'request_id':'5','data':{'message':'Hello','value':42}});assert (await response('5'))['status']=='success'
        await idle(service);assert 'retained' not in service.jobs
        # Actual connection failure, followed by durable cached-result retry to original broker.
        with patch('app.actions.MQTT.connect',side_effect=OSError('isolated outage')):
            await service.run_request_payload('{"request_id":"outage","data":false}')
        assert service.last['execution']=='success' and service.last['delivery']=='failed'
        await send(a_client,'echo/request',{'request_id':'outage','data':False});assert (await response('outage'))['data'] is False
        await idle(service);assert service.last['delivery']=='published'
        await service.deactivate();await send(a_client,'echo/request',{'request_id':'inactive','data':0});await asyncio.sleep(.2);assert 'inactive' not in service.jobs
        await service.save(config,True);await service.publish();await send(a_client,'echo/request',{'request_id':'reactivated','data':42});assert (await response('reactivated'))['data']==42
        await idle(service);await studio.delete({'id':'echo','confirmed':True});await send(a_client,'echo/request',{'request_id':'deleted','data':0});await asyncio.sleep(.1);assert 'deleted' not in service.jobs
        await studio.close()
        assert not any(host=='broker' and topic=='echo/result' for host,topic,_,_ in seen)
        assert not any('/internal/' in topic for _,topic,_,_ in seen)
        before=len(seen);await observe('broker');await observe('broker2');await asyncio.sleep(.3)
        assert not any(topic=='echo/result' for _,topic,_,_ in seen[before:]),'Results must not be retained'
    for client in clients:client.disconnect();await asyncio.to_thread(client.loop_stop)
    print('PASS: Echo across brokers A/B; all JSON types; duplicate/conflict; invalid JSON; retained rejection; restart; delivery failure/retry; draft test isolation; deactivate/reactivate/delete; no internal workflow topics or retained results.')

asyncio.run(main())
