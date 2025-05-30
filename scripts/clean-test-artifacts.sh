#!/bin/bash
# Script to clean up test artifacts and prepare for fresh test run

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Function to clean test artifacts
clean_artifacts() {
    print_info "Cleaning test artifacts..."
    
    cd "$PROJECT_ROOT"
    
    # Clean Python cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type f -name "*.pyo" -delete 2>/dev/null || true
    find . -type f -name ".coverage" -delete 2>/dev/null || true
    find . -type f -name ".coverage.*" -delete 2>/dev/null || true
    
    # Clean test output directories
    rm -rf htmlcov/* 2>/dev/null || true
    rm -rf coverage/* 2>/dev/null || true
    rm -rf test-results/* 2>/dev/null || true
    rm -rf .pytest_cache/* 2>/dev/null || true
    rm -rf test-logs/* 2>/dev/null || true
    
    # Create clean directories
    mkdir -p htmlcov coverage test-results .pytest_cache test-logs
    
    print_info "Test artifacts cleaned"
}

# Function to archive test results
archive_results() {
    local archive_name="test-results-$(date +%Y%m%d-%H%M%S).tar.gz"
    
    print_info "Archiving test results to: $archive_name"
    
    cd "$PROJECT_ROOT"
    
    if [[ -d "test-results" ]] || [[ -d "coverage" ]] || [[ -d "htmlcov" ]]; then
        tar -czf "$archive_name" \
            test-results/ \
            coverage/ \
            htmlcov/ \
            test-logs/ \
            2>/dev/null || true
        
        print_info "Test results archived to: $archive_name"
    else
        print_warn "No test results to archive"
    fi
}

# Function to prepare test environment
prepare_env() {
    print_info "Preparing test environment..."
    
    cd "$PROJECT_ROOT"
    
    # Ensure directories exist with proper permissions
    mkdir -p test-results coverage htmlcov .pytest_cache test-logs
    
    # Set permissions for Docker
    chmod -R 777 test-results coverage htmlcov .pytest_cache test-logs 2>/dev/null || true
    
    print_info "Test environment prepared"
}

# Main command handling
case "${1:-clean}" in
    "clean")
        clean_artifacts
        ;;
    
    "archive")
        archive_results
        ;;
    
    "prepare")
        prepare_env
        ;;
    
    "full")
        # Archive existing results, then clean and prepare
        archive_results
        clean_artifacts
        prepare_env
        ;;
    
    *)
        echo "Usage: $0 {clean|archive|prepare|full}"
        echo ""
        echo "Commands:"
        echo "  clean    - Remove all test artifacts"
        echo "  archive  - Archive current test results"
        echo "  prepare  - Prepare test environment"
        echo "  full     - Archive, clean, and prepare"
        exit 1
        ;;
esac