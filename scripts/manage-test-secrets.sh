#!/bin/bash
# Script to manage test secrets and environment variables

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if running in CI
is_ci() {
    if [[ -n "${CI}" ]] || [[ -n "${GITHUB_ACTIONS}" ]] || [[ -n "${JENKINS_HOME}" ]]; then
        return 0
    else
        return 1
    fi
}

# Function to validate required test environment variables
validate_test_env() {
    local required_vars=(
        "DATABASE_URL"
        "REDIS_URL"
        "SECRET_KEY"
    )
    
    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            missing_vars+=("$var")
        fi
    done
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        print_error "Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        return 1
    fi
    
    print_info "All required test environment variables are set"
    return 0
}

# Function to setup test environment
setup_test_env() {
    local env_file="$1"
    
    if [[ ! -f "$env_file" ]]; then
        print_error "Environment file not found: $env_file"
        return 1
    fi
    
    print_info "Loading environment from: $env_file"
    
    # Export variables from file
    set -a
    source "$env_file"
    set +a
    
    # Validate environment
    validate_test_env
}

# Function to generate mock API keys for testing
generate_mock_keys() {
    print_info "Generating mock API keys for testing..."
    
    # Generate random mock keys
    export OPENAI_API_KEY="sk-test-$(openssl rand -hex 24)"
    export TWILIO_ACCOUNT_SID="ACtest$(openssl rand -hex 16)"
    export TWILIO_AUTH_TOKEN="test-$(openssl rand -hex 16)"
    export DELIVERECT_API_KEY="test-$(openssl rand -hex 20)"
    export SECRET_KEY="test-secret-$(openssl rand -hex 32)"
    
    print_info "Mock API keys generated"
}

# Function to mask sensitive values in logs
mask_secrets() {
    local log_file="$1"
    
    if [[ ! -f "$log_file" ]]; then
        return 0
    fi
    
    print_info "Masking secrets in log file: $log_file"
    
    # List of patterns to mask
    local patterns=(
        "sk-[a-zA-Z0-9]{48}"  # OpenAI API keys
        "AC[a-f0-9]{32}"       # Twilio Account SIDs
        "Bearer [a-zA-Z0-9._-]+"  # Bearer tokens
        "password=[^&\s]+"     # Password parameters
    )
    
    # Create a temporary file
    local temp_file=$(mktemp)
    cp "$log_file" "$temp_file"
    
    # Apply masking
    for pattern in "${patterns[@]}"; do
        sed -i -E "s/$pattern/***MASKED***/g" "$temp_file"
    done
    
    # Replace original file
    mv "$temp_file" "$log_file"
    
    print_info "Secrets masked in log file"
}

# Function to setup CI environment
setup_ci_env() {
    print_info "Setting up CI test environment..."
    
    # Use mock keys in CI
    generate_mock_keys
    
    # Set CI-specific variables
    export TESTING=true
    export FASTAPI_ENV=test
    export LOG_LEVEL=INFO
    export PYTEST_WORKERS=2  # Limit workers in CI
    export MOCK_OPENAI=true
    export MOCK_TWILIO=true
    export MOCK_DELIVERECT=true
    
    # Database and Redis URLs for CI
    export DATABASE_URL="postgresql+asyncpg://redbarsushi:redbarsushi@localhost:5433/redbarsushi_test"
    export REDIS_URL="redis://localhost:6380/0"
    
    print_info "CI test environment configured"
}

# Main command handling
case "${1:-}" in
    "setup")
        if is_ci; then
            setup_ci_env
        else
            env_file="${2:-$PROJECT_ROOT/.env.test}"
            setup_test_env "$env_file"
        fi
        ;;
    
    "generate")
        generate_mock_keys
        ;;
    
    "validate")
        validate_test_env
        ;;
    
    "mask")
        log_file="${2:-}"
        if [[ -z "$log_file" ]]; then
            print_error "Usage: $0 mask <log_file>"
            exit 1
        fi
        mask_secrets "$log_file"
        ;;
    
    "export")
        # Export current environment to a file (excluding sensitive values)
        output_file="${2:-$PROJECT_ROOT/.env.test.generated}"
        print_info "Exporting test environment to: $output_file"
        
        {
            echo "# Generated test environment - $(date)"
            echo "# DO NOT COMMIT THIS FILE"
            echo ""
            env | grep -E "^(DATABASE_URL|REDIS_URL|TESTING|FASTAPI_ENV|LOG_LEVEL|MOCK_)" | sort
        } > "$output_file"
        
        print_info "Environment exported (sensitive values excluded)"
        ;;
    
    *)
        echo "Usage: $0 {setup|generate|validate|mask|export} [args]"
        echo ""
        echo "Commands:"
        echo "  setup [env_file]  - Set up test environment from file"
        echo "  generate         - Generate mock API keys"
        echo "  validate         - Validate required environment variables"
        echo "  mask <log_file>  - Mask secrets in log file"
        echo "  export [file]    - Export current test environment"
        exit 1
        ;;
esac