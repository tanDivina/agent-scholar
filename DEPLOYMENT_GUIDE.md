# Agent Scholar - Deployment Guide

This comprehensive guide covers deploying the Agent Scholar AI research assistant system to AWS using automated deployment scripts and best practices.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Detailed Deployment](#detailed-deployment)
- [Configuration](#configuration)
- [Environment Management](#environment-management)
- [Monitoring & Maintenance](#monitoring--maintenance)
- [Troubleshooting](#troubleshooting)
- [Security Considerations](#security-considerations)

## 🚀 Prerequisites

### Required Software

- **AWS CLI v2**: [Installation Guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- **Node.js 18+**: [Download](https://nodejs.org/)
- **Python 3.9+**: [Download](https://www.python.org/downloads/)
- **Git**: [Download](https://git-scm.com/downloads/)

### AWS Requirements

- AWS Account with appropriate permissions
- AWS CLI configured with credentials
- Sufficient service limits for:
  - Lambda functions (15+ functions)
  - API Gateway (1 REST API)
  - OpenSearch Serverless (1 collection)
  - S3 buckets (2-3 buckets)
  - Cognito User Pool (1 pool)

### Permissions Required

Your AWS user/role needs the following permissions:
- `CloudFormationFullAccess`
- `IAMFullAccess`
- `LambdaFullAccess`
- `APIGatewayFullAccess`
- `S3FullAccess`
- `OpenSearchServerlessFullAccess`
- `CognitoIdentityProviderFullAccess`
- `BedrockFullAccess`
- `CloudWatchFullAccess`

## ⚡ Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/your-org/agent-scholar.git
cd agent-scholar

# Make deployment script executable
chmod +x deploy.sh

# Run automated deployment
./deploy.sh
```

### 2. Access the Application

After successful deployment:

```bash
# Start the Streamlit application
source venv/bin/activate
streamlit run streamlit_app_secure.py
```

Navigate to `http://localhost:8501` and login with:
- **Email**: `user@example.com`
- **Password**: `UserPassword123!`

## 🔧 Detailed Deployment

### Step 1: Environment Preparation

```bash
# Check prerequisites
./deploy.sh --help

# Set environment variables (optional)
export AWS_REGION=us-east-1
export ENVIRONMENT=dev
export STACK_NAME=agent-scholar
```

### Step 2: Configuration

Create a `.env` file for local configuration:

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_PROFILE=default

# Environment
ENVIRONMENT=dev
STACK_NAME=agent-scholar

# Optional: External API Keys
SERP_API_KEY=your_serp_api_key
GOOGLE_API_KEY=your_google_api_key
GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id

# Optional: Alert Configuration
ALERT_EMAIL=admin@yourcompany.com
```

### Step 3: Deployment Options

#### Full Deployment (Recommended)
```bash
./deploy.sh
```

#### Environment-Specific Deployment
```bash
# Development
./deploy.sh --environment dev --region us-east-1

# Staging
./deploy.sh --environment staging --region us-west-2

# Production
./deploy.sh --environment prod --region us-east-1
```

#### Deployment with Options
```bash
# Skip tests (faster deployment)
./deploy.sh --skip-tests

# Deploy only infrastructure
./deploy.sh --deploy-only

# Skip build step
./deploy.sh --skip-build
```

### Step 4: Post-Deployment Verification

```bash
# Check deployment status
aws cloudformation describe-stacks --stack-name agent-scholar

# Test API endpoint
curl https://your-api-endpoint.amazonaws.com/health

# Run end-to-end tests
python tests/e2e/test_runner.py --all
```

## ⚙️ Configuration

### Infrastructure Configuration

The system can be configured through CDK context values:

```json
{
  "environment": "prod",
  "region": "us-east-1",
  "foundationModel": "anthropic.claude-3-sonnet-20240229-v1:0",
  "enableMfa": true,
  "alertEmail": "admin@yourcompany.com",
  "domainName": "agent-scholar.yourcompany.com"
}
```

### Application Configuration

Key configuration files:

- **`cdk.json`**: CDK configuration and context
- **`.env`**: Environment variables
- **`tests/e2e/test_config.json`**: Testing configuration
- **`streamlit_config.toml`**: Streamlit application settings

### Service Configuration

#### Lambda Functions
- **Memory**: Auto-optimized based on function type
- **Timeout**: 30s (orchestrator), 120s (document processing)
- **Concurrency**: Auto-scaling with reserved capacity

#### API Gateway
- **Throttling**: 2000 requests per second
- **Caching**: Enabled for GET requests
- **CORS**: Configured for web applications

#### OpenSearch
- **Capacity**: Serverless with auto-scaling
- **Security**: VPC endpoints and encryption
- **Backup**: Point-in-time recovery enabled

## 🌍 Environment Management

### Development Environment

```bash
# Deploy development environment
./deploy.sh --environment dev

# Features:
# - Relaxed security settings
# - Debug logging enabled
# - Sample data included
# - Cost-optimized resources
```

### Staging Environment

```bash
# Deploy staging environment
./deploy.sh --environment staging

# Features:
# - Production-like configuration
# - Performance testing enabled
# - Monitoring and alerting
# - Load testing capabilities
```

### Production Environment

```bash
# Deploy production environment
./deploy.sh --environment prod

# Features:
# - High availability
# - Enhanced security
# - Comprehensive monitoring
# - Auto-scaling enabled
# - Backup and disaster recovery
```

### Environment Promotion

```bash
# Promote from dev to staging
./deploy.sh --environment staging --skip-tests

# Promote from staging to production
./deploy.sh --environment prod --skip-tests
```

## 📊 Monitoring & Maintenance

### CloudWatch Dashboards

Access monitoring dashboards:
- **Performance Dashboard**: System-wide performance metrics
- **Lambda Metrics**: Function-specific performance
- **API Gateway Metrics**: Request latency and error rates
- **Security Dashboard**: Authentication and authorization metrics

### Automated Monitoring

The system includes automated monitoring for:
- **Performance Degradation**: Response time increases
- **Error Rate Spikes**: High error rates across services
- **Resource Utilization**: Memory and CPU usage
- **Security Events**: Failed authentication attempts

### Maintenance Tasks

#### Regular Maintenance
```bash
# Update dependencies
npm update
pip install -r requirements.txt --upgrade

# Run security audit
npm audit
pip-audit

# Update CDK
npm install -g aws-cdk@latest
```

#### Performance Optimization
```bash
# Run load tests
python tests/load/load_test_runner.py --url https://your-api-endpoint.amazonaws.com

# Analyze performance
python src/lambda/performance-monitor/monitor.py

# Review CloudWatch metrics
aws cloudwatch get-dashboard --dashboard-name agent-scholar-performance
```

### Backup and Recovery

#### Automated Backups
- **S3 Buckets**: Versioning and cross-region replication
- **OpenSearch**: Automated snapshots
- **Lambda Code**: Versioned deployments
- **Configuration**: Infrastructure as Code in Git

#### Disaster Recovery
```bash
# Backup current deployment
aws cloudformation describe-stacks --stack-name agent-scholar > backup-stack.json

# Restore from backup
./deploy.sh --environment prod --region us-west-2
```

## 🔍 Troubleshooting

### Common Issues

#### Deployment Failures

**Issue**: CDK bootstrap fails
```bash
# Solution: Bootstrap with explicit account/region
cdk bootstrap aws://123456789012/us-east-1
```

**Issue**: Lambda deployment timeout
```bash
# Solution: Increase timeout and retry
./deploy.sh --skip-tests --skip-build
```

**Issue**: OpenSearch capacity issues
```bash
# Solution: Check service limits
aws service-quotas get-service-quota --service-code opensearch --quota-code L-6408ABDE
```

#### Runtime Issues

**Issue**: High Lambda cold starts
```bash
# Solution: Enable provisioned concurrency
aws lambda put-provisioned-concurrency-config \
  --function-name agent-scholar-orchestrator \
  --provisioned-concurrency-config ProvisionedConcurrencyConfig=10
```

**Issue**: API Gateway timeouts
```bash
# Solution: Check Lambda function logs
aws logs tail /aws/lambda/agent-scholar-orchestrator --follow
```

**Issue**: Authentication failures
```bash
# Solution: Verify Cognito configuration
aws cognito-idp describe-user-pool --user-pool-id your-pool-id
```

### Debugging Commands

```bash
# Check stack status
aws cloudformation describe-stack-events --stack-name agent-scholar

# View Lambda logs
aws logs tail /aws/lambda/agent-scholar-orchestrator --follow

# Test API endpoints
curl -X POST https://your-api-endpoint.amazonaws.com/research \
  -H "Content-Type: application/json" \
  -d '{"query": "test query"}'

# Check OpenSearch health
aws opensearchserverless batch-get-collection --names agent-scholar-collection
```

### Performance Debugging

```bash
# Run performance tests
python tests/e2e/test_performance_benchmarks.py

# Check resource utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=agent-scholar-orchestrator \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-01T23:59:59Z \
  --period 3600 \
  --statistics Average
```

## 🔒 Security Considerations

### Security Best Practices

#### Infrastructure Security
- **VPC Isolation**: Lambda functions in private subnets
- **Encryption**: All data encrypted in transit and at rest
- **IAM Roles**: Least privilege access principles
- **WAF Protection**: Web Application Firewall enabled

#### Application Security
- **Authentication**: Cognito-based user management
- **Authorization**: Role-based access control
- **Input Validation**: Comprehensive input sanitization
- **Rate Limiting**: API and user-level rate limiting

#### Monitoring Security
- **Security Events**: Automated detection and alerting
- **Audit Logging**: Comprehensive audit trail
- **Vulnerability Scanning**: Regular security assessments
- **Compliance**: SOC 2 and GDPR considerations

### Security Configuration

```bash
# Enable MFA for production
./deploy.sh --environment prod --context enableMfa=true

# Configure security alerts
export ALERT_EMAIL=security@yourcompany.com
./deploy.sh --environment prod
```

### Security Monitoring

```bash
# Check security events
aws logs filter-log-events \
  --log-group-name /aws/lambda/agent-scholar-auth \
  --filter-pattern "ERROR"

# Review WAF logs
aws wafv2 get-sampled-requests \
  --web-acl-arn your-web-acl-arn \
  --rule-metric-name SecurityEvent \
  --scope REGIONAL \
  --time-window StartTime=2024-01-01T00:00:00Z,EndTime=2024-01-01T23:59:59Z \
  --max-items 100
```

## 📚 Additional Resources

### Documentation
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [Amazon Bedrock User Guide](https://docs.aws.amazon.com/bedrock/)
- [OpenSearch Serverless Guide](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless.html)

### Support
- **GitHub Issues**: [Report bugs and feature requests](https://github.com/your-org/agent-scholar/issues)
- **Documentation**: [Wiki and guides](https://github.com/your-org/agent-scholar/wiki)
- **Community**: [Discussions and Q&A](https://github.com/your-org/agent-scholar/discussions)

### Cost Optimization
- **AWS Cost Calculator**: Estimate deployment costs
- **Reserved Capacity**: Consider reserved instances for production
- **Resource Optimization**: Regular review of resource utilization

---

## 🎯 Quick Reference

### Essential Commands
```bash
# Deploy
./deploy.sh

# Destroy
./deploy.sh --destroy

# Test
python tests/e2e/test_runner.py --all

# Monitor
aws cloudwatch get-dashboard --dashboard-name agent-scholar-performance

# Logs
aws logs tail /aws/lambda/agent-scholar-orchestrator --follow
```

### Important URLs
- **API Endpoint**: Check `outputs.json` after deployment
- **CloudWatch Dashboard**: Available in deployment output
- **Cognito Console**: AWS Console → Cognito → User Pools
- **S3 Buckets**: AWS Console → S3

For additional help, run `./deploy.sh --help` or consult the troubleshooting section above.