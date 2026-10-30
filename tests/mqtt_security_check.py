"""Real TLS validation and MQTT ACL rejection against a disposable broker."""
import os
import ssl
from app.domain import Invalid
from app.mqtt import MQTT

settings={'mqtt':{'mode':'manual','host':'broker-tls','port':8883,'tls':True,'username':'test-user','password':'test-password'}}
def client():return MQTT({'prefix':'security-check','device_id':'test'},lambda _:None,subscribe=False)

os.environ['SSL_CERT_FILE']='/certs/ca.crt'
c=client()
try:
    c.connect(settings)
    c.publish('allowed/result',{'ok':True},absolute=True,retain=False)
    try:c.publish('forbidden/result',{'ok':False},absolute=True,retain=False)
    except Invalid:pass
    else:raise AssertionError('Denied publication was reported as successful')
finally:c.close()

for conf,trust in [({**settings['mqtt'],'host':'wrong-host'},'/certs/ca.crt'),(settings['mqtt'],'/etc/ssl/certs/ca-certificates.crt')]:
    os.environ['SSL_CERT_FILE']=trust
    os.environ['SSL_CERT_DIR']='/nonexistent-ca-directory'
    c=client()
    try:
        try:c.connect({'mqtt':conf})
        except ssl.SSLCertVerificationError:pass
        else:raise AssertionError('TLS certificate validation was bypassed')
    finally:c.close()

os.environ['SSL_CERT_FILE']='/certs/ca.crt'
c=client()
try:
    try:c.connect({'mqtt':{**settings['mqtt'],'password':'wrong-password'}})
    except Invalid:assert c.connection_error=='bad_credentials' or c.connection_error=='not_authorized'
    else:raise AssertionError('Bad credentials were accepted')
finally:c.close()
print('PASS: verified TLS; rejected untrusted CA and wrong hostname; rejected bad credentials; denied publication not marked successful.')
