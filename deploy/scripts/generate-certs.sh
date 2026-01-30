#!/bin/bash
# =============================================================================
# TRJM - Self-Signed Certificate Generator
# =============================================================================
# Generates self-signed TLS certificates for local development
# Usage: ./generate-certs.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="${SCRIPT_DIR}/../certs"

# Certificate parameters
COUNTRY="US"
STATE="California"
LOCALITY="San Francisco"
ORGANIZATION="TRJM Development"
COMMON_NAME="localhost"
DAYS_VALID=365

echo "=== TRJM Certificate Generator ==="
echo ""

# Create certs directory if it doesn't exist
mkdir -p "$CERT_DIR"

# Check if certificates already exist
if [ -f "$CERT_DIR/server.crt" ] && [ -f "$CERT_DIR/server.key" ]; then
    echo "Certificates already exist in $CERT_DIR"
    read -p "Do you want to regenerate them? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Keeping existing certificates."
        exit 0
    fi
fi

echo "Generating self-signed certificates..."
echo ""

# Create OpenSSL configuration for SAN (Subject Alternative Names)
cat > "$CERT_DIR/openssl.cnf" << EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
x509_extensions = v3_req
distinguished_name = dn

[dn]
C = $COUNTRY
ST = $STATE
L = $LOCALITY
O = $ORGANIZATION
CN = $COMMON_NAME

[v3_req]
subjectAltName = @alt_names
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment

[alt_names]
DNS.1 = localhost
DNS.2 = *.localhost
DNS.3 = trjm.local
DNS.4 = *.trjm.local
IP.1 = 127.0.0.1
IP.2 = ::1
EOF

# Generate private key
echo "1. Generating private key..."
openssl genrsa -out "$CERT_DIR/server.key" 2048

# Generate certificate signing request
echo "2. Generating certificate signing request..."
openssl req -new \
    -key "$CERT_DIR/server.key" \
    -out "$CERT_DIR/server.csr" \
    -config "$CERT_DIR/openssl.cnf"

# Generate self-signed certificate
echo "3. Generating self-signed certificate..."
openssl x509 -req \
    -days $DAYS_VALID \
    -in "$CERT_DIR/server.csr" \
    -signkey "$CERT_DIR/server.key" \
    -out "$CERT_DIR/server.crt" \
    -extensions v3_req \
    -extfile "$CERT_DIR/openssl.cnf"

# Set permissions
chmod 600 "$CERT_DIR/server.key"
chmod 644 "$CERT_DIR/server.crt"

# Clean up temporary files
rm -f "$CERT_DIR/server.csr" "$CERT_DIR/openssl.cnf"

echo ""
echo "=== Certificate Generation Complete ==="
echo ""
echo "Files created:"
echo "  - $CERT_DIR/server.crt (certificate)"
echo "  - $CERT_DIR/server.key (private key)"
echo ""
echo "Certificate details:"
openssl x509 -in "$CERT_DIR/server.crt" -noout -subject -dates
echo ""
echo "To trust this certificate on your system:"
echo ""
echo "  macOS:"
echo "    sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain $CERT_DIR/server.crt"
echo ""
echo "  Windows (PowerShell as Admin):"
echo "    Import-Certificate -FilePath $CERT_DIR/server.crt -CertStoreLocation Cert:\\LocalMachine\\Root"
echo ""
echo "  Linux (Debian/Ubuntu):"
echo "    sudo cp $CERT_DIR/server.crt /usr/local/share/ca-certificates/trjm.crt"
echo "    sudo update-ca-certificates"
echo ""
