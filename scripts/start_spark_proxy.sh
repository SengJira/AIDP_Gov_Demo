#!/usr/bin/env bash
# Start a local TLS-terminating proxy for the DDPE Spark Connect endpoint.
#
# Why needed: the DDPE gRPC ingress presents a cert signed by an internal
# TitanCA whose root is not in our trust bundle, and the istio gateway
# routes on the gRPC :authority header - so the client must connect to a
# local endpoint while still presenting the real hostname.
#
#   client -> https://localhost:$PORT (our CA) -> https://<ddpe-host>:443
#   + gRPC channel option grpc.default_authority=<ddpe-host>
#
# Usage:  scripts/start_spark_proxy.sh            (idempotent)
# Env:    DDPE_GRPC_HOST, DDPE_PROXY_PORT (defaults below)
set -euo pipefail

HOST="${DDPE_GRPC_HOST:-jirawut-demo-grpc.ddpe.lab9bgp.com}"
PORT="${DDPE_PROXY_PORT:-15003}"
DIR="${SPARK_TLS_DIR:-/tmp/sparktls}"

mkdir -p "$DIR"

# 1. local CA + server cert (SAN covers localhost AND the ddpe host)
if [[ ! -f "$DIR/ca.pem" ]]; then
  openssl req -x509 -newkey rsa:2048 -keyout "$DIR/ca.key" -out "$DIR/ca.pem" \
    -days 90 -nodes -subj "/CN=LocalSparkCA" \
    -addext "basicConstraints=critical,CA:TRUE" 2>/dev/null
  openssl req -newkey rsa:2048 -keyout "$DIR/srv.key" -out "$DIR/srv.csr" \
    -nodes -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,DNS:${HOST},IP:127.0.0.1" 2>/dev/null
  openssl x509 -req -in "$DIR/srv.csr" -CA "$DIR/ca.pem" -CAkey "$DIR/ca.key" \
    -CAcreateserial -out "$DIR/srv.crt" -days 90 -copy_extensions copy 2>/dev/null
  cat "$DIR/srv.crt" "$DIR/srv.key" > "$DIR/srv.pem"
  echo "generated CA+cert in $DIR"
fi

# 2. haproxy config
cat > "$DIR/haproxy.cfg" <<EOF
global
    maxconn 256
defaults
    mode tcp
    timeout connect 10s
    timeout client 300s
    timeout server 300s
frontend spark_tls_in
    bind 127.0.0.1:${PORT} ssl crt ${DIR}/srv.pem alpn h2
    default_backend ddpe_grpc
backend ddpe_grpc
    server ddpe ${HOST}:443 ssl verify none sni str(${HOST})
EOF

# 3. (re)start haproxy
if pgrep -f "haproxy -f ${DIR}/haproxy.cfg" >/dev/null; then
  echo "proxy already running on 127.0.0.1:${PORT}"
else
  haproxy -f "$DIR/haproxy.cfg" -D
  echo "proxy started: 127.0.0.1:${PORT} -> ${HOST}:443"
fi

echo "set GRPC_DEFAULT_SSL_ROOTS_FILE_PATH=${DIR}/ca.pem for clients"
