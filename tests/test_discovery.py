import copy
import json
import tempfile
import unittest
from unittest.mock import patch
from app.actions import Studio
from app.discovery import DEFAULT
from app.domain import Invalid
from test_actions import broker


class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Historical instances: temporarily expose the old type only in this fixture.
        from app.action_types import TYPES
        legacy_catalog=patch("app.actions.CATALOG",[TYPES["echo"].metadata]);legacy_catalog.start();self.addCleanup(legacy_catalog.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.studio = Studio(self.tmp.name)
        self.broker = (await self.studio.brokers.save(broker()))['brokers'][0]['id']
        self.d = self.studio.discovery
        self.config = {**DEFAULT, 'enabled': True, 'broker_id': self.broker}

    async def asyncTearDown(self):
        await self.studio.close()
        self.tmp.cleanup()

    async def test_optional_no_actions_and_explicit_selection(self):
        with patch('app.discovery.MQTT') as mqtt:
            await self.d.reconcile();mqtt.assert_not_called()
        with self.assertRaises(Invalid):await self.d.save({**DEFAULT,'enabled':True})
        await self.d.save(self.config)
        desired=self.d.desired()
        configs=[p for t,p in desired.items() if t.endswith('/config')]
        self.assertEqual(len(configs),1)
        self.assertEqual(configs[0]['device']['name'],'HA AI Studio · '+self.studio.instance_id)
        self.assertEqual(desired[self.studio.namespace+'/discovery/active_actions'],'0')

    async def test_instance_identity_persists_and_isolates_installations(self):
        await self.studio.create({'id':'same','name':'Same action','type':'echo'})
        initial=self.d.desired()
        restored=Studio(self.tmp.name)
        self.assertEqual(restored.instance_id,self.studio.instance_id)
        self.assertEqual(restored.discovery.desired(),initial)
        self.assertEqual(restored.discovery.public()['instance_id'],self.studio.instance_id)
        with tempfile.TemporaryDirectory() as other_root:
            other=Studio(other_root)
            await other.create({'id':'same','name':'Same action','type':'echo'})
            self.assertNotEqual(other.instance_id,self.studio.instance_id)
            self.assertTrue(set(initial).isdisjoint(other.discovery.desired()))
            own=[v for k,v in initial.items() if k.endswith('/config')]
            foreign=[v for k,v in other.discovery.desired().items() if k.endswith('/config')]
            self.assertTrue({v['unique_id'] for v in own}.isdisjoint(v['unique_id'] for v in foreign))
            self.assertTrue({tuple(v['device']['identifiers']) for v in own}.isdisjoint(tuple(v['device']['identifiers']) for v in foreign))
            for v in own:self.assertIn(self.studio.instance_id,v['device']['name'])
            for v in foreign:self.assertIn(other.instance_id,v['device']['name'])
            await other.close()
        await restored.close()

    async def test_existing_installation_adopts_identity_without_changing_routes(self):
        original={'prefix':'studio_existing','device_id':'original-device'}
        self.studio.store.write('identity.json',original)
        restored=Studio(self.tmp.name)
        self.assertEqual(restored.instance_id,original['prefix'])
        saved=restored.store.read('identity.json')
        self.assertEqual(saved,{**original,'instance_id':original['prefix']})
        desired=restored.discovery.desired()
        entity=desired['homeassistant/sensor/studio_existing/active_actions/config']
        self.assertEqual(entity['unique_id'],'studio_existing_active_actions')
        self.assertEqual(entity['device']['identifiers'],['original-device'])
        self.assertEqual(Studio(self.tmp.name).instance_id,restored.instance_id)
        await restored.close()

    async def test_stable_ids_rename_legacy_and_diagnostics(self):
        await self.studio.create({'id':'echo','name':'First','type':'echo'})
        service=self.studio.get('echo');prefix=service.identity['prefix']
        first=self.d.desired();keys=set(first)
        config=copy.deepcopy(service.config['draft']);config['name']='Renamed'
        await service.save(config,False)
        second=self.d.desired();self.assertEqual(keys,set(second))
        entity=second[f'homeassistant/sensor/{prefix}/status/config']
        self.assertEqual(entity['unique_id'],prefix+'_status')
        self.assertEqual(entity['device']['via_device'],self.studio.store.read('identity.json')['device_id'])
        self.assertTrue(entity['device']['name'].endswith('Renamed'))
        self.assertEqual(second[prefix+'/status'],'disabled')
        service.config.update(enabled=True,active=config)
        service.last={'execution':'success','delivery':'failed','request_id':'PRIVATE','data':'PRIVATE'}
        desired=self.d.desired();self.assertEqual(desired[prefix+'/status'],'success');self.assertEqual(desired[prefix+'/delivery'],'failed')
        self.assertNotIn('PRIVATE',json.dumps(desired))
        service.running=True;self.assertEqual(self.d.desired()[prefix+'/status'],'running');service.running=False
        await service.test(config,'{"request_id":"UI","data":"PRIVATE"}')
        self.assertEqual(self.d.desired(),desired)
        restored=Studio(self.tmp.name);self.assertEqual(restored.get('echo').identity['prefix'],prefix)
        service.supported=False;self.assertNotIn(prefix+'/status',self.d.desired())

    async def test_ownership_before_publish_and_cleanup(self):
        await self.d.save(self.config)
        calls=[]
        def publish(topic,payload,**kwargs):
            owned=self.studio.store.read('discovery.json')['owned']
            self.assertTrue(any(topic in i['topics'] for i in owned))
            calls.append((topic,payload,kwargs))
        with patch('app.discovery.MQTT') as transport:
            transport.return_value.publish.side_effect=publish
            await self.d.reconcile()
            self.assertTrue(calls)
            self.assertTrue(all(k['retain'] for _,_,k in calls))
            await self.d.save({**DEFAULT})
            await self.d.reconcile()
        self.assertEqual(self.d.data['owned'],[])
        self.assertTrue(any(p=='' for _,p,_ in calls))

    async def test_pending_cleanup_survives_restart_and_guards_broker(self):
        await self.d.save(self.config)
        with patch('app.discovery.MQTT'):await self.d.reconcile()
        await self.d.save(dict(DEFAULT))
        with patch('app.discovery.MQTT') as transport:
            transport.return_value.connect.side_effect=OSError('SECRET')
            with self.assertRaises(OSError):await self.d.reconcile()
        restored=Studio(self.tmp.name)
        self.assertGreater(restored.discovery.public()['pending_cleanup'],0)
        with self.assertRaises(Invalid):await restored.brokers.delete({'id':self.broker,'confirmed':True})
        edited={**broker('different'),'id':self.broker}
        with self.assertRaises(Invalid):await restored.brokers.save(edited)
        self.assertNotIn('SECRET',json.dumps(restored.discovery.public()))
        with patch('app.discovery.MQTT'):await restored.discovery.reconcile()
        await restored.brokers.delete({'id':self.broker,'confirmed':True})

    async def test_delete_only_owned_topics_and_switch(self):
        await self.studio.create({'id':'echo','name':'First','type':'echo'})
        prefix=self.studio.get('echo').identity['prefix']
        await self.d.save(self.config)
        with patch('app.discovery.MQTT') as transport:
            await self.d.reconcile()
            await self.studio.delete({'id':'echo','confirmed':True});await self.d.reconcile()
            deleted=[c.args[0] for c in transport.return_value.publish.call_args_list if c.args[1]=='']
            self.assertEqual(set(deleted),{f'homeassistant/sensor/{prefix}/status/config',f'homeassistant/sensor/{prefix}/delivery/config',prefix+'/status',prefix+'/delivery'})
            before=set(self.studio.brokers.all());await self.studio.brokers.save(broker('second'));other=(set(self.studio.brokers.all())-before).pop()
            await self.d.save({**self.config,'broker_id':other});await self.d.reconcile()
            self.assertEqual({i['broker_id'] for i in self.d.data['owned']},{other})

    async def test_prefix_validation_and_legacy_identity_preserved(self):
        for prefix in ('','homeassistant/#','$SYS','bad\n'):
            with self.assertRaises(Invalid):await self.d.save({**self.config,'prefix':prefix})
        await self.studio.create({'id':'old','name':'Old','type':'echo'})
        service=self.studio.get('old');service.store.write('identity.json',{'prefix':'existing','device_id':'existing-device'})
        restored=Studio(self.tmp.name)
        entity=restored.discovery.desired()['homeassistant/sensor/existing/status/config']
        self.assertEqual(entity['unique_id'],'existing_status')
        self.assertEqual(entity['device']['identifiers'],['existing-device'])

    async def test_persistence_failure_never_authorizes_publication(self):
        before=copy.deepcopy(self.d.data)
        with patch.object(self.d.store,'write',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):await self.d.save(self.config)
        self.assertEqual(self.d.data,before)
        await self.d.save(self.config)
        original=self.d.store.write
        def fail_manifest(name,value):
            if name=='discovery.json':raise OSError('disk full')
            original(name,value)
        with patch('app.discovery.MQTT') as transport:
            with patch.object(self.d.store,'write',side_effect=fail_manifest):
                with self.assertRaises(OSError):await self.d.reconcile()
            transport.return_value.publish.assert_not_called()
            self.assertEqual(self.d.data['owned'],[])
            await self.d.reconcile()
            self.assertTrue(self.d.store.read('discovery.json')['owned'])

    async def test_discovery_route_collisions_and_stale_processing(self):
        await self.studio.create({'id':'echo','name':'Echo','type':'echo'})
        service=self.studio.get('echo');prefix=service.identity['prefix']
        config=copy.deepcopy(service.config['draft'])
        config['input']['broker_id']=self.broker
        config['output'].update(broker_id=self.broker,topic=prefix+'/status')
        await service.save(config,True)
        with self.assertRaises(Invalid):await self.d.save(self.config)
        await service.deactivate();await self.d.save(self.config)
        with self.assertRaises(Invalid):await service.save(config,True)
        with self.assertRaises(Invalid):await self.d.save({**self.config,'ha_status_topic':self.studio.namespace+'/discovery/availability'})
        config['output']['topic']='safe/result';await service.save(config,True)
        service.last={'execution':'processing','delivery':'not_sent'}
        self.assertEqual(self.d.desired()[prefix+'/status'],'interrupted')

    async def test_cleanup_connection_survives_missing_supervisor(self):
        await self.d.save(self.config)
        with patch('app.discovery.MQTT'):await self.d.reconcile()
        # Simulate a disappeared discovered registry item after a restart.
        self.studio.brokers.manual.pop(self.broker)
        await self.d.save({**self.config,'enabled':False})
        with patch('app.discovery.MQTT') as transport:
            await self.d.reconcile()
            self.assertEqual(transport.return_value.connect.call_args.args[0]['mqtt']['host'],'broker')
        self.assertEqual(self.d.data['owned'],[])
        self.assertEqual(self.studio.brokers.cleanup_connections,{})

    async def test_legacy_migration_and_custom_prefix_partial_publish(self):
        for id in ('first','second'):
            await self.studio.create({'id':id,'name':id,'type':'echo'})
            service=self.studio.get(id);config=copy.deepcopy(service.config['draft'])
            config['input']['broker_id']=self.broker
            await service.save(config,True)
        # Simulate upgrade from a pre-manifest version; preserve stored identities.
        (self.studio.store.root/'discovery.json').unlink()
        restored=Studio(self.tmp.name);manager=restored.discovery
        self.assertTrue(manager.public()['legacy_pending'])
        with patch('app.discovery.MQTT') as transport:
            await manager.reconcile();transport.assert_not_called()
            await manager.save(self.config)
            transport.return_value.publish.side_effect=OSError('partial publish')
            with self.assertRaises(OSError):await manager.reconcile()
        restarted=Studio(self.tmp.name);manager=restarted.discovery
        with patch('app.discovery.MQTT') as transport:
            await manager.save({**self.config,'prefix':'custom-ha'})
            await manager.reconcile()
            configs=[topic for item in manager.data['owned'] for topic in item['topics'] if topic.endswith('/config')]
            self.assertTrue(configs);self.assertTrue(all(t.startswith('custom-ha/') for t in configs))
            self.assertEqual(len(set(configs)),5)

    async def test_saved_retry_route_blocks_discovery_collision(self):
        await self.studio.create({'id':'echo','name':'Echo','type':'echo'})
        service=self.studio.get('echo');config=copy.deepcopy(service.config['draft'])
        config['input']['broker_id']=self.broker
        config['output'].update(broker_id=self.broker,topic=service.identity['prefix']+'/delivery')
        service.jobs={'old':{'config':config}}
        with self.assertRaises(Invalid):await self.d.save(self.config)
