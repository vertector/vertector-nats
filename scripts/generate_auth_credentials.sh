#!/bin/bash
# Generate authentication credentials for NATS JetStream
# This script generates bcrypt hashed passwords and NKeys for NATS authentication

set -e

# Check if mkpasswd or htpasswd is available for bcrypt
if command -v mkpasswd &> /dev/null; then
    BCRYPT_CMD="mkpasswd -m bcrypt"
elif command -v htpasswd &> /dev/null; then
    BCRYPT_CMD="htpasswd -nbB"
else
    echo "Error: Neither mkpasswd nor htpasswd found."
    echo "Install one of these tools:"
    echo "  Ubuntu/Debian: apt-get install whois"
    echo "  macOS: brew install mkpasswd"
    echo "  Or use: apt-get install apache2-utils (for htpasswd)"
    exit 1
fi

echo "================================================"
echo "NATS JetStream Authentication Generator"
echo "================================================"
echo ""

# Function to generate bcrypt hash
generate_bcrypt() {
    local password="$1"
    if command -v mkpasswd &> /dev/null; then
        echo $(mkpasswd -m bcrypt "$password")
    else
        # htpasswd outputs "username:hash", so extract hash
        echo $(htpasswd -nbB "" "$password" | cut -d: -f2)
    fi
}

# Function to generate random password
generate_password() {
    local length="${1:-32}"
    openssl rand -base64 "$length" | tr -d "=+/" | cut -c1-"$length"
}

# Create credentials directory
CREDS_DIR="${CREDS_DIR:-./credentials}"
mkdir -p "$CREDS_DIR"

echo "Generating credentials for NATS services..."
echo ""

# Generate credentials for each service
declare -A SERVICES=(
    ["schedule_service"]="Academic Schedule Service"
    ["notes_service"]="Notes Taking Service"
    ["admin"]="Admin User"
    ["monitoring"]="Monitoring Service"
)

# Output file
OUTPUT_FILE="$CREDS_DIR/nats_credentials.env"
CONFIG_FILE="$CREDS_DIR/nats_users.conf"

# Clear existing files
> "$OUTPUT_FILE"
> "$CONFIG_FILE"

echo "# NATS Authentication Credentials" >> "$OUTPUT_FILE"
echo "# Generated: $(date)" >> "$OUTPUT_FILE"
echo "# WARNING: Keep these credentials secure!" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

echo "# NATS User Configuration" >> "$CONFIG_FILE"
echo "# Generated: $(date)" >> "$CONFIG_FILE"
echo "# Include this in nats-server.conf: include './credentials/nats_users.conf'" >> "$CONFIG_FILE"
echo "" >> "$CONFIG_FILE"
echo "authorization {" >> "$CONFIG_FILE"
echo "    users = [" >> "$CONFIG_FILE"

for service in "${!SERVICES[@]}"; do
    description="${SERVICES[$service]}"

    echo "Generating credentials for: $description ($service)"

    # Generate random password
    password=$(generate_password 32)

    # Generate bcrypt hash
    echo "  Hashing password..."
    hash=$(generate_bcrypt "$password")

    # Write to .env file
    echo "# $description" >> "$OUTPUT_FILE"
    echo "NATS_USERNAME_${service^^}=$service" >> "$OUTPUT_FILE"
    echo "NATS_PASSWORD_${service^^}=$password" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"

    # Write to NATS config file
    cat >> "$CONFIG_FILE" <<EOF
        # $description
        {
            user: "$service"
            password: "$hash"
EOF

    # Add permissions based on service
    case "$service" in
        "schedule_service")
            cat >> "$CONFIG_FILE" <<EOF
            permissions: {
                publish: ["academic.>", "_INBOX.>"]
                subscribe: ["academic.>", "_INBOX.>"]
            }
EOF
            ;;
        "notes_service")
            cat >> "$CONFIG_FILE" <<EOF
            permissions: {
                publish: ["notes.>", "_INBOX.>"]
                subscribe: ["academic.>", "notes.>", "_INBOX.>"]
            }
EOF
            ;;
        "monitoring")
            cat >> "$CONFIG_FILE" <<EOF
            permissions: {
                publish: ["_INBOX.>"]
                subscribe: [">"]
            }
EOF
            ;;
        "admin")
            cat >> "$CONFIG_FILE" <<EOF
            permissions: {
                publish: [">"]
                subscribe: [">"]
            }
EOF
            ;;
    esac

    echo "        }," >> "$CONFIG_FILE"
    echo ""
done

# Remove trailing comma from last user
sed -i.bak '$ s/,$//' "$CONFIG_FILE"
rm -f "$CONFIG_FILE.bak"

echo "    ]" >> "$CONFIG_FILE"
echo "    timeout: 2.0" >> "$CONFIG_FILE"
echo "}" >> "$CONFIG_FILE"

# Set secure permissions
chmod 600 "$OUTPUT_FILE"
chmod 600 "$CONFIG_FILE"

echo ""
echo "✅ Credential generation complete!"
echo ""
echo "Generated files in $CREDS_DIR:"
echo "  nats_credentials.env  - Environment variables for application"
echo "  nats_users.conf       - NATS server user configuration"
echo ""
echo "Next steps:"
echo ""
echo "1. Review generated credentials:"
echo "   cat $OUTPUT_FILE"
echo ""
echo "2. Add to your application .env file:"
echo "   cat $CREDS_DIR/nats_credentials.env >> .env"
echo ""
echo "3. Include in NATS server config:"
echo "   Add to nats-server.conf: include '$CREDS_DIR/nats_users.conf'"
echo ""
echo "4. For Kubernetes, create secrets:"
echo "   kubectl create secret generic nats-auth \\"
echo "     --from-env-file=$CREDS_DIR/nats_credentials.env"
echo ""
echo "5. Restart NATS server to apply new credentials"
echo ""
echo "⚠️  IMPORTANT:"
echo "   - Keep $CREDS_DIR secure and NEVER commit to git!"
echo "   - Add to .gitignore: echo '$CREDS_DIR/' >> .gitignore"
echo "   - Rotate credentials regularly (every 90 days recommended)"
echo "   - Use a secrets manager (HashiCorp Vault, AWS Secrets Manager, etc.) in production"
echo ""

# Generate .gitignore entry
if [ -f ".gitignore" ]; then
    if ! grep -q "^credentials/" .gitignore; then
        echo "credentials/" >> .gitignore
        echo "✅ Added credentials/ to .gitignore"
    fi
fi

# Generate token-based auth example
TOKEN=$(generate_password 64)
cat > "$CREDS_DIR/nats_token.env" <<EOF
# Token-based authentication (alternative to username/password)
# Generated: $(date)

NATS_TOKEN=$TOKEN
EOF

chmod 600 "$CREDS_DIR/nats_token.env"

echo ""
echo "📝 Also generated token-based auth:"
echo "   $CREDS_DIR/nats_token.env"
echo ""
