"""Optional local-development MQTT settings; never copied to app data."""
import os
from .domain import Invalid, defaults, settings_check


def dev_mqtt_settings():
    if os.getenv('HA_AI_STUDIO_DEV') != '1':
        return None
    try:
        tls=os.getenv('DEV_MQTT_TLS','false')
        if tls not in ('true','false'):raise ValueError()
        value={'mqtt':{'mode':'manual','host':os.getenv('DEV_MQTT_HOST',''),
                      'port':int(os.getenv('DEV_MQTT_PORT','1883')),
                      'username':os.getenv('DEV_MQTT_USERNAME',''),
                      'password':os.getenv('DEV_MQTT_PASSWORD',''),'tls':tls=='true'}}
        return settings_check(value,defaults(),allow_unconfigured=True)
    except (ValueError,TypeError):
        raise Invalid('Invalid dev MQTT configuration. Set DEV_MQTT_HOST, a valid port and TLS=true or false in .env.') from None
