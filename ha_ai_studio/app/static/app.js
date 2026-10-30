import {mqttTestAutomationYaml} from './ha-example.js';
const $=id=>document.getElementById(id);
let current=null,state=null,dirty=false,busy=false,readSettings=null,brokerData=null,catalog=[],deleteTarget=null;
let brokerEditing=null,brokerDeleteTarget=null,leaveDestination='actions',discoveryDirty=false;
let discoveryData=null;
const modules=new Map();
function renderJson(id,value){
 const code=$(id),source=JSON.stringify(value,null,2);code.replaceChildren();
 const tokens=/"(?:\\.|[^"\\])*"(?=\s*:)|"(?:\\.|[^"\\])*"|\b(?:true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[{}\[\],:]/g;
 let offset=0;
 for(const match of source.matchAll(tokens)){
  code.append(document.createTextNode(source.slice(offset,match.index)));
  const token=document.createElement('span'),text=match[0];
  const kind=text.startsWith('"')?(/^\s*:/.test(source.slice(match.index+text.length))?'key':'string'):/^(true|false|null)$/.test(text)?'literal':/^-?\d/.test(text)?'number':'punctuation';
  token.className='json-'+kind;token.textContent=text;code.append(token);offset=match.index+text.length;
 }
 code.append(document.createTextNode(source.slice(offset)));
}
function iconButton(kind,label){
 const paths={live:'M3 3h18v18H3V3zm3 4v2h12V7H6zm0 4v2h8v-2H6zm0 4v2h12v-2H6z',test:'M8 5v14l11-7z',edit:'M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z',delete:'M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z'};
 const button=document.createElement('button');button.className='icon-button'+(kind==='delete'?' danger':'');button.title=label;button.setAttribute('aria-label',label);
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');svg.setAttribute('focusable','false');const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',paths[kind]);svg.append(path);button.append(svg);return button;
}
async function api(action,body){
 const url=new URL('api/'+action,document.baseURI);if(current)url.searchParams.set('id',current);
 const response=await fetch(url,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json','X-HA-AI-Studio-Request':'1'},body:body===undefined?undefined:JSON.stringify(body)});
 const data=await response.json();if(!response.ok)throw Error(data.error||'Request failed.');return data;
}
function message(text,error=false){$('message').textContent=text;$('message').hidden=!text;$('message').className=error?'error':'';}
async function action(fn){if(busy)return;busy=true;sync();try{await fn();}catch(error){message(error.message,true);}finally{busy=false;sync();}}
function sync(){
 for(const id of ['save','schemas','create','back','nav-actions','nav-settings','add-broker','refresh-brokers','discovery-refresh'])$(id).disabled=busy;
 $('ha-example').disabled=busy||!state?.supported;
 $('save').disabled||=!state?.supported;$('schemas').disabled||=!state?.supported;
 $('config-fields').inert=busy;$('discovery-form').inert=busy;
 document.querySelectorAll('dialog input,dialog select,dialog button').forEach(el=>el.disabled=busy);
 if(state)$('config-status').textContent=state.supported?(dirty?'Unsaved changes':''):'Unsupported legacy action · Disabled';
}
function changed(){dirty=true;sync();}
function readDraft(){return {name:$('action-name').value,input:{broker_id:$('input-broker').value||null,topic:$('input-topic').value},settings:readSettings?readSettings():{},output:{broker_id:$('output-broker').value||null,topic:$('output-topic').value}};}
function setNav(page){for(const id of ['actions','settings']){if(id===page)$('nav-'+id).setAttribute('aria-current','page');else $('nav-'+id).removeAttribute('aria-current');}}
async function list(){
 const data=await api('actions');catalog=data.types;
 $('action-rows').replaceChildren();$('empty').hidden=!!data.actions.length;
 for(const item of data.actions){const row=document.createElement('tr');for(const text of [item.definition.name,item.plugin?.name||'Legacy workflow',!item.supported?'Unsupported · Disabled':item.busy?'Busy':item.enabled?'Active':'Inactive']){const cell=document.createElement('td');cell.textContent=text;row.append(cell);}
 const cell=document.createElement('td');cell.className='row-actions';const edit=iconButton('edit','Edit '+item.definition.name);edit.onclick=()=>action(()=>openAction(item.definition.id));const remove=iconButton('delete','Delete '+item.definition.name);remove.disabled=item.busy;remove.onclick=()=>{if(busy)return;deleteTarget=item.definition;$('delete-description').textContent=`Delete “${deleteTarget.name}”?`;$('delete-error').textContent='';$('delete-panel').showModal();};const live=iconButton('live','Live activity '+item.definition.name);live.onclick=()=>action(()=>openLive(item.definition.id,item.definition.name));cell.append(live,edit,remove);row.append(cell);$('action-rows').append(row);}
 return data;
}
function brokerOptions(id,value,same){const select=$(id);select.replaceChildren();const blank=document.createElement('option');blank.value='';blank.textContent=same?'Same as input':'Select a broker';select.append(blank);for(const b of brokerData.brokers){const option=document.createElement('option');option.value=b.id;option.textContent=b.name+(b.id===brokerData.default_id?' · HA default':'');select.append(option);}if(value&&!brokerData.brokers.some(b=>b.id===value)){const option=document.createElement('option');option.value=value;option.textContent='Unavailable broker';select.append(option);}select.value=value||'';}
async function openAction(id){stopLive();
 current=id;state=await api('action');brokerData=await api('brokers');dirty=false;readSettings=null;
 $('actions').hidden=true;$('settings-page').hidden=true;$('editor').hidden=false;setNav('actions');$('action-title').textContent=state.definition.name;
 $('config-error').textContent=state.issues.join(' ');$('config-error').hidden=!state.issues.length;$('config-fields').hidden=!state.supported;
 if(state.supported){const draft=state.config.draft;$('action-name').value=draft.name;$('action-active').checked=state.enabled;brokerOptions('input-broker',draft.input.broker_id,false);brokerOptions('output-broker',draft.output.broker_id,true);$('input-topic').value=draft.input.topic;$('output-topic').value=draft.output.topic;
 $('type-editor').replaceChildren();const type=state.definition.type;if(!modules.has(type))modules.set(type,await import(new URL(`../action-types/${type}/editor.js`,import.meta.url)));readSettings=modules.get(type).render($('type-editor'),structuredClone(draft.settings),{changed});
 renderJson('input-schema',state.plugin.input_schema);renderJson('output-schema',state.plugin.output_schema);}
 history.replaceState(null,'',`#actions/${encodeURIComponent(id)}`);message('');
}
for(const id of ['action-name','action-active','input-broker','output-broker','input-topic','output-topic'])$(id).addEventListener('input',changed);
async function save(){const config=readDraft();const enabled=$('action-active').checked;state=await api('action',{config,enabled});dirty=false;await openAction(current);message(enabled?'Action saved. Active.':'Action saved. Inactive.');}
$('save').onclick=()=>action(save);
$('schemas').onclick=()=>{if(!busy&&state?.supported)$('schemas-panel').showModal();};
for(const id of ['close-schemas','done-schemas'])$(id).onclick=()=>$('schemas-panel').close();
$('create').onclick=()=>{if(busy)return;$('create-form').reset();$('new-type').replaceChildren();for(const type of catalog){const option=document.createElement('option');option.value=type.type;option.textContent=type.name;$('new-type').append(option);}$('create-error').textContent='';$('create-panel').showModal();};
$('close-create').onclick=()=>{if(!busy)$('create-panel').close();};
$('create-form').onsubmit=event=>{event.preventDefault();action(async()=>{try{const name=$('new-name').value.trim();const slug=name.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,36);const id=(/^[a-z]/.test(slug)?slug:'action')+'-'+crypto.randomUUID().slice(0,8);await api('actions',{id,name,type:$('new-type').value});$('create-panel').close();await openAction(id);}catch(error){$('create-error').textContent=error.message;}});};
async function leave(){stopLive();current=null;state=null;dirty=false;discoveryDirty=false;readSettings=null;$('editor').hidden=true;$('actions').hidden=leaveDestination==='settings';$('settings-page').hidden=leaveDestination!=='settings';history.replaceState(null,'','#'+leaveDestination);setNav(leaveDestination);message('');if(leaveDestination==='settings')await showSettings();else await list();}
function navigate(page){if(busy)return;leaveDestination=page;if(dirty)$('leave-panel').showModal();else action(leave);}
$('back').onclick=()=>navigate('actions');$('nav-actions').onclick=()=>navigate('actions');$('nav-settings').onclick=()=>navigate('settings');$('keep-editing').onclick=()=>$('leave-panel').close();$('discard').onclick=()=>{$('leave-panel').close();action(leave);};
window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
window.addEventListener('hashchange',()=>navigate(location.hash==='#settings'?'settings':'actions'));
for(const id of ['close-delete','cancel-delete'])$(id).onclick=()=>{if(!busy)$('delete-panel').close();};
for(const dialog of document.querySelectorAll('dialog'))dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault();});
$('confirm-delete').onclick=()=>action(async()=>{try{await api('delete-action',{id:deleteTarget.id,confirmed:true});$('delete-panel').close();await list();message('Action deleted. Original files and IDs were preserved.');}catch(error){$('delete-error').textContent=error.message;}});
async function showSettings(){stopLive();
 $('actions').hidden=true;$('editor').hidden=true;$('settings-page').hidden=false;setNav('settings');history.replaceState(null,'','#settings');
 const data=await api('brokers');brokerData=data;discoveryData=await api('discovery');$('broker-rows').replaceChildren();$('no-brokers').hidden=!!data.brokers.length;
 for(const broker of data.brokers){
  const row=document.createElement('tr');
  for(const text of [broker.name,`${broker.host}:${broker.port}${broker.tls?' · TLS':''}`,broker.source==='supervisor'?'Home Assistant · default':broker.source==='environment'?'.env':'Manual',discoveryData.config.broker_id===broker.id&&discoveryData.config.enabled?'Enabled':'Disabled']){const cell=document.createElement('td');cell.textContent=text;row.append(cell);}
  const actions=document.createElement('td');actions.className='row-actions';
  const test=iconButton('test','Test '+broker.name);test.onclick=()=>testBroker(broker);actions.append(test);
  const edit=iconButton('edit','Edit broker '+broker.name);edit.onclick=()=>editBroker(broker);actions.append(edit);
  if(broker.editable){
   const remove=iconButton('delete','Delete broker '+broker.name);remove.onclick=()=>{brokerDeleteTarget=broker;$('broker-delete-name').textContent=`Delete “${broker.name}”?`;$('broker-delete-error').textContent='';$('broker-delete-panel').showModal();};actions.append(remove);}
  row.append(actions);$('broker-rows').append(row);
 }
}
function editBroker(broker=null){if(busy)return;brokerEditing=broker;$('broker-form').reset();$('broker-title').textContent=broker?'Edit broker':'Add broker';$('broker-name').value=broker?.name||'';$('broker-host').value=broker?.host||'';$('broker-port').value=broker?.port||1883;$('broker-tls').checked=broker?.tls||false;$('broker-secrets').textContent=broker?`Username ${broker.secrets.username?'stored':'not set'} · Password ${broker.secrets.password?'stored':'not set'}`:'';$('broker-error').textContent='';const readonly=!!broker&&!broker.editable;$('broker-connection').disabled=readonly;discoveryDirty=false;renderDiscovery();$('broker-panel').showModal();}
$('add-broker').onclick=()=>editBroker();$('close-broker').onclick=()=>{if(!busy)$('broker-panel').close();};
$('broker-panel').addEventListener('cancel',event=>{if(busy)event.preventDefault();});
$('broker-form').onsubmit=event=>{event.preventDefault();action(async()=>{try{
 const value={id:brokerEditing?.id||null,name:$('broker-name').value,host:$('broker-host').value,port:Number($('broker-port').value),tls:$('broker-tls').checked};
 for(const key of ['username','password'])value[key]=$('broker-clear').checked?'':$('broker-'+key).value||null;
 const enabled=$('discovery-enabled').checked;
 const discovery={enabled,broker_id:brokerEditing?.id||null,prefix:$('discovery-prefix').value,ha_status_topic:$('discovery-ha-status').value};
 for(const text of [discovery.prefix,discovery.ha_status_topic])if(!text||new TextEncoder().encode(text).length>128||text.startsWith('$')||/[#+\x00-\x1f]/.test(text)||text.endsWith('/'))throw Error('Use concrete discovery topics without wildcards or a trailing slash.');
 if(!brokerEditing||brokerEditing.editable){
  const previous=new Set(brokerData.brokers.map(b=>b.id));
  brokerData=await api('brokers',value);
  brokerEditing=brokerData.brokers.find(b=>value.id?b.id===value.id:!previous.has(b.id));
  if(!brokerEditing)throw Error('Broker saved, but could not reload its settings. Reopen the panel to configure discovery.');
 }
 if(enabled||discoveryData.config.broker_id===brokerEditing.id){
  discovery.broker_id=enabled?brokerEditing.id:null;
  try{discoveryData=await api('discovery',discovery);}catch(error){throw Error('Connection settings saved. Discovery settings were not saved: '+error.message);}
 }
 discoveryDirty=false;$('broker-panel').close();await showSettings();message('Broker settings saved.');
 }catch(error){$('broker-error').textContent=error.message;}});};
$('refresh-brokers').onclick=()=>action(async()=>{const data=await api('broker-refresh',{});await showSettings();message(data.default_id?'Home Assistant MQTT broker found.':'No Home Assistant MQTT service found. You can add a broker manually.');});
$('broker-delete-cancel').onclick=()=>{if(!busy)$('broker-delete-panel').close();};
$('broker-delete-confirm').onclick=()=>action(async()=>{try{await api('broker-delete',{id:brokerDeleteTarget.id,confirmed:true});$('broker-delete-panel').close();await showSettings();message('Broker deleted.');}catch(error){$('broker-delete-error').textContent=error.message;}});

action(async()=>{const route=location.hash.split('/');await list();if(route[0]==='#settings')await showSettings();else if(route[0]==='#actions'&&route[1]){if(route[2]==='live')await openLive(decodeURIComponent(route[1]));else await openAction(decodeURIComponent(route[1]));}else{history.replaceState(null,'','#actions');setNav('actions');}});

function discoveryStatus(data){
 $('discovery-status').textContent=data.status;
 $('discovery-status').hidden=!$('discovery-enabled').checked;
 $('discovery-cleanup').hidden=!data.pending_cleanup&&!data.legacy_pending;
 $('discovery-cleanup').textContent=data.legacy_pending?'Previous discovery records found. Save discovery settings to reconcile them.':`${data.pending_cleanup} owned messages awaiting cleanup. Keep the previous broker available; cleanup retries automatically before new discovery is published.`;
}
function renderDiscovery(){
 const data=discoveryData,c=data.config,selected=!!brokerEditing&&c.broker_id===brokerEditing.id;
 $('discovery-enabled').checked=selected&&c.enabled;
 $('discovery-refresh').hidden=!$('discovery-enabled').checked;
 $('discovery-prefix').value=c.prefix;$('discovery-ha-status').value=c.ha_status_topic;
 $('discovery-owner').textContent=!selected&&c.enabled?'Currently enabled on '+(brokerData.brokers.find(b=>b.id===c.broker_id)?.name||'another broker')+'. Enabling here moves discovery to this broker.':'';
 discoveryStatus(data);if(!selected)$('discovery-status').textContent='Discovery is disabled for this broker.';
}
$('discovery-refresh').onclick=()=>action(async()=>{discoveryData=await api('discovery');if(discoveryDirty)discoveryStatus(discoveryData);else renderDiscovery();});
for(const id of ['discovery-enabled','discovery-prefix','discovery-ha-status'])$(id).addEventListener('input',()=>{discoveryDirty=true;$('discovery-refresh').hidden=!$('discovery-enabled').checked;$('discovery-status').hidden=!$('discovery-enabled').checked;});

async function testBroker(broker){
 if(busy)return;
 $('broker-test-name').textContent=broker.name;
 $('broker-test-summary').dataset.state='pending';
 $('broker-test-status').textContent='Testing connection…';
 $('broker-test-status').className='';
 $('broker-test-log').textContent='Connecting from the app container. Waiting for diagnostic results…';
 $('broker-test-scope').textContent='No MQTT messages will be published. Credentials are hidden.';
 $('broker-test-panel').showModal();
 await action(async()=>{
  try{
   const result=await api('broker-test',{id:broker.id});
   $('broker-test-summary').dataset.state=result.ok?'success':'error';
   $('broker-test-status').textContent=result.message;
   $('broker-test-status').className=result.ok?'':'error';
   $('broker-test-log').textContent=result.logs.map(entry=>`[${(entry.elapsed_ms/1000).toFixed(2)}s] ${entry.message}`).join('\n');
   $('broker-test-scope').textContent=result.scope;
  }catch(error){$('broker-test-summary').dataset.state='error';$('broker-test-status').textContent=error.message;$('broker-test-status').className='error';$('broker-test-log').textContent='The diagnostic request could not be completed.';}
 });
}
$('close-broker-test').onclick=()=>{if(!busy)$('broker-test-panel').close();};

$('ha-example').onclick=()=>{
 if(busy||!state?.supported)return;
 const config=state.enabled?state.config.active:readDraft();
 const broker=brokerData.brokers.find(b=>b.id===config.input.broker_id);
 $('ha-example-source').textContent=state.enabled?'Uses the active configuration. Unsaved edits and draft changes are not included.':'Draft example. Save and activate this action before running the test.';
 $('ha-example-broker').textContent='Home Assistant must connect to the Input broker'+(broker?' “'+broker.name+'”.':'. Select an Input broker before activating.')+' mqtt.publish uses Home Assistant’s configured broker.'+(config.output.broker_id&&config.output.broker_id!==config.input.broker_id?' Output uses a different broker. HA can only receive the result if that topic is bridged to its MQTT broker.':'');
 $('ha-example-yaml').value=mqttTestAutomationYaml(config,state.plugin.example);
 $('ha-copy-status').textContent=config.input.topic&&config.output.topic?'':'Set Input and Result topics first.';
 $('copy-ha-example').disabled=!config.input.topic||!config.output.topic;
 $('ha-example-panel').showModal();
};
$('close-ha-example').onclick=()=>$('ha-example-panel').close();
$('copy-ha-example').onclick=async()=>{
 try{await navigator.clipboard.writeText($('ha-example-yaml').value);$('ha-copy-status').textContent='YAML copied.';}
 catch{ $('ha-example-yaml').focus();$('ha-example-yaml').select();$('ha-copy-status').textContent='Clipboard access is unavailable. Copy the selected YAML manually.'; }
};

let liveTimer=null,liveGeneration=0,livePaused=false,liveCursor=0,liveEpoch=null,liveEntries=[];
function stopLive(){liveGeneration++;clearTimeout(liveTimer);$('live-page').hidden=true;}
async function openLive(id,name){
 stopLive();current=id;dirty=false;liveCursor=0;liveEpoch=null;liveEntries=[];livePaused=false;
 $('live-pause').textContent='Pause';$('actions').hidden=true;$('editor').hidden=true;$('settings-page').hidden=true;$('live-page').hidden=false;
 $('live-title').textContent=(name||id)+' · Live activity';$('live-log').textContent='Waiting for MQTT messages…';setNav('actions');message('');
 history.replaceState(null,'',`#actions/${encodeURIComponent(id)}/live`);pollLive(liveGeneration,id);
}
async function pollLive(generation,id){
 if(generation!==liveGeneration||$('live-page').hidden)return;
 try{
  if(!livePaused){
   const url=new URL('api/live',document.baseURI);url.searchParams.set('id',id);url.searchParams.set('after',liveCursor);
   const response=await fetch(url);if(!response.ok)throw Error('Live activity unavailable. Retrying…');const data=await response.json();
   if(generation!==liveGeneration)return;
   if(livePaused){liveTimer=setTimeout(()=>pollLive(generation,id),1000);return;}
   if(liveEpoch&&data.epoch!==liveEpoch){liveCursor=0;liveEntries=[];liveEpoch=data.epoch;liveTimer=setTimeout(()=>pollLive(generation,id),0);return;}
   liveEpoch=data.epoch;liveCursor=data.cursor;liveEntries.push(...data.events);liveEntries=liveEntries.slice(-200);
   $('live-status').textContent=data.mqtt+' · Live'+(data.gap?' · Older events expired':'');
   const log=$('live-log'),follow=log.scrollHeight-log.scrollTop-log.clientHeight<48;
   log.textContent=liveEntries.map(e=>`[${e.timestamp}] ${e.kind.toUpperCase()}  ${e.message}${e.topic?'\n  Topic: '+e.topic:''}${e.payload!==undefined?'\n'+e.payload:''}${e.truncated?'\n[Payload truncated]':''}`).join('\n\n')||'Waiting for MQTT messages…';
   if(follow)log.scrollTop=log.scrollHeight;
  }
 }catch(error){if(generation===liveGeneration)$('live-status').textContent=error.message;}
 if(generation===liveGeneration)liveTimer=setTimeout(()=>pollLive(generation,id),1000);
}
$('live-back').onclick=()=>navigate('actions');
$('live-pause').onclick=()=>{livePaused=!livePaused;$('live-pause').textContent=livePaused?'Resume':'Pause';$('live-status').textContent=livePaused?'Display paused · Action continues running':'Resuming live activity…';};
