#!/bin/bash
# Track A verification suite
set -u

echo "=== 1 API APP-CONFIG ==="
curl -sS --max-time 15 -w '\nHTTP=%{http_code} ssl_verify=%{ssl_verify_result}\n' \
  https://api.orairadio.in/api/public/app-config || echo API_FAIL

echo "=== 2 STREAM ==="
curl -sS --max-time 12 -r 0-511 -o /tmp/stream-sample.bin -w 'HTTP=%{http_code} ctype=%{content_type} bytes=%{size_download} ssl=%{ssl_verify_result}\n' \
  https://stream.orairadio.in/listen/orai_radio/radio.mp3 || echo STREAM_FAIL
file /tmp/stream-sample.bin 2>/dev/null || true
xxd /tmp/stream-sample.bin 2>/dev/null | head -2 || true

echo "=== 3 CONFIG JSON ==="
curl -sS --max-time 15 -w '\nHTTP=%{http_code} ssl_verify=%{ssl_verify_result}\n' \
  https://config.orairadio.in/app-config.json || echo CONFIG_FAIL

echo "=== 4 ADMIN BLOCK ==="
curl -sS --max-time 10 -o /tmp/admin-body.txt -w 'HTTP=%{http_code}\n' \
  https://api.orairadio.in/api/admin/app-config/stream_url || true
head -c 200 /tmp/admin-body.txt; echo

echo "=== 5 PUBLIC 8080 ==="
ss -lntp | grep 8080 || true
curl -sS --max-time 5 http://35.244.15.150:8080/api/public/app-config && echo PUBLIC_8080_OPEN || echo PUBLIC_8080_UNREACHABLE_OK

echo "=== 6 CERT SAN ==="
echo | openssl s_client -connect api.orairadio.in:443 -servername api.orairadio.in 2>/dev/null \
  | openssl x509 -noout -subject -issuer -ext subjectAltName 2>/dev/null | head -20

echo "=== 7 NETWORK ==="
sudo docker exec azuracast getent hosts neena-backend
