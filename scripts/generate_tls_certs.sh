#!/bin/bash
# Generate TLS certificates for NATS JetStream
# This script generates self-signed certificates for testing and development
# For production, use certificates from a trusted CA (Let's Encrypt, DigiCert, etc.)

set -e

# Configuration
CERT_DIR="${CERT_DIR:-./tls}"
DAYS_VALID="${DAYS_VALID:-365}"
COUNTRY="${COUNTRY:-US}"
STATE="${STATE:-California}"
CITY="${CITY:-San Francisco}"
ORG="${ORG:-Example Org}"
OU="${OU:-Engineering}"
CN_CA="${CN_CA:-NATS Root CA}"
CN_SERVER="${CN_SERVER:-nats-server}"
CN_CLIENT="${CN_CLIENT:-nats-client}"

# Server alternative names
SERVER_ALT_NAMES="${SERVER_ALT_NAMES:-DNS:localhost,DNS:nats,DNS:nats-server,IP:127.0.0.1}"

echo "================================================"
echo "NATS JetStream TLS Certificate Generator"
echo "================================================"
echo ""
echo "Configuration:"
echo "  Certificate Directory: $CERT_DIR"
echo "  Validity Period: $DAYS_VALID days"
echo "  Server Alt Names: $SERVER_ALT_NAMES"
echo ""

# Create certificate directory
mkdir -p "$CERT_DIR"
cd "$CERT_DIR"

# Generate CA key and certificate
echo "[1/6] Generating CA private key..."
openssl genrsa -out ca-key.pem 4096

echo "[2/6] Generating CA certificate..."
openssl req -new -x509 -days "$DAYS_VALID" -key ca-key.pem -out ca-cert.pem \
    -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/OU=$OU/CN=$CN_CA"

# Generate server key and certificate
echo "[3/6] Generating server private key..."
openssl genrsa -out server-key.pem 4096

echo "[4/6] Generating server certificate signing request..."
openssl req -new -key server-key.pem -out server-req.pem \
    -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/OU=$OU/CN=$CN_SERVER"

# Create server certificate with SAN
echo "[5/6] Signing server certificate with CA..."
cat > server-cert-ext.cnf <<EOF
subjectAltName = $SERVER_ALT_NAMES
extendedKeyUsage = serverAuth
EOF

openssl x509 -req -days "$DAYS_VALID" -in server-req.pem \
    -CA ca-cert.pem -CAkey ca-key.pem -CAcreateserial \
    -out server-cert.pem -extfile server-cert-ext.cnf

# Generate client key and certificate
echo "[6/6] Generating client private key and certificate..."
openssl genrsa -out client-key.pem 4096

openssl req -new -key client-key.pem -out client-req.pem \
    -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/OU=$OU/CN=$CN_CLIENT"

cat > client-cert-ext.cnf <<EOF
extendedKeyUsage = clientAuth
EOF

openssl x509 -req -days "$DAYS_VALID" -in client-req.pem \
    -CA ca-cert.pem -CAkey ca-key.pem -CAcreateserial \
    -out client-cert.pem -extfile client-cert-ext.cnf

# Set appropriate permissions
chmod 600 *-key.pem
chmod 644 *-cert.pem

# Clean up temporary files
rm -f *.cnf *.pem.srl *-req.pem

echo ""
echo "✅ Certificate generation complete!"
echo ""
echo "Generated files in $CERT_DIR:"
echo "  ca-cert.pem       - CA certificate (distribute to all clients/servers)"
echo "  ca-key.pem        - CA private key (keep secure!)"
echo "  server-cert.pem   - Server certificate"
echo "  server-key.pem    - Server private key"
echo "  client-cert.pem   - Client certificate"
echo "  client-key.pem    - Client private key"
echo ""
echo "Verification commands:"
echo "  openssl x509 -in ca-cert.pem -noout -text"
echo "  openssl x509 -in server-cert.pem -noout -text"
echo "  openssl x509 -in client-cert.pem -noout -text"
echo "  openssl verify -CAfile ca-cert.pem server-cert.pem"
echo "  openssl verify -CAfile ca-cert.pem client-cert.pem"
echo ""
echo "Next steps:"
echo "  1. Review certificate validity: openssl x509 -in server-cert.pem -noout -dates"
echo "  2. Update NATS server config to use server-cert.pem and server-key.pem"
echo "  3. Update application .env to use client-cert.pem and client-key.pem"
echo "  4. Run TLS tests: python tests/integration/test_tls_connection.py"
echo ""
echo "⚠️  IMPORTANT: For production, use certificates from a trusted CA!"
echo ""
