#!/bin/bash
# Security Audit Script for NATS JetStream Integration
# Performs comprehensive security checks and generates audit report

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Output file
REPORT_FILE="security_audit_report_$(date +%Y%m%d_%H%M%S).txt"

echo "================================================"
echo "NATS JetStream Security Audit"
echo "================================================"
echo "Started: $(date)"
echo "Report: $REPORT_FILE"
echo ""

# Log function
log() {
    echo "$1" | tee -a "$REPORT_FILE"
}

# Check function
check() {
    local name="$1"
    local command="$2"
    local expected="$3"
    local severity="${4:-FAIL}"  # FAIL or WARN

    log "Checking: $name"

    if eval "$command"; then
        echo -e "${GREEN}✅ PASS${NC}: $name" | tee -a "$REPORT_FILE"
        ((PASSED++))
        return 0
    else
        if [ "$severity" = "WARN" ]; then
            echo -e "${YELLOW}⚠️  WARN${NC}: $name" | tee -a "$REPORT_FILE"
            ((WARNINGS++))
        else
            echo -e "${RED}❌ FAIL${NC}: $name" | tee -a "$REPORT_FILE"
            ((FAILED++))
        fi
        return 1
    fi
}

log "================================================"
log "1. TLS/SSL CONFIGURATION"
log "================================================"
log ""

# Check if TLS is enabled
check "TLS enabled in configuration" \
    "grep -q 'NATS_ENABLE_TLS=true' .env 2>/dev/null" \
    "true"

# Check TLS certificate files exist
check "TLS CA certificate exists" \
    "[ -f tls/ca-cert.pem ]" \
    "true"

check "TLS server certificate exists" \
    "[ -f tls/server-cert.pem ]" \
    "true"

check "TLS client certificate exists" \
    "[ -f tls/client-cert.pem ]" \
    "true"

# Check certificate permissions
check "TLS private key has secure permissions (600)" \
    "[ \$(stat -c '%a' tls/server-key.pem 2>/dev/null || stat -f '%A' tls/server-key.pem 2>/dev/null | tail -c 4) = '0600' ] || [ \$(stat -c '%a' tls/server-key.pem 2>/dev/null || stat -f '%A' tls/server-key.pem 2>/dev/null | tail -c 4) = '600' ]" \
    "true" \
    "WARN"

# Check certificate validity
if [ -f tls/server-cert.pem ]; then
    EXPIRY=$(openssl x509 -in tls/server-cert.pem -noout -enddate 2>/dev/null | cut -d= -f2)
    EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "$EXPIRY" +%s 2>/dev/null)
    NOW_EPOCH=$(date +%s)
    DAYS_UNTIL_EXPIRY=$(( ($EXPIRY_EPOCH - $NOW_EPOCH) / 86400 ))

    if [ $DAYS_UNTIL_EXPIRY -gt 30 ]; then
        log "✅ Certificate expires in $DAYS_UNTIL_EXPIRY days"
        ((PASSED++))
    elif [ $DAYS_UNTIL_EXPIRY -gt 0 ]; then
        log "⚠️  WARNING: Certificate expires in $DAYS_UNTIL_EXPIRY days"
        ((WARNINGS++))
    else
        log "❌ FAIL: Certificate has expired!"
        ((FAILED++))
    fi
fi

log ""
log "================================================"
log "2. AUTHENTICATION"
log "================================================"
log ""

# Check authentication is enabled
check "Authentication enabled" \
    "grep -q 'NATS_ENABLE_AUTH=true' .env 2>/dev/null || grep -q 'NATS_USERNAME=' .env 2>/dev/null" \
    "true"

# Check no hardcoded passwords in source code
check "No hardcoded passwords in source code" \
    "! grep -r 'password.*=.*[\"'\''].*[\"'\'']' src/ --include='*.py' | grep -v 'password: str' | grep -v 'password=None' | grep -q ." \
    "true"

# Check credentials not in git
check ".env file not tracked by git" \
    "! git ls-files --error-unmatch .env >/dev/null 2>&1" \
    "true"

check "credentials/ directory not tracked by git" \
    "! git ls-files credentials/ >/dev/null 2>&1" \
    "true" \
    "WARN"

# Check password complexity (if credentials exist)
if [ -f credentials/nats_credentials.env ]; then
    check "Passwords are complex (>= 32 characters)" \
        "grep 'NATS_PASSWORD_' credentials/nats_credentials.env | cut -d= -f2 | awk 'length(\$0) >= 32' | wc -l | grep -q -v '^0$'" \
        "true" \
        "WARN"
fi

log ""
log "================================================"
log "3. SECRETS MANAGEMENT"
log "================================================"
log ""

# Check for exposed secrets
check "No secrets in environment variables (use secrets manager)" \
    "! env | grep -i 'password\\|token\\|secret\\|key' | grep -q ." \
    "true" \
    "WARN"

# Check .gitignore
check ".gitignore includes credentials/" \
    "grep -q '^credentials/' .gitignore 2>/dev/null" \
    "true"

check ".gitignore includes .env" \
    "grep -q '^\\.env$' .gitignore 2>/dev/null || grep -q '^\\.env' .gitignore 2>/dev/null" \
    "true"

check ".gitignore includes *.pem" \
    "grep -q '\\.pem' .gitignore 2>/dev/null" \
    "true"

# Check for secrets in git history
check "No credentials committed to git history" \
    "! git log --all --full-history -- credentials/ .env tls/*.pem | grep -q ." \
    "true" \
    "WARN"

log ""
log "================================================"
log "4. DEPENDENCY SECURITY"
log "================================================"
log ""

# Check for known vulnerabilities using pip-audit
if command -v pip-audit &> /dev/null; then
    log "Running pip-audit..."
    if pip-audit --desc 2>&1 | tee -a "$REPORT_FILE" | grep -q "No known vulnerabilities found"; then
        log "✅ No known vulnerabilities in dependencies"
        ((PASSED++))
    else
        log "❌ Vulnerabilities found in dependencies"
        ((FAILED++))
    fi
else
    log "⚠️  pip-audit not installed. Install with: pip install pip-audit"
    ((WARNINGS++))
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
check "Python version is 3.12 or higher" \
    "python3 -c 'import sys; exit(0 if sys.version_info >= (3, 12) else 1)'" \
    "true" \
    "WARN"

log ""
log "================================================"
log "5. CODE SECURITY"
log "================================================"
log ""

# Check for SQL injection vulnerabilities (if using database)
check "No raw SQL queries (should use parameterized queries)" \
    "! grep -r 'execute(.*%.*%' src/ --include='*.py' | grep -q ." \
    "true" \
    "WARN"

# Check for eval/exec usage
check "No dangerous eval() or exec() calls" \
    "! grep -r '\\(eval\\|exec\\)(' src/ --include='*.py' | grep -q ." \
    "true"

# Check for pickle usage (insecure deserialization)
check "No pickle usage (use JSON instead)" \
    "! grep -r 'import pickle' src/ --include='*.py' | grep -q ." \
    "true" \
    "WARN"

# Check for shell=True in subprocess
check "No shell=True in subprocess calls" \
    "! grep -r 'subprocess.*shell=True' src/ --include='*.py' | grep -q ." \
    "true"

log ""
log "================================================"
log "6. NATS SERVER CONFIGURATION"
log "================================================"
log ""

# Check NATS server security settings
if [ -f config/nats-server-tls.conf ]; then
    check "NATS TLS verify enabled" \
        "grep -q 'verify: true' config/nats-server-tls.conf" \
        "true"

    check "NATS authentication configured" \
        "grep -q 'authorization' config/nats-server-tls.conf" \
        "true"

    check "NATS max_connections limit set" \
        "grep -q 'max_connections:' config/nats-server-tls.conf" \
        "true" \
        "WARN"

    check "NATS max_payload limit set" \
        "grep -q 'max_payload:' config/nats-server-tls.conf" \
        "true" \
        "WARN"

    check "NATS debug mode disabled in production" \
        "grep -q 'debug: false' config/nats-server-tls.conf" \
        "true" \
        "WARN"

    check "NATS trace mode disabled in production" \
        "grep -q 'trace: false' config/nats-server-tls.conf" \
        "true" \
        "WARN"
fi

log ""
log "================================================"
log "7. LOGGING AND MONITORING"
log "================================================"
log ""

# Check structured logging
check "Structured (JSON) logging enabled" \
    "grep -q 'LOG_FORMAT=json' .env 2>/dev/null || grep -q 'json' src/vertector_nats/*.py" \
    "true" \
    "WARN"

# Check sensitive data not logged
check "No passwords logged" \
    "! grep -r 'log.*password' src/ --include='*.py' | grep -v 'password: str' | grep -q ." \
    "true"

check "No tokens logged" \
    "! grep -r 'log.*token' src/ --include='*.py' | grep -v 'token: str' | grep -q ." \
    "true"

# Check metrics enabled
check "Metrics collection enabled" \
    "grep -q 'NATS_ENABLE_METRICS=true' .env 2>/dev/null" \
    "true" \
    "WARN"

log ""
log "================================================"
log "8. NETWORK SECURITY"
log "================================================"
log ""

# Check localhost binding (should not be exposed publicly)
check "Application not binding to 0.0.0.0 (use localhost or specific IP)" \
    "! grep -r 'host.*=.*[\"'\''"]0\\.0\\.0\\.0[\"'\''"]' src/ --include='*.py' | grep -q ." \
    "true" \
    "WARN"

# Check NATS uses TLS URL
check "NATS servers use nats:// or tls:// protocol" \
    "grep 'NATS_SERVERS=' .env 2>/dev/null | grep -q 'nats://' " \
    "true" \
    "WARN"

log ""
log "================================================"
log "9. CONTAINER SECURITY (if using Docker)"
log "================================================"
log ""

if [ -f Dockerfile ]; then
    check "Dockerfile doesn't run as root" \
        "grep -q 'USER' Dockerfile" \
        "true" \
        "WARN"

    check "Dockerfile uses specific version tags (not :latest)" \
        "! grep 'FROM.*:latest' Dockerfile | grep -q ." \
        "true" \
        "WARN"

    check "Dockerfile minimizes layers" \
        "[ \$(grep -c '^RUN' Dockerfile) -lt 10 ]" \
        "true" \
        "WARN"
fi

if [ -f docker-compose.yml ] || [ -f docker-compose.tls.yml ]; then
    check "Docker Compose uses secrets (not environment variables)" \
        "grep -q 'secrets:' docker-compose*.yml" \
        "true" \
        "WARN"
fi

log ""
log "================================================"
log "10. ACCESS CONTROL"
log "================================================"
log ""

# Check file permissions
check "Source files not world-writable" \
    "! find src/ -type f -perm -002 | grep -q ." \
    "true"

check "Configuration files not world-readable" \
    "! find config/ -name '*.conf' -perm -004 | grep -q ." \
    "true" \
    "WARN"

# Check NATS permissions are properly scoped
if [ -f config/nats-server-tls.conf ]; then
    check "NATS users have restricted permissions (not publish: '>')" \
        "! grep -A 5 'permissions:' config/nats-server-tls.conf | grep 'publish: \"[>]\"' | head -1 | grep -q ." \
        "true" \
        "WARN"
fi

log ""
log "================================================"
log "SUMMARY"
log "================================================"
log ""

TOTAL=$((PASSED + FAILED + WARNINGS))
SCORE=$(( (PASSED * 100) / TOTAL ))

log "Total Checks: $TOTAL"
log "Passed: $PASSED"
log "Failed: $FAILED"
log "Warnings: $WARNINGS"
log ""
log "Security Score: $SCORE%"
log ""

if [ $SCORE -ge 90 ]; then
    log "✅ EXCELLENT: Security posture is strong"
    EXIT_CODE=0
elif [ $SCORE -ge 75 ]; then
    log "✅ GOOD: Security posture is acceptable with minor issues"
    EXIT_CODE=0
elif [ $SCORE -ge 60 ]; then
    log "⚠️  FAIR: Security posture needs improvement"
    EXIT_CODE=1
else
    log "❌ POOR: Critical security issues must be addressed"
    EXIT_CODE=2
fi

log ""
log "================================================"
log "RECOMMENDATIONS"
log "================================================"
log ""

if [ $FAILED -gt 0 ]; then
    log "Critical Actions Required:"
    log "1. Review and fix all FAILED checks above"
    log "2. Ensure TLS is properly configured and enabled"
    log "3. Enable authentication for all NATS connections"
    log "4. Move all secrets to a secrets manager"
    log "5. Update dependencies to patch known vulnerabilities"
fi

if [ $WARNINGS -gt 0 ]; then
    log ""
    log "Recommended Improvements:"
    log "1. Address all WARNING items for enhanced security"
    log "2. Implement certificate expiry monitoring"
    log "3. Set up automated security scanning in CI/CD"
    log "4. Review and restrict NATS user permissions"
    log "5. Enable comprehensive audit logging"
fi

log ""
log "================================================"
log "Report saved to: $REPORT_FILE"
log "Completed: $(date)"
log "================================================"

exit $EXIT_CODE
