import socket
import ssl
import unittest
from unittest.mock import patch
from app.broker_probe import probe

class ProbeTests(unittest.TestCase):
    def run_probe(self,error=None,code=None):
        with patch('app.broker_probe.socket.getaddrinfo'),patch('app.broker_probe.MQTT') as client:
            client.return_value.connection_error=code
            client.return_value.connect.side_effect=error
            result=probe({'mqtt':{'host':'private-host','port':1883,'username':'private-user','password':'private-password'}})
            client.return_value.close.assert_called_once()
            client.return_value.publish.assert_not_called()
            return result
    def test_success_has_scope_and_no_credentials(self):
        result=self.run_probe();self.assertTrue(result['ok']);self.assertIn('not tested',result['scope'])
        self.assertNotIn('private',str(result))
    def test_safe_failures(self):
        for error,code in [(ConnectionRefusedError('SECRET'),'connection_refused'),(TimeoutError('SECRET'),'timeout'),(socket.gaierror('SECRET'),'dns_failed'),(ssl.SSLCertVerificationError('SECRET'),'tls_certificate')]:
            result=self.run_probe(error);self.assertFalse(result['ok']);self.assertEqual(result['code'],code);self.assertNotIn('SECRET',str(result))
    def test_connack_rejection(self):
        result=self.run_probe(Exception('SECRET'),'not_authorized')
        self.assertEqual(result['code'],'not_authorized');self.assertNotIn('SECRET',str(result))
