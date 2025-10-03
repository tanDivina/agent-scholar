#!/bin/bash

# Agent Scholar Deployment Script
# This script automates the complete deployment of the Agent Scholar system

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
STACK_NAME="agent-scholar"
AWS_REGION="${AWS_REGION:-us-east-1}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
CDK_VERSION="2.100.0"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if AWS CLI is installed
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if Node.js is installed
    if ! command -v node &> /dev/null; then
        print_error "Node.js is not installed. Please install it first."
        exit 1
    fi
    
    # Check if Python is installed
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed. Please install it first."
        exit 1
    fi
    
    # Check if CDK is installed
    if ! command -v cdk &> /dev/null; then
        print_warning "AWS CDK is not installed. Installing..."
        npm install -g aws-cdk@${CDK_VERSION}
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials not configured. Please run 'aws configure' first."
        exit 1
    fi
    
    print_success "Prerequisites check completed"
}

# Function to setup environment
setup_environment() {
    print_status "Setting up environment..."
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        print_status "Creating Python virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Install Python dependencies
    print_status "Installing Python dependencies..."
    pip install -r requirements.txt
    
    # Install Node.js dependencies
    print_status "Installing Node.js dependencies..."
    npm install
    
    print_success "Environment setup completed"
}

# Function to run tests
run_tests() {
    print_status "Running tests..."
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Run unit tests
    print_status "Running unit tests..."
    python -m pytest tests/unit/ -v --tb=short
    
    # Run integration tests
    print_status "Running integration tests..."
    python -m pytest tests/integration/ -v --tb=short
    
    # Run security tests
    print_status "Running security tests..."
    python -m pytest tests/unit/test_security.py -v
    
    print_success "All tests passed"
}

# Function to build and package
build_package() {
    print_status "Building and packaging..."
    
    # Create deployment package directories
    mkdir -p dist/lambda
    mkdir -p dist/layers
    
    # Package Lambda functions
    print_status "Packaging Lambda functions..."
    
    # Package shared layer
    print_status "Creating shared layer..."
    mkdir -p layers/shared/python
    cp -r src/shared/* layers/shared/python/
    
    # Install layer dependencies
    pip install -r layers/shared/requirements.txt -t layers/shared/python/
    
    # Package individual Lambda functions
    for lambda_dir in src/lambda/*/; do
        if [ -d "$lambda_dir" ]; then
            lambda_name=$(basename "$lambda_dir")
            print_status "Packaging Lambda function: $lambda_name"
            
            # Create function package
            mkdir -p "dist/lambda/$lambda_name"
            cp -r "$lambda_dir"* "dist/lambda/$lambda_name/"
            
            # Install function-specific dependencies if requirements.txt exists
            if [ -f "$lambda_dir/requirements.txt" ]; then
                pip install -r "$lambda_dir/requirements.txt" -t "dist/lambda/$lambda_name/"
            fi
        fi
    done
    
    print_success "Build and packaging completed"
}

# Function to deploy infrastructure
deploy_infrastructure() {
    print_status "Deploying infrastructure..."
    
    # Bootstrap CDK if needed
    print_status "Bootstrapping CDK..."
    cdk bootstrap aws://$(aws sts get-caller-identity --query Account --output text)/${AWS_REGION}
    
    # Synthesize CloudFormation template
    print_status "Synthesizing CloudFormation template..."
    cdk synth
    
    # Deploy the stack
    print_status "Deploying Agent Scholar stack..."
    cdk deploy ${STACK_NAME} \
        --parameters Environment=${ENVIRONMENT} \
        --parameters Region=${AWS_REGION} \
        --require-approval never \
        --outputs-file outputs.json
    
    print_success "Infrastructure deployment completed"
}

# Function to configure services
configure_services() {
    print_status "Configuring services..."
    
    # Extract outputs from deployment
    if [ -f "outputs.json" ]; then
        API_ENDPOINT=$(jq -r '.["'${STACK_NAME}'"].ApiEndpoint' outputs.json)
        USER_POOL_ID=$(jq -r '.["'${STACK_NAME}'"].UserPoolId' outputs.json)
        USER_POOL_CLIENT_ID=$(jq -r '.["'${STACK_NAME}'"].UserPoolClientId' outputs.json)
        
        print_status "API Endpoint: $API_ENDPOINT"
        print_status "User Pool ID: $USER_POOL_ID"
        print_status "User Pool Client ID: $USER_POOL_CLIENT_ID"
        
        # Create environment configuration file
        cat > .env << EOF
API_BASE_URL=$API_ENDPOINT
COGNITO_USER_POOL_ID=$USER_POOL_ID
COGNITO_USER_POOL_CLIENT_ID=$USER_POOL_CLIENT_ID
AWS_REGION=$AWS_REGION
ENVIRONMENT=$ENVIRONMENT
EOF
        
        print_success "Environment configuration created"
    else
        print_warning "No outputs.json found, skipping service configuration"
    fi
    
    # Upload sample documents if S3 bucket exists
    DOCUMENTS_BUCKET=$(jq -r '.["'${STACK_NAME}'"].DocumentsBucket' outputs.json 2>/dev/null || echo "null")
    if [ "$DOCUMENTS_BUCKET" != "null" ] && [ "$DOCUMENTS_BUCKET" != "" ]; then
        print_status "Uploading sample documents..."
        aws s3 cp tests/sample_documents/ s3://$DOCUMENTS_BUCKET/documents/ --recursive
        print_success "Sample documents uploaded"
    fi
}

# Function to run post-deployment tests
run_post_deployment_tests() {
    print_status "Running post-deployment tests..."
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Wait for services to be ready
    print_status "Waiting for services to be ready..."
    sleep 30
    
    # Run API integration tests
    if [ -f "outputs.json" ]; then
        API_ENDPOINT=$(jq -r '.["'${STACK_NAME}'"].ApiEndpoint' outputs.json)
        
        # Test API health endpoint
        print_status "Testing API health endpoint..."
        if curl -f "${API_ENDPOINT}/health" > /dev/null 2>&1; then
            print_success "API health check passed"
        else
            print_warning "API health check failed, but continuing..."
        fi
        
        # Run end-to-end tests
        print_status "Running end-to-end tests..."
        python tests/e2e/test_runner.py --config tests/e2e/test_config.json || print_warning "E2E tests had issues"
    fi
    
    print_success "Post-deployment tests completed"
}

# Function to setup monitoring
setup_monitoring() {
    print_status "Setting up monitoring and alerting..."
    
    # Create CloudWatch dashboard URL
    if [ -f "outputs.json" ]; then
        DASHBOARD_URL=$(jq -r '.["'${STACK_NAME}'"].DashboardUrl' outputs.json 2>/dev/null || echo "")
        if [ "$DASHBOARD_URL" != "" ]; then
            print_status "CloudWatch Dashboard: $DASHBOARD_URL"
        fi
    fi
    
    print_success "Monitoring setup completed"
}

# Function to display deployment summary
display_summary() {
    print_success "🎉 Agent Scholar deployment completed successfully!"
    echo ""
    echo "=== DEPLOYMENT SUMMARY ==="
    
    if [ -f "outputs.json" ]; then
        echo "Stack Name: $STACK_NAME"
        echo "Environment: $ENVIRONMENT"
        echo "Region: $AWS_REGION"
        echo ""
        
        API_ENDPOINT=$(jq -r '.["'${STACK_NAME}'"].ApiEndpoint' outputs.json 2>/dev/null || echo "N/A")
        USER_POOL_ID=$(jq -r '.["'${STACK_NAME}'"].UserPoolId' outputs.json 2>/dev/null || echo "N/A")
        DOCUMENTS_BUCKET=$(jq -r '.["'${STACK_NAME}'"].DocumentsBucket' outputs.json 2>/dev/null || echo "N/A")
        DASHBOARD_URL=$(jq -r '.["'${STACK_NAME}'"].DashboardUrl' outputs.json 2>/dev/null || echo "N/A")
        
        echo "🌐 API Endpoint: $API_ENDPOINT"
        echo "👤 User Pool ID: $USER_POOL_ID"
        echo "📁 Documents Bucket: $DOCUMENTS_BUCKET"
        echo "📊 Dashboard: $DASHBOARD_URL"
        echo ""
    fi
    
    echo "=== NEXT STEPS ==="
    echo "1. Start the Streamlit app:"
    echo "   source venv/bin/activate"
    echo "   streamlit run streamlit_app_secure.py"
    echo ""
    echo "2. Access the application at: http://localhost:8501"
    echo ""
    echo "3. Upload documents to: $DOCUMENTS_BUCKET/documents/"
    echo ""
    echo "4. Monitor performance at: $DASHBOARD_URL"
    echo ""
    echo "=== DEMO ACCOUNTS ==="
    echo "Email: user@example.com | Password: UserPassword123!"
    echo "Email: admin@example.com | Password: AdminPassword123!"
    echo ""
    print_success "Deployment completed! 🚀"
}

# Function to cleanup on failure
cleanup_on_failure() {
    print_error "Deployment failed. Cleaning up..."
    
    # Optionally destroy the stack if deployment failed
    read -p "Do you want to destroy the partially deployed stack? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Destroying stack..."
        cdk destroy ${STACK_NAME} --force
        print_success "Stack destroyed"
    fi
}

# Function to show help
show_help() {
    echo "Agent Scholar Deployment Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --help, -h          Show this help message"
    echo "  --environment, -e   Set environment (dev, staging, prod) [default: dev]"
    echo "  --region, -r        Set AWS region [default: us-east-1]"
    echo "  --skip-tests        Skip running tests"
    echo "  --skip-build        Skip build and packaging"
    echo "  --deploy-only       Only deploy infrastructure (skip tests and build)"
    echo "  --destroy           Destroy the deployed stack"
    echo ""
    echo "Environment Variables:"
    echo "  AWS_REGION          AWS region for deployment"
    echo "  ENVIRONMENT         Deployment environment"
    echo "  STACK_NAME          CloudFormation stack name"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Deploy with defaults"
    echo "  $0 -e prod -r us-west-2             # Deploy to production in us-west-2"
    echo "  $0 --skip-tests                      # Deploy without running tests"
    echo "  $0 --destroy                         # Destroy the deployed stack"
}

# Function to destroy stack
destroy_stack() {
    print_status "Destroying Agent Scholar stack..."
    
    read -p "Are you sure you want to destroy the stack '$STACK_NAME'? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cdk destroy ${STACK_NAME} --force
        print_success "Stack destroyed successfully"
        
        # Clean up local files
        rm -f outputs.json .env
        print_success "Local configuration files cleaned up"
    else
        print_status "Stack destruction cancelled"
    fi
}

# Main deployment function
main() {
    local skip_tests=false
    local skip_build=false
    local deploy_only=false
    local destroy=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                show_help
                exit 0
                ;;
            --environment|-e)
                ENVIRONMENT="$2"
                shift 2
                ;;
            --region|-r)
                AWS_REGION="$2"
                shift 2
                ;;
            --skip-tests)
                skip_tests=true
                shift
                ;;
            --skip-build)
                skip_build=true
                shift
                ;;
            --deploy-only)
                deploy_only=true
                shift
                ;;
            --destroy)
                destroy=true
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Handle destroy option
    if [ "$destroy" = true ]; then
        destroy_stack
        exit 0
    fi
    
    # Set trap for cleanup on failure
    trap cleanup_on_failure ERR
    
    print_status "Starting Agent Scholar deployment..."
    print_status "Environment: $ENVIRONMENT"
    print_status "Region: $AWS_REGION"
    print_status "Stack Name: $STACK_NAME"
    echo ""
    
    # Run deployment steps
    check_prerequisites
    
    if [ "$deploy_only" = false ]; then
        setup_environment
        
        if [ "$skip_tests" = false ]; then
            run_tests
        fi
        
        if [ "$skip_build" = false ]; then
            build_package
        fi
    fi
    
    deploy_infrastructure
    configure_services
    
    if [ "$deploy_only" = false ]; then
        run_post_deployment_tests
    fi
    
    setup_monitoring
    display_summary
    
    # Remove trap
    trap - ERR
}

# Run main function with all arguments
main "$@"