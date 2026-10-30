"""Common validation and private MQTT configuration."""
import copy
from datetime import datetime, timezone

class Invalid(ValueError):
    pass

def stamp():
    return datetime.now(timezone.utc).isoformat()

def defaults():
    return {'mqtt': {'mode':'supervisor','host':'','port':1883,'username':'','password':'','tls':False}}

def settings_check(value, previous, allow_unconfigured=False):
    if not isinstance(value,dict) or set(value)!={'mqtt'} or not isinstance(value['mqtt'],dict):
        raise Invalid('Provide MQTT settings.')
    conf=copy.deepcopy(value['mqtt'])
    if set(conf)!=set(defaults()['mqtt']):raise Invalid('Invalid MQTT settings fields.')
    if conf['mode'] not in ('manual','supervisor'):raise Invalid('Choose manual or Supervisor MQTT.')
    if type(conf['port']) is not int or not 1<=conf['port']<=65535:raise Invalid('MQTT port must be 1–65535.')
    if type(conf['tls']) is not bool:raise Invalid('TLS must be true or false.')
    for key in ('host','username','password'):
        if conf[key] is None and key in ('username','password'):conf[key]=previous['mqtt'][key]
        if not isinstance(conf[key],str) or len(conf[key])>512 or any(ord(c)<32 for c in conf[key]):raise Invalid('Invalid MQTT connection field.')
    if conf['mode']=='manual' and not conf['host'].strip() and not allow_unconfigured:raise Invalid('MQTT host is required.')
    return {'mqtt':conf}

def public_settings(value):
    result=copy.deepcopy(value)
    present={key:bool(result['mqtt'][key]) for key in ('username','password')}
    for key in present:result['mqtt'][key]=None
    return {'settings':result,'secrets':present}
