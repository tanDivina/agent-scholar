#!/usr/bin/env python3
"""
Agent Scholar Streamlit Launcher

Simple launcher script for the Agent Scholar Streamlit interface.
Handles environment setup and configuration validation.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def check_requirements():
    """Check if required packages are installed."""
    required_packages = [
        'streamlit',
        'requests',
        'plotly',
        'pandas'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n💡 Install missing packages with:")
        print("   pip install -r requirements-streamlit.txt")
        return False
    
    print("✅ All required packages are installed")
    return True

def check_configuration():
    """Check if configuration files exist and are valid."""
    config_files = [
        '.streamlit/config.toml',
        '.streamlit/secrets.toml'
    ]
    
    missing_files = []
    
    for config_file in config_files:
        if not Path(config_file).exists():
            missing_files.append(config_file)
    
    if missing_files:
        print("⚠️  Missing configuration files:")
        for file in missing_files:
            print(f"   - {file}")
        print("\n💡 These files should be created automatically.")
        return False
    
    # Check if API URL is configured
    secrets_file = Path('.streamlit/secrets.toml')
    if secrets_file.exists():
        content = secrets_file.read_text()
        if 'your-api-gateway-url' in content:
            print("⚠️  Please update the API_BASE_URL in .streamlit/secrets.toml")
            print("   Replace 'your-api-gateway-url' with your actual API Gateway URL")
            return False
    
    print("✅ Configuration files are present")
    return True

def run_streamlit(port=8501, debug=False):
    """Run the Streamlit application."""
    cmd = [
        sys.executable, '-m', 'streamlit', 'run', 'streamlit_app.py',
        '--server.port', str(port),
        '--server.headless', 'true'
    ]
    
    if debug:
        cmd.extend(['--logger.level', 'debug'])
    
    print(f"🚀 Starting Agent Scholar on port {port}...")
    print(f"🌐 Open your browser to: http://localhost:{port}")
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n👋 Agent Scholar stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running Streamlit: {e}")
        sys.exit(1)

def main():
    """Main launcher function."""
    parser = argparse.ArgumentParser(description='Launch Agent Scholar Streamlit Interface')
    parser.add_argument('--port', type=int, default=8501, help='Port to run on (default: 8501)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--skip-checks', action='store_true', help='Skip requirement and configuration checks')
    
    args = parser.parse_args()
    
    print("🧠 Agent Scholar - Streamlit Interface Launcher")
    print("=" * 50)
    
    if not args.skip_checks:
        print("🔍 Checking requirements...")
        if not check_requirements():
            sys.exit(1)
        
        print("🔍 Checking configuration...")
        if not check_configuration():
            print("\n💡 You can still run the application, but you may need to configure the API URL.")
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                sys.exit(1)
    
    # Set environment variables if needed
    if 'API_BASE_URL' in os.environ:
        print(f"🔗 Using API URL from environment: {os.environ['API_BASE_URL']}")
    
    run_streamlit(port=args.port, debug=args.debug)

if __name__ == '__main__':
    main()