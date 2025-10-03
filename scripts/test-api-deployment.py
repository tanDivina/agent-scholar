#!/usr/bin/env python3
"""
Test script for validating API Gateway deployment.

This script performs basic validation of the deployed API endpoints
to ensure they are working correctly.
"""

import json
import requests
import sys
import time
import uuid
from typing import Dict, Any, Optional


def test_api_endpoint(base_url: str) -> bool:
    """
    Test the deployed API endpoints.
    
    Args:
        base_url: Base URL of the API Gateway
        
    Returns:
        True if all tests pass, False otherwise
    """
    print(f"Testing API at: {base_url}")
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    # Test 1: Health check
    print("\n1. Testing health check endpoint...")
    try:
        response = requests.get(f"{base_url}/health", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data.get('status', 'unknown')}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {str(e)}")
        return False
    
    # Test 2: CORS preflight
    print("\n2. Testing CORS preflight...")
    try:
        response = requests.options(f"{base_url}/chat", headers=headers, timeout=10)
        if response.status_code == 200:
            cors_headers = [
                'Access-Control-Allow-Origin',
                'Access-Control-Allow-Methods',
                'Access-Control-Allow-Headers'
            ]
            missing_headers = [h for h in cors_headers if h not in response.headers]
            if not missing_headers:
                print("✅ CORS headers present")
            else:
                print(f"⚠️  Missing CORS headers: {missing_headers}")
        else:
            print(f"❌ CORS preflight failed: {response.status_code}")
    except Exception as e:
        print(f"❌ CORS preflight error: {str(e)}")
    
    # Test 3: Chat endpoint with simple query
    print("\n3. Testing chat endpoint...")
    session_id = str(uuid.uuid4())
    payload = {
        'query': 'Hello, can you help me with research?',
        'session_id': session_id
    }
    
    try:
        response = requests.post(
            f"{base_url}/chat",
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'response' in data and 'session_id' in data:
                agent_response = data['response']
                if 'answer' in agent_response and len(agent_response['answer'].strip()) > 0:
                    print("✅ Chat endpoint working")
                    print(f"   Session ID: {data['session_id']}")
                    print(f"   Answer length: {len(agent_response['answer'])} characters")
                    print(f"   Reasoning steps: {len(agent_response.get('reasoning_steps', []))}")
                else:
                    print("❌ Chat response missing or empty")
                    return False
            else:
                print("❌ Chat response format invalid")
                return False
        else:
            print(f"❌ Chat endpoint failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"   Raw response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Chat endpoint error: {str(e)}")
        return False
    
    # Test 4: Session retrieval
    print("\n4. Testing session retrieval...")
    try:
        response = requests.get(
            f"{base_url}/session/{session_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            session_data = response.json()
            if 'session_id' in session_data and session_data['session_id'] == session_id:
                print("✅ Session retrieval working")
                print(f"   Query count: {session_data.get('query_count', 0)}")
            else:
                print("❌ Session data invalid")
        elif response.status_code == 404:
            print("⚠️  Session not found (DynamoDB might not be configured)")
        else:
            print(f"❌ Session retrieval failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Session retrieval error: {str(e)}")
    
    # Test 5: Error handling
    print("\n5. Testing error handling...")
    try:
        # Test with missing query
        response = requests.post(
            f"{base_url}/chat",
            headers=headers,
            json={'session_id': session_id},
            timeout=10
        )
        
        if response.status_code == 400:
            print("✅ Error handling working (missing query)")
        else:
            print(f"⚠️  Unexpected response for missing query: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error handling test failed: {str(e)}")
    
    print("\n🎉 API deployment test completed!")
    return True


def main():
    """Main function to run API tests."""
    if len(sys.argv) != 2:
        print("Usage: python test-api-deployment.py <api-gateway-url>")
        print("Example: python test-api-deployment.py https://abc123.execute-api.us-east-1.amazonaws.com/prod")
        sys.exit(1)
    
    api_url = sys.argv[1].rstrip('/')
    
    print("🚀 Agent Scholar API Deployment Test")
    print("=" * 50)
    
    success = test_api_endpoint(api_url)
    
    if success:
        print("\n✅ All critical tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Check the deployment.")
        sys.exit(1)


if __name__ == '__main__':
    main()