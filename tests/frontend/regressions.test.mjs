import test from 'node:test';
import assert from 'node:assert/strict';
import {mqttTestAutomationYaml} from '../../ha_ai_studio/app/static/ha-example.js';
import {render} from '../../ha_ai_studio/app/static/schema-editor.js';

// Minimal DOM substitute: tests execute the real editor and application handlers.
// Browser layout and accessibility are checked separately in the embedded browser.
class Element {
 constructor(tag='div'){this.tag=tag;this.children=[];this.attributes={};this.handlers={};this.value='';this.hidden=true;this.disabled=false;this.open=false;this.textContent='';this.dataset={};}
 append(...items){this.children.push(...items);}
 replaceChildren(...items){this.children=[...items];}
 setAttribute(key,value){this.attributes[key]=value;}
 removeAttribute(key){delete this.attributes[key];}
 addEventListener(name,handler){this.handlers[name]=handler;}
 showModal(){this.open=true;this.hidden=false;}
 close(){this.open=false;this.handlers.close?.();}
}
function documentStub(){
 const nodes=new Map();
 const document={baseURI:'http://example.invalid/',getElementById(id){if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);},
  createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),createTextNode:text=>({textContent:text}),
  querySelectorAll:()=>[],querySelector:()=>null};
 document.getElementById('actions').hidden=false;
 return document;
}
function numericEditor(settings,required=[]){
 globalThis.document=documentStub();const host=new Element();
 const read=render(host,settings,{changed(){}},{type:'object',additionalProperties:false,required,properties:{limit:{type:'integer',title:'Limit'}}});
 return {read,input:host.children[1].children[0]};
}
test('clearing an optional number removes it rather than saving zero',()=>{
 const {read,input}=numericEditor({limit:7});input.value='';input.oninput();assert.deepEqual(read(),{});
});
test('zero is preserved and absent optional numbers stay absent',()=>{
 let editor=numericEditor({limit:0});assert.deepEqual(editor.read(),{limit:0});
 editor=numericEditor({});assert.deepEqual(editor.read(),{});
});
test('required, fractional, nonfinite and malformed numbers are rejected',()=>{
 let editor=numericEditor({},['limit']);assert.throws(editor.read,/Limit is required/);
 editor=numericEditor({limit:7});editor.input.value='';assert.deepEqual(editor.read(),{});
 for(const value of ['1.2','Infinity','invalid']){editor.input.value=value;assert.throws(editor.read,/valid integer/);}
 editor.input.value='';editor.input.validity={badInput:true};assert.throws(editor.read,/valid number/);
});

async function application(example=null){
 const document=documentStub(),requests=[],polls=[];
 const value={definition:{id:'fixture',name:'Fixture',type:'git-fixture'},plugin:{dynamic:true,version:'1',commit:'a'.repeat(40),example,input_schema:{},output_schema:{},settings_schema:{type:'object',additionalProperties:false}},
  environment:{status:'Ready',logs:['Environment is ready.']},issues:[],supported:true,enabled:false,busy:false,config:{draft:{name:'Fixture',settings:{},input:{broker_id:null,topic:'fixture/request'},output:{broker_id:null,topic:'fixture/result'}}}};
 let operationError=null,statusError=null;
 globalThis.document=document;globalThis.window={addEventListener(){}};globalThis.location={hash:'#actions'};globalThis.history={replaceState(){}};
 globalThis.fetch=async(url,options)=>{
  const parsed=new URL(url);requests.push({path:parsed.pathname,id:parsed.searchParams.get('id'),options});
  if(parsed.pathname==='/api/brokers')return {ok:true,json:async()=>({brokers:[]})};
  if(parsed.pathname==='/api/actions')return {ok:true,json:async()=>({types:[],actions:[structuredClone(value)]})};
  const error=parsed.pathname==='/api/environment'?operationError:statusError;
  return {ok:!error,json:async()=>error?{error}:structuredClone(value)};
 };
 const interval=globalThis.setInterval;globalThis.setInterval=callback=>{polls.push(callback);return 0;};
 try{await import(new URL(`../../ha_ai_studio/app/static/app.js?case=${Math.random()}`,import.meta.url));}
 finally{globalThis.setInterval=interval;}
 await new Promise(resolve=>setImmediate(resolve));
 const row=document.getElementById('action-rows').children[0];
 const button=row.children.at(-1).children.find(el=>el.attributes['aria-label']==='Installation details Fixture');
 await button.onclick();
 return {get:id=>document.getElementById(id),openEditor:async()=>{document.getElementById('environment-panel').close();await row.children.at(-1).children.find(el=>el.attributes['aria-label']==='Edit Fixture').onclick();},requests,poll:polls[0],operationError:error=>{operationError=error;},statusError:error=>{statusError=error;}};
}
test('rebuild failure is visible inside the open panel and survives polling',async()=>{
 const app=await application();app.operationError('Environment rebuild failed.');
 await app.get('environment-rebuild').onclick();
 assert.equal(app.get('environment-panel').open,true);
 assert.equal(app.get('environment-error').hidden,false);
 assert.equal(app.get('environment-error').textContent,'Environment rebuild failed.');
 assert.equal(app.get('message').textContent,'');
 assert.equal(app.requests.at(-1).id,'fixture');
 await app.poll();assert.equal(app.get('environment-error').textContent,'Environment rebuild failed.');
 app.operationError(null);await app.get('environment-rebuild').onclick();assert.equal(app.get('environment-error').hidden,true);
});
test('manual and background refresh errors appear in the panel and recover',async()=>{
 const app=await application();app.statusError('Installation status unavailable.');
 await app.get('environment-refresh').onclick();assert.equal(app.get('environment-error').textContent,'Installation status unavailable.');
 app.statusError(null);await app.get('environment-refresh').onclick();assert.equal(app.get('environment-error').hidden,true);
 app.statusError('Connection interrupted.');await app.poll();assert.equal(app.get('environment-error').textContent,'Connection interrupted.');
 app.statusError(null);await app.poll();assert.equal(app.get('environment-error').hidden,true);
 app.get('environment-panel').close();assert.equal(app.get('environment-panel').open,false);
});

test('HA test template is unavailable without a valid example',async()=>{
 const app=await application();await app.openEditor();
 assert.equal(app.get('ha-example').disabled,true);
 assert.match(app.get('ha-example').title,/No valid example/);
 app.get('ha-example').onclick();assert.equal(app.get('ha-example-panel').open,false);
});
test('valid zero-valued example enables HA test template',async()=>{
 const app=await application({request_id:'example',data:0});await app.openEditor();
 assert.equal(app.get('ha-example').disabled,false);
 app.get('ha-example').onclick();assert.equal(app.get('ha-example-panel').open,true);
 assert.match(app.get('ha-example-yaml').value,/mqtt.publish/);
});
test('template generator refuses missing examples and preserves null/false/zero',()=>{
 const config={name:'Fixture',input:{topic:'fixture/request'},output:{topic:'fixture/result'}};
 for(const example of [null,undefined,{},[],{request_id:'one'}])assert.throws(()=>mqttTestAutomationYaml(config,example),/No valid example/);
 for(const value of [null,false,0]){
  const yaml=mqttTestAutomationYaml(config,{request_id:'one',data:value});
  assert.ok(yaml.includes(JSON.stringify(JSON.stringify({data:value}))));
 }
});
