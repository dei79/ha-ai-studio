// JSON quoted strings are valid YAML scalars and Jinja string literals.
export function mqttTestAutomationYaml(config, example) {
 if(!example||typeof example!=='object'||Array.isArray(example)||!Object.hasOwn(example,'data'))throw Error('No valid example request is available for this action.');
 const payload={...example};delete payload.request_id;
 return `alias: ${JSON.stringify('HA AI Studio - Test '+config.name)}
description: Send a test request and show incoming results.
mode: parallel
max: 10
triggers:
  - trigger: mqtt
    topic: ${JSON.stringify(config.output.topic)}
conditions: []
actions:
  - choose:
      - conditions:
          - condition: template
            value_template: >-
              {{ trigger is defined
                 and trigger.platform is defined
                 and trigger.platform == 'mqtt' }}
        sequence:
          - action: persistent_notification.create
            data:
              title: HA AI Studio - Result
              message: "{{ trigger.payload }}"
    default:
      - action: mqtt.publish
        data:
          topic: ${JSON.stringify(config.input.topic)}
          qos: 1
          retain: false
          payload: >-
            {{ dict(
              ${JSON.stringify(JSON.stringify(payload))} | from_json,
              request_id=now().isoformat() ~ '-' ~ (range(100000) | random)
            ) | to_json }}
`;
}
