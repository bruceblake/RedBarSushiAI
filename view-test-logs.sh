#!/bin/bash
# Script to view and manage test logs

# Constants
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Log directory
LOG_DIR="$HOME/redbar_test_logs"
SCREENSHOT_DIR="screenshots"

# Function to check if logs exist
check_logs() {
  if [ ! -d "$LOG_DIR" ]; then
    echo -e "${RED}Log directory not found. No tests have been run yet.${NC}"
    return 1
  fi
  
  # Count test logs
  test_logs=$(find "$LOG_DIR" -name "e2e_test_*.log" | wc -l)
  if [ "$test_logs" -eq 0 ]; then
    echo -e "${RED}No test logs found. Run tests first with ./run-full-e2e-tests.sh${NC}"
    return 1
  fi
  
  return 0
}

# Function to list all logs
list_logs() {
  echo -e "${BOLD}Available Test Logs:${NC}"
  
  # List all test logs with date and file size
  find "$LOG_DIR" -name "e2e_test_*.log" -type f | sort -r | while read -r log_file; do
    basename=$(basename "$log_file")
    size=$(du -h "$log_file" | cut -f1)
    date_str=$(echo "$basename" | grep -o "[0-9]\{8\}_[0-9]\{6\}" | sed 's/\([0-9]\{4\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)_\([0-9]\{2\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)/\1-\2-\3 \4:\5:\6/')
    
    # Check if there were failures
    if grep -q "FAILED" "$log_file"; then
      status="${RED}✗ FAILED${NC}"
    elif grep -q "PASSED" "$log_file"; then
      status="${GREEN}✓ PASSED${NC}"
    else
      status="${YELLOW}? UNKNOWN${NC}"
    fi
    
    echo -e "${YELLOW}$date_str${NC} - ${BLUE}$size${NC} - $status - $basename"
  done
}

# Function to view a specific log
view_log() {
  if [ -z "$1" ]; then
    echo -e "${RED}No log file specified.${NC}"
    return 1
  fi
  
  log_file="$LOG_DIR/$1"
  
  if [ ! -f "$log_file" ]; then
    echo -e "${RED}Log file not found: $1${NC}"
    return 1
  fi
  
  # Use less to view the log file
  less -R "$log_file"
}

# Function to view the most recent log
view_latest_log() {
  latest_log=$(find "$LOG_DIR" -name "e2e_test_*.log" -type f | sort -r | head -n 1)
  
  if [ -z "$latest_log" ]; then
    echo -e "${RED}No log files found.${NC}"
    return 1
  fi
  
  echo -e "${YELLOW}Viewing latest log: $(basename "$latest_log")${NC}"
  less -R "$latest_log"
}

# Function to show test summary
show_test_summary() {
  if [ -z "$1" ]; then
    log_file=$(find "$LOG_DIR" -name "e2e_test_*.log" -type f | sort -r | head -n 1)
  else
    log_file="$LOG_DIR/$1"
  fi
  
  if [ ! -f "$log_file" ]; then
    echo -e "${RED}Log file not found.${NC}"
    return 1
  fi
  
  echo -e "${BOLD}Test Summary for $(basename "$log_file"):${NC}"
  echo -e "${YELLOW}======================================${NC}"
  
  # Extract test information
  echo -e "${BOLD}Test Results:${NC}"
  grep -E "PASSED|FAILED|SKIPPED" "$log_file" | sort | uniq -c | while read -r line; do
    if echo "$line" | grep -q "PASSED"; then
      echo -e "${GREEN}$line${NC}"
    elif echo "$line" | grep -q "FAILED"; then
      echo -e "${RED}$line${NC}"
    else
      echo -e "${YELLOW}$line${NC}"
    fi
  done
  
  echo -e "${YELLOW}======================================${NC}"
  
  # Show failure details if any
  if grep -q "FAILED" "$log_file"; then
    echo -e "${BOLD}${RED}Failure Details:${NC}"
    grep -A 10 "FAILED" "$log_file" | head -n 20
    echo -e "${YELLOW}(Use 'view' command to see full log)${NC}"
  fi
  
  # Show screenshot information
  echo -e "${BOLD}Screenshots:${NC}"
  if [ -d "$SCREENSHOT_DIR" ]; then
    find "$SCREENSHOT_DIR" -name "*.png" -type f -newer "$log_file" | while read -r screenshot; do
      echo -e "${BLUE}$(basename "$screenshot")${NC}"
    done
  else
    echo -e "${YELLOW}No screenshots directory found.${NC}"
  fi
  
  # Root directory screenshots
  find . -maxdepth 1 -name "*.png" -type f | while read -r screenshot; do
    echo -e "${BLUE}$(basename "$screenshot")${NC}"
  done
}

# Function to cleanup old logs
cleanup_logs() {
  echo -e "${BOLD}Log Cleanup${NC}"
  echo -e "${YELLOW}This will remove old test logs and screenshots.${NC}"
  read -p "Keep how many recent logs? (default: 5) " keep_count
  
  # Default to 5 if not specified
  keep_count=${keep_count:-5}
  
  # Find logs to delete
  logs_to_delete=$(find "$LOG_DIR" -name "e2e_test_*.log" -type f | sort -r | tail -n +$((keep_count+1)))
  
  if [ -z "$logs_to_delete" ]; then
    echo -e "${GREEN}No old logs to delete.${NC}"
  else
    echo -e "${YELLOW}The following logs will be deleted:${NC}"
    echo "$logs_to_delete" | xargs -n1 basename
    
    read -p "Proceed with deletion? (y/n) " confirm
    if [[ $confirm =~ ^[Yy]$ ]]; then
      echo "$logs_to_delete" | xargs rm
      echo -e "${GREEN}Old logs deleted.${NC}"
    else
      echo -e "${YELLOW}Deletion cancelled.${NC}"
    fi
  fi
}

# Display help menu
show_help() {
  echo -e "${BOLD}Test Log Viewer${NC}"
  echo "Usage: $0 [command] [args]"
  echo ""
  echo "Commands:"
  echo "  list             List all available test logs"
  echo "  view [log_file]  View a specific log file"
  echo "  latest           View the most recent log file"
  echo "  summary [log]    Show test summary for a log file (default: latest)"
  echo "  cleanup          Remove old log files"
  echo "  help             Show this help message"
  echo ""
  echo "Examples:"
  echo "  $0 list          List all logs"
  echo "  $0 latest        View the most recent log"
  echo "  $0 summary       Show summary of latest test run"
  echo "  $0 view e2e_test_20250418_123456.log  View a specific log"
}

# Main function
main() {
  # Create log directory if it doesn't exist
  mkdir -p "$LOG_DIR"
  
  # Process command line arguments
  cmd=${1:-"help"}
  
  case "$cmd" in
    list)
      check_logs && list_logs
      ;;
    view)
      log_file=$2
      if [ -z "$log_file" ]; then
        echo -e "${RED}No log file specified.${NC}"
        echo -e "${YELLOW}Use '$0 list' to see available logs.${NC}"
        return 1
      fi
      view_log "$log_file"
      ;;
    latest)
      check_logs && view_latest_log
      ;;
    summary)
      check_logs && show_test_summary "$2"
      ;;
    cleanup)
      check_logs && cleanup_logs
      ;;
    help|*)
      show_help
      ;;
  esac
}

# Run the main function
main "$@"