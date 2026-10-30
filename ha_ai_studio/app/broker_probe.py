"""Safe, structured connection diagnostics. Never forward exception/broker text."""
import errno
import socket
import ssl
import time
import uuid
from .mqtt import MQTT

MESSAGES = {
    'dns_failed': 'Host resolution failed. Check the broker host name and container DNS.',
    'connection_refused': 'TCP connection refused. Check that the broker is running and listening on the configured port.',
    'network_unreachable': 'The broker network is unreachable from the app container. Check routing, VPN and firewall settings.',
    'timeout': 'Connection timed out. Check the address, port, firewall and whether this is an MQTT listener.',
    'tls_certificate': 'TLS certificate verification failed. Check certificate trust, host name and certificate validity.',
    'tls_failed': 'TLS negotiation failed. Check whether this port requires TLS and whether a client certificate is required.',
    'unsupported_protocol': 'The broker rejected MQTT v5. This app requires an MQTT v5 listener.',
    'invalid_client_id': 'The broker rejected the generated client ID. Check broker client-ID restrictions.',
    'bad_credentials': 'The broker rejected the username or password. Update the saved MQTT credentials.',
    'not_authorized': 'The broker denied access. Check the saved MQTT credentials and broker connection permissions.',
    'server_unavailable': 'The broker reported that its service is unavailable.',
    'server_busy': 'The broker reported that it is busy. Try again later.',
    'banned': 'The broker rejected this client as banned. Check broker access policy.',
    'connection_rejected': 'The broker rejected the MQTT connection. Check its access policy and listener settings.',
    'connection_failed': 'Connection failed without a specific safe diagnostic. Check broker logs and listener settings.',
}

def probe(settings):
    started=time.monotonic();logs=[]
    def report(stage,message):
        logs.append({'stage':stage,'elapsed_ms':round((time.monotonic()-started)*1000),'message':message})
    conf=settings['mqtt']
    client=MQTT({'prefix':'studio_probe_'+uuid.uuid4().hex[:12],'device_id':'probe'},lambda _:None,subscribe=False,report=report)
    ok=False;code=None
    try:
        report('settings','Using saved broker settings. Credentials are hidden.')
        report('dns','Resolving the broker host from the app container.')
        socket.getaddrinfo(conf['host'],int(conf['port']),type=socket.SOCK_STREAM)
        report('dns_ok','Host resolution succeeded.')
        client.connect(settings)
        ok=True
        report('mqtt_ok','MQTT v5 connection accepted by the broker.')
    except Exception as error:
        code=client.connection_error
        if not code:
            if isinstance(error,socket.gaierror):code='dns_failed'
            elif isinstance(error,ssl.SSLCertVerificationError):code='tls_certificate'
            elif isinstance(error,ssl.SSLError):code='tls_failed'
            elif isinstance(error,ConnectionRefusedError):code='connection_refused'
            elif isinstance(error,TimeoutError):code='timeout'
            elif isinstance(error,OSError) and error.errno in (errno.ENETUNREACH,errno.EHOSTUNREACH):code='network_unreachable'
            elif any(item['stage']=='mqtt' for item in logs):code='timeout'
            else:code='connection_failed'
        report('error',MESSAGES.get(code,MESSAGES['connection_failed']))
    finally:
        try:client.close();report('closed','Test connection closed. No messages published or subscriptions created.')
        except Exception:report('closed','Test ended. No messages published or subscriptions created.')
    message='Broker connection successful.' if ok else MESSAGES.get(code,MESSAGES['connection_failed'])
    return {'ok':ok,'code':code,'message':message,'logs':logs,
            'scope':'Connection and authentication only. Topic publish/subscribe permissions were not tested.'}
