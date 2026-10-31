"""Bounded, ephemeral camera-test diagnostics; never device payloads or credentials."""
from contextvars import ContextVar
from datetime import datetime, timezone
import re
import time
from .domain import Invalid

current = ContextVar('camera_test_progress', default=None)

def begin(service, ident):
    if not isinstance(ident,str) or not re.fullmatch(r'[a-f0-9]{32}',ident):
        raise Invalid('Invalid camera test progress ID.')
    records=getattr(service,'camera_test_progress',{})
    records={key:value for key,value in records.items() if time.monotonic()-value['created']<3600}
    if ident in records:raise Invalid('Camera test progress ID already used.')
    while len(records)>=8:records.pop(next(iter(records)))
    record={'created':time.monotonic(),'entries':[]};records[ident]=record;service.camera_test_progress=records
    def append(message):
        if len(record['entries'])<100:
            record['entries'].append({'time':datetime.now(timezone.utc).isoformat(timespec='seconds'),'message':message})
    return append

def read(service,ident):
    record=getattr(service,'camera_test_progress',{}).get(ident)
    return {'entries':record['entries'] if record and time.monotonic()-record['created']<3600 else []}
