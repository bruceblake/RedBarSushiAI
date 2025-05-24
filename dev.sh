#!/bin/bash
# Development environment management script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[STATUS]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to free up a port
free_port() {
    local port=$1
    if check_port $port; then
        print_warning "Port $port is in use. Attempting to free it..."
        
        # Check if it's a Docker container
        local container=$(docker ps --format "table {{.Names}}\t{{.Ports}}" | grep ":$port->" | awk '{print $1}')
        if [ ! -z "$container" ]; then
            print_status "Stopping Docker container using port $port: $container"
            docker stop $container
        else
            # Check for local Redis
            local pid=$(lsof -ti:$port)
            if [ ! -z "$pid" ]; then
                print_warning "Process $pid is using port $port"
                # Don't kill system processes automatically
                return 1
            fi
        fi
    fi
    return 0
}

# Main script
case "$1" in
    start)
        print_status "Starting development environment..."
        
        # Check for .env file
        if [ ! -f .env ]; then
            if [ -f .env.example ]; then
                print_warning ".env file not found. Creating from .env.example..."
                cp .env.example .env
                print_warning "Please update .env with your actual API keys!"
            else
                print_error ".env file not found and no .env.example available!"
                exit 1
            fi
        fi
        
        # Check critical ports
        PORTS=(5432 6379 8000)
        for port in "${PORTS[@]}"; do
            if check_port $port; then
                print_warning "Port $port is already in use"
                case $port in
                    5432)
                        print_status "PostgreSQL port - checking if it's our container..."
                        ;;
                    6379)
                        print_status "Redis port - checking if it's our container..."
                        ;;
                    8000)
                        print_status "App port - checking if it's our container..."
                        ;;
                esac
            fi
        done
        
        # Stop any existing containers
        print_status "Stopping any existing containers..."
        docker-compose down 2>/dev/null || true
        
        # Start services
        print_status "Starting Docker services..."
        docker-compose up -d
        
        # Wait for services to be ready
        print_status "Waiting for services to be ready..."
        sleep 5
        
        # Check service health
        print_status "Checking service health..."
        docker-compose ps
        
        # Initialize database if needed
        if docker-compose exec -T postgres psql -U redbarsushi -d redbarsushi -c "SELECT 1 FROM location LIMIT 1;" >/dev/null 2>&1; then
            print_success "Database already initialized"
        else
            print_status "Initializing database..."
            docker-compose exec -T app python -m app.db_init
            print_success "Database initialized"
        fi
        
        print_success "Development environment is ready!"
        print_status "App: http://localhost:8000"
        print_status "API docs: http://localhost:8000/docs"
        print_status "Logs: docker-compose logs -f"
        ;;
        
    stop)
        print_status "Stopping development environment..."
        docker-compose down
        print_success "Development environment stopped"
        ;;
        
    restart)
        $0 stop
        $0 start
        ;;
        
    logs)
        docker-compose logs -f ${2:-}
        ;;
        
    shell)
        print_status "Opening shell in app container..."
        docker-compose exec app bash
        ;;
        
    test)
        print_status "Running tests..."
        docker-compose exec app pytest tests/ -v ${@:2}
        ;;
        
    clean)
        print_status "Cleaning development environment..."
        docker-compose down -v --remove-orphans
        docker system prune -f
        print_success "Environment cleaned"
        ;;
        
    status)
        print_status "Checking environment status..."
        docker-compose ps
        echo
        print_status "Port usage:"
        for port in 5432 6379 8000; do
            if check_port $port; then
                echo "Port $port: IN USE"
            else
                echo "Port $port: FREE"
            fi
        done
        ;;
        
    init-db)
        print_status "Initializing database..."
        docker-compose exec app python -m app.db_init
        print_success "Database initialized"
        ;;
        
    *)
        echo "Usage: $0 {start|stop|restart|logs|shell|test|clean|status|init-db}"
        echo
        echo "Commands:"
        echo "  start    - Start the development environment"
        echo "  stop     - Stop the development environment"
        echo "  restart  - Restart the development environment"
        echo "  logs     - View logs (optionally specify service: logs app)"
        echo "  shell    - Open a shell in the app container"
        echo "  test     - Run tests"
        echo "  clean    - Clean up all containers and volumes"
        echo "  status   - Check environment status"
        echo "  init-db  - Initialize the database"
        exit 1
        ;;
esac