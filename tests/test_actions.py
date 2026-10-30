import asyncio
import copy
import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch,Mock,AsyncMock
from aiohttp.test_utils import TestClient,TestServer
from app.actions import Studio,parse,MAX_BYTES
from app.action_types import TYPES
from app.domain import Invalid
from app.server import create_app
from app.store import Store

def broker(host='broker'):
    return {'id':None,'name':host,'host':host,'port':1883,'tls':False,'username':'private-user','password':'private-password'}

class Actions(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.studio=Studio(self.tmp.name)
        await self.studio.create({'id':'echo','name':'Echo test','type':'echo'});self.s=self.studio.get('echo')
        self.a=(await self.studio.brokers.save(broker()))['brokers'][0]['id']
        before=set(self.studio.brokers.all());await self.studio.brokers.save(broker('broker2'));self.b=next(iter(set(self.studio.brokers.all())-before))
        self.conf=copy.deepcopy(self.s.config['draft']);self.conf['input'].update(broker_id=self.a,topic='echo/request');self.conf['output'].update(broker_id=self.b,topic='echo/result')
    async def asyncTearDown(self):await self.studio.close();self.tmp.cleanup()
    async def activate(self):await self.s.save(self.conf,True)
    async def send(self,data=None,id='one'):
        with patch('app.actions.MQTT'):
            return await self.s.run_request_payload(json.dumps({'request_id':id,'data':data}))
    async def test_save_checkbox_state_is_atomic_and_persistent(self):
        await self.s.save(self.conf,True,set_enabled=True)
        revised=copy.deepcopy(self.conf);revised['name']='Saved inactive'
        with patch.object(self.s,'disconnect',new_callable=AsyncMock) as disconnect:
            with patch.object(self.s.store,'write',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):await self.s.save(revised,False,set_enabled=False)
            self.assertTrue(self.s.enabled);self.assertNotEqual(self.s.config['draft']['name'],revised['name'])
            disconnect.assert_not_called()
            await self.s.save(revised,False,set_enabled=False)
            disconnect.assert_awaited_once()
        restored=Studio(self.tmp.name)
        self.assertFalse(restored.get('echo').enabled)
        self.assertEqual(restored.get('echo').config['draft'],revised)
        await self.s.save(revised,True,set_enabled=True)
        self.assertTrue(self.s.enabled);self.assertEqual(self.s.config['active'],revised)
        await restored.close()

    async def test_live_activity_is_scoped_bounded_and_ephemeral(self):
        await self.activate()
        await self.send({'hello':'world'})
        events=self.s.live()['events']
        self.assertEqual([e['kind'] for e in events],['input','processing','processing','output','delivery'])
        self.assertIn('world',events[0]['payload']);self.assertIn('world',events[3]['payload'])
        self.assertNotIn('private-password',json.dumps(events))
        cursor=self.s.live()['cursor'];self.assertEqual(self.s.live(cursor)['events'],[])
        await self.s.test(self.conf,json.dumps({'request_id':'test','data':1}))
        self.assertEqual(self.s.live()['cursor'],cursor)
        for i in range(210):self.s.trace('processing','step')
        self.assertEqual(len(self.s.live()['events']),200);self.assertTrue(self.s.live(1)['gap'])
        restored=Studio(self.tmp.name)
        self.assertEqual(restored.get('echo').live()['events'],[])
        self.assertNotEqual(restored.get('echo').event_epoch,self.s.event_epoch)
        await restored.close()
        await self.studio.create({'id':'other','name':'Other','type':'echo'})
        self.assertEqual(self.studio.get('other').live()['events'],[])

    async def test_shutdown_drains_connect_and_publish_workers(self):
        await self.activate()
        for phase in ('connect','publish'):
            with self.subTest(phase=phase):
                started=threading.Event();release=threading.Event();calls=[]
                class Transport:
                    def __init__(self,*args,**kwargs):pass
                    def block(self,name):
                        calls.append(name+'_started')
                        if name==phase:
                            started.set()
                            if not release.wait(5):raise TimeoutError()
                        calls.append(name+'_finished')
                    def connect(self,*args):self.block('connect')
                    def publish(self,*args,**kwargs):self.block('publish')
                    def close(self):calls.append('close')
                with patch('app.actions.MQTT',Transport):
                    task=asyncio.create_task(self.s.run_request_payload(json.dumps({'request_id':phase,'data':1})))
                    try:
                        self.assertTrue(await asyncio.to_thread(started.wait,2))
                        task.cancel();await asyncio.sleep(.02)
                        task.cancel();await asyncio.sleep(.02)
                        self.assertFalse(task.done());self.assertNotIn('close',calls)
                    finally:release.set()
                    with self.assertRaises(asyncio.CancelledError):await task
                self.assertLess(calls.index(phase+'_finished'),calls.index('close'))
                if phase=='connect':self.assertNotIn('publish_started',calls)
                self.assertEqual(self.s.last['delivery'],'unknown')
                self.assertEqual(self.s.jobs[phase]['delivery'],'unknown')

    async def test_shutdown_drains_input_connection(self):
        await self.activate()
        started=threading.Event();release=threading.Event();calls=[]
        class Transport:
            def __init__(self,*args,**kwargs):pass
            def connect(self,*args):
                started.set()
                if not release.wait(5):raise TimeoutError()
                calls.append('connected')
            def close(self):calls.append('closed')
        with patch('app.actions.MQTT',Transport):
            self.s.task=asyncio.create_task(self.s.publish())
            self.assertTrue(await asyncio.to_thread(started.wait,2))
            shutdown=asyncio.create_task(self.s.close())
            try:
                await asyncio.sleep(.02)
                self.assertFalse(shutdown.done());self.assertEqual(calls,[])
            finally:release.set()
            await shutdown
        self.assertEqual(calls,['connected','closed']);self.assertIsNone(self.s.mqtt)

    async def test_all_json_types_echo_semantically_unchanged(self):
        await self.activate()
        for n,value in enumerate([None,False,0,True,42,'',[],{},[0,False,None],{'x':{'nested':[1,'two']}}]):
            result=await self.send(value,str(n));self.assertEqual(result,{'request_id':str(n),'status':'success','data':value})
    async def test_validation_and_errors_preserve_valid_id(self):
        for payload,id,code in [('{',None,'invalid_request'),('{}',None,'invalid_request_id'),('{"request_id":""}',None,'invalid_request_id'),('{"request_id":"x"}','x','invalid_request'),('{"request_id":"x","data":NaN}',None,'invalid_request'),('{"request_id":"x","data":1e999}','x','invalid_request'),('{"request_id":"x","data":1,"extra":2}','x','invalid_request')]:
            result=await self.s.test(self.conf,payload);self.assertEqual(result['result']['request_id'],id);self.assertEqual(result['result']['error']['code'],code)
        for id in [' '*4,'x'*129,'x\n']:
            _,error=parse(json.dumps({'request_id':id,'data':None}),TYPES['echo']);self.assertEqual(error['request_id'],None)
        _,error=parse(json.dumps({'request_id':'x','data':'a'*MAX_BYTES}),TYPES['echo']);self.assertEqual(error['error']['code'],'message_too_large');self.assertEqual(error['request_id'],'x')
        self.assertIsNotNone(parse('{"request_id":"x","data":1,"data":2}',TYPES['echo'])[1])
    async def test_draft_test_never_connects_or_changes_production(self):
        before=copy.deepcopy(self.s.config)
        with patch('app.actions.MQTT') as mqtt:
            result=await self.s.test(self.conf,'{"request_id":"test","data":false}');mqtt.assert_not_called()
        self.assertFalse(result['result']['data']);self.assertEqual(result['delivery'],'not_sent');self.assertEqual(self.s.jobs,{});self.assertIsNone(self.s.last);self.assertEqual(self.s.config,before)
    async def test_activate_deactivate_persist_draft_separation(self):
        with patch('app.actions.MQTT') as mqtt:await self.s.publish();mqtt.assert_not_called()
        await self.activate();draft=copy.deepcopy(self.conf);draft['name']='Draft name';await self.s.save(draft,False)
        self.assertNotEqual(self.s.config['draft'],self.s.config['active'])
        await self.s.deactivate();restored=Studio(self.tmp.name).get('echo');self.assertFalse(restored.enabled);self.assertEqual(restored.config['draft'],draft)
        with patch('app.actions.MQTT') as mqtt:await restored.publish();mqtt.assert_not_called()
    async def test_dedup_conflict_and_restart(self):
        await self.activate();first=await self.send({'v':42})
        with patch.object(TYPES['echo'],'execute',side_effect=AssertionError('no replay')):
            self.assertEqual(await self.send({'v':42}),first)
            self.assertEqual((await self.send({'v':99}))['error']['code'],'request_id_conflict')
            self.s=Studio(self.tmp.name).get('echo');self.assertEqual(await self.send({'v':42}),first)
    async def test_intent_persisted_before_execution_and_interrupted_not_replayed(self):
        await self.activate()
        async def crash(data,settings):
            self.assertIsNone(self.s.store.read('action-jobs.json')['one']['result']);raise asyncio.CancelledError()
        with patch.object(TYPES['echo'],'execute',crash):
            with self.assertRaises(asyncio.CancelledError):await self.send(42)
        self.s=Studio(self.tmp.name).get('echo');self.assertEqual((await self.send(42))['error']['code'],'interrupted')
    async def test_intent_write_failure_prevents_execution(self):
        await self.activate()
        with patch.object(self.s.store,'write',side_effect=OSError()),patch.object(TYPES['echo'],'execute',new_callable=AsyncMock) as execute:
            with self.assertRaises(OSError):await self.send(42)
            execute.assert_not_called()
    async def test_result_commit_failure_never_reexecutes(self):
        await self.activate();original=self.s.store.write
        def fail(name,value):
            if name=='action-jobs.json' and value['one']['result'] is not None:raise OSError()
            original(name,value)
        with patch.object(self.s.store,'write',side_effect=fail):
            with self.assertRaises(OSError):await self.send(42)
        self.s=Studio(self.tmp.name).get('echo');self.assertEqual((await self.send(42))['error']['code'],'interrupted')
    async def test_delivery_failure_and_saved_route_retry(self):
        await self.activate()
        with patch('app.actions.MQTT') as mqtt:
            mqtt.return_value.connect.side_effect=OSError('private-password');result=await self.s.run_request_payload('{"request_id":"one","data":0}')
        self.assertEqual(result['status'],'success');self.assertEqual(self.s.last['delivery'],'failed');self.assertEqual(self.s.jobs['one']['delivery'],'failed')
        changed=copy.deepcopy(self.conf);changed['output']['broker_id']=self.a;await self.s.save(changed,True)
        with self.assertRaises(Invalid):await self.studio.brokers.delete({'id':self.b,'confirmed':True})
        self.s=Studio(self.tmp.name).get('echo')
        with patch('app.actions.MQTT') as mqtt,patch.object(TYPES['echo'],'execute',new_callable=AsyncMock) as execute:
            await self.s.run_request_payload('{"request_id":"one","data":0}');execute.assert_not_called();self.assertEqual(mqtt.return_value.connect.call_args.args[0]['mqtt']['host'],'broker2');self.assertFalse(mqtt.return_value.publish.call_args.kwargs['retain'])
        self.assertEqual(self.s.last['delivery'],'published')
    async def test_loop_and_duplicate_active_input_rejected(self):
        same=copy.deepcopy(self.conf);same['output']=copy.deepcopy(same['input'])
        with self.assertRaises(Invalid):await self.s.save(same,True)
        await self.activate();await self.studio.create({'id':'other','name':'Other','type':'echo'});other=self.studio.get('other')
        with self.assertRaises(Invalid):await other.save(self.conf,True)
        reverse=copy.deepcopy(self.conf);reverse['input']={'broker_id':self.b,'topic':'echo/result'};reverse['output']={'broker_id':self.a,'topic':'echo/request'}
        with self.assertRaises(Invalid):await other.save(reverse,True)
    async def test_broker_edit_cannot_introduce_cycle(self):
        config=copy.deepcopy(self.conf);config['output']['topic']=config['input']['topic'];await self.s.save(config,True)
        with self.assertRaises(Invalid):await self.studio.brokers.save(broker()|{'id':self.b})
        self.assertEqual(self.studio.brokers.get(self.b)['settings']['mqtt']['host'],'broker2')
    async def test_response_envelopes_and_stale_callbacks_ignored(self):
        await self.activate();self.s.trigger(b'{"status":"error","request_id":"x"}');self.assertTrue(self.s.queue.empty())
        generation=self.s.transport_generation;await self.s.disconnect();self.s.trigger(b'{}',generation);self.assertTrue(self.s.queue.empty())
        await self.s.deactivate();self.s.trigger(b'{}');self.assertTrue(self.s.queue.empty())
    async def test_dequeued_message_generation_checked_under_execution_lock(self):
        await self.activate();generation=self.s.transport_generation
        async with self.s.lock:
            pending=asyncio.create_task(self.s.run_request_payload('{"request_id":"old","data":0}',generation))
            await asyncio.sleep(0);await self.s.disconnect()
        with patch('app.actions.MQTT') as mqtt:
            self.assertIsNone(await pending);mqtt.assert_not_called()
        self.assertNotIn('old',self.s.jobs)
    async def test_unknown_delivery_after_restart(self):
        await self.activate();await self.send(42)
        self.s.jobs['one']['delivery']='pending';self.s.store.write('action-jobs.json',self.s.jobs)
        self.s.last['delivery']='pending';self.s.store.write('action-last.json',self.s.last)
        restored=Studio(self.tmp.name).get('echo');self.assertEqual(restored.jobs['one']['delivery'],'unknown');self.assertEqual(restored.last['delivery'],'unknown')
    async def test_legacy_files_preserved_without_conversion(self):
        root=Store(self.tmp.name+'/legacy');root.write('agents.json',{'agents':[{'id':'old','name':'Old'}]});path=Store(root.root/'agents'/'old');original={'draft':{'steps':[]},'active':{'steps':[]}};path.write('workflow.json',original);path.write('identity.json',{'prefix':'stable','device_id':'stable'})
        legacy=Studio(root.root).get('old');self.assertFalse(legacy.supported);self.assertFalse(legacy.enabled);self.assertEqual(path.read('workflow.json'),original);self.assertFalse((path.root/'action-config.json').exists());self.assertEqual(legacy.identity['prefix'],'stable')
        with patch('app.actions.MQTT') as mqtt:await legacy.publish();mqtt.assert_not_called()
    async def test_delete_preserves_files_reserves_id_and_restart(self):
        await self.activate();await self.send(42);before=self.s.store.read('action-jobs.json')
        await self.studio.delete({'id':'echo','confirmed':True});self.assertEqual(self.s.store.read('action-jobs.json'),before)
        restored=Studio(self.tmp.name);self.assertEqual(restored.list()['actions'],[])
        with self.assertRaises(Invalid):await restored.create({'id':'echo','name':'Again','type':'echo'})
    async def test_action_request_namespaces_are_isolated(self):
        await self.activate();await self.send(0,'same')
        await self.studio.create({'id':'second','name':'Second','type':'echo'});other=self.studio.get('second')
        config=copy.deepcopy(self.conf);config['input']['topic']='second/request';await other.save(config,True)
        with patch('app.actions.MQTT'):
            result=await other.run_request_payload('{"request_id":"same","data":false}')
        self.assertIs(result['data'],False);self.assertEqual(self.s.jobs['same']['result']['data'],0)
    async def test_busy_mutations_and_failed_delete_commit(self):
        async with self.s.lock:
            with self.assertRaises(Invalid):await self.s.save(self.conf,True)
            with self.assertRaises(Invalid):await self.s.deactivate()
            with self.assertRaises(Invalid):await self.studio.delete({'id':'echo','confirmed':True})
        with patch.object(self.studio.store,'write',side_effect=OSError()):
            with self.assertRaises(OSError):await self.studio.delete({'id':'echo','confirmed':True})
        self.assertIs(self.studio.get('echo'),self.s)
    async def test_secrets_and_broker_reference_guard(self):
        self.assertNotIn('private-',json.dumps(self.studio.brokers.public()));await self.s.save(self.conf,False)
        with self.assertRaises(Invalid):await self.studio.brokers.delete({'id':self.a,'confirmed':True})
        await self.studio.brokers.save(broker()|{'id':self.a,'username':None,'password':None})
        self.assertEqual(Studio(self.tmp.name).brokers.get(self.a)['settings']['mqtt']['password'],'private-password')
    async def test_discovery_only_after_success(self):
        with patch.dict(os.environ,{'SUPERVISOR_TOKEN':'secret'}),patch('app.brokers.credentials',side_effect=OSError()):
            self.assertIsNone((await self.studio.brokers.refresh())['default_id'])
        with patch.dict(os.environ,{'SUPERVISOR_TOKEN':'secret'}),patch('app.brokers.credentials',return_value={'host':'ha','port':1883,'username':'private-user','password':'private-password'}):
            result=await self.studio.brokers.refresh();self.assertEqual(result['default_id'],'home-assistant');self.assertNotIn('private-',json.dumps(result))
        self.assertNotIn('home-assistant',self.studio.store.read('brokers.json'))

class API(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.client=TestClient(TestServer(create_app(self.tmp.name,dev=True)));await self.client.start_server()
    async def asyncTearDown(self):await self.client.close();self.tmp.cleanup()
    async def post(self,path,body):return await self.client.post(path,json=body,headers={'X-HA-AI-Studio-Request':'1'})
    async def test_create_test_deactivate_delete_and_removed_routes(self):
        response=await self.post('/api/actions',{'id':'echo','name':'Echo','type':'echo'});state=await response.json();self.assertEqual(response.status,200)
        result=await self.post('/api/test?id=echo',{'config':state['config']['draft'],'payload':'{"request_id":"test","data":null}'});self.assertIsNone((await result.json())['result']['data'])
        self.assertEqual((await self.post('/api/deactivate?id=echo',{})).status,200)
        for path in ('workflow','agents','run','calibration'):self.assertEqual((await self.client.get('/api/'+path)).status,404)
        self.assertEqual((await self.client.get('/action-types/echo/editor.js')).status,200);self.assertEqual((await self.client.get('/action-types/json_project/editor.js')).status,404)
        self.assertEqual((await self.post('/api/delete-action',{'id':'echo','confirmed':True})).status,200)
    async def test_boundary_and_relative_ingress_assets(self):
        self.assertEqual((await self.client.post('/api/actions',json={})).status,403)
        html=await (await self.client.get('/')).text();self.assertIn('src="static/app.js"',html)
        js=await (await self.client.get('/static/app.js')).text();self.assertIn("new URL('api/'+action,document.baseURI)",js);self.assertIn('../action-types/${type}/editor.js',js)
