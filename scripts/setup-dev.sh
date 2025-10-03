#!/bin/bash

# Development environment setup script for Agent Scholar

set -e

echo "Setting up Agent Scholar development environment..."

# Check if Python 3.11+ is available
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "Error: Python 3.11 or higher is required. Found: $python_version"
    exit 1
fi

echo "✓ Python version check passed: $python_version"

# Install Node.js dependencies
echo "Installing Node.js dependencies..."
npm install

echo "✓ Node.js dependencies installed"

# Install Python development dependencies
echo "Installing Python development dependencies..."
pip3 install -r requirements-dev.txt

echo "✓ Python development dependencies installed"

# Create virtual environment for Lambda functions (optional)
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
    echo "To activate: source venv/bin/activate"
fi

# Build TypeScript
echo "Building TypeScript..."
npm run build

echo "✓ TypeScript build completed"

# Run basic tests
echo "Running basic tests..."
npm run test:unit

echo "✓ Basic tests passed"

echo ""
echo "🎉 Development environment setup complete!"
echo ""
echo "Next steps:"
echo "1. Configure AWS credentials: aws configure"
echo "2. Bootstrap CDK: npm run bootstrap"
echo "3. Deploy infrastructure: npm run deploy"
echo ""
echo "Available commands:"
echo "  npm run build          - Build TypeScript"
echo "  npm run test           - Run Jest tests"
echo "  npm run test:python    - Run Python tests"
echo "  npm run synth          - Synthesize CDK templates"
echo "  npm run deploy         - Deploy to AWS"
echo "  npm run destroy        - Destroy AWS resources"