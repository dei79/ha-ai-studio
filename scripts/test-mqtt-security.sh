#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
network="studio-security-$$"
broker="studio-security-broker-$$"
certs=$(mktemp -d)
cleanup() { docker rm -f "$broker" >/dev/null 2>&1 || true; docker network rm "$network" >/dev/null 2>&1 || true; rm -rf "$certs"; }
trap cleanup EXIT INT TERM
openssl req -x509 -newkey rsa:2048 -nodes -keyout "$certs/ca.key" -out "$certs/ca.crt" -days 1 -subj '/CN=Studio disposable test CA' >/dev/null 2>&1
openssl req -newkey rsa:2048 -nodes -keyout "$certs/server.key" -out "$certs/server.csr" -subj '/CN=broker-tls' >/dev/null 2>&1
printf 'subjectAltName=DNS:broker-tls\nextendedKeyUsage=serverAuth\n' > "$certs/extensions"
openssl x509 -req -in "$certs/server.csr" -CA "$certs/ca.crt" -CAkey "$certs/ca.key" -CAcreateserial -out "$certs/server.crt" -days 1 -extfile "$certs/extensions" >/dev/null 2>&1
printf 'user test-user\ntopic readwrite allowed/#\n' > "$certs/acl"
cat > "$certs/mosquitto.conf" <<'EOF'
listener 8883
allow_anonymous false
persistence false
password_file /certs/passwords
acl_file /certs/acl
certfile /certs/server.crt
keyfile /certs/server.key
EOF
# Disposable test material only; never mounts production data or credentials.
chmod 755 "$certs"
chmod 644 "$certs/server.key"
docker network create --internal "$network" >/dev/null
docker run --rm -d --name "$broker" --network "$network" --network-alias broker-tls --network-alias wrong-host -v "$certs:/certs" eclipse-mosquitto:2 sh -c 'mosquitto_passwd -b -c /certs/passwords test-user test-password; chmod 644 /certs/passwords; exec mosquitto -c /certs/mosquitto.conf' >/dev/null
# Bound startup wait; it never touches a real broker.
i=0
until docker exec "$broker" mosquitto_pub -h broker-tls -p 8883 --cafile /certs/ca.crt -u test-user -P test-password -t allowed/ready -m ready 2>/dev/null; do
  i=$((i+1)); [ "$i" -lt 20 ] || exit 1; sleep 1
done
docker run --rm --platform linux/amd64 --network "$network" -e PYTHONPATH=/app -v "$PWD/tests:/tests:ro" -v "$certs/ca.crt:/certs/ca.crt:ro" ha-ai-studio:dev python /tests/mqtt_security_check.py
