#!/usr/bin/env python3
"""
Simple test script to validate JetFriend API functionality
"""

import requests
import json
import sys

BASE_URL = "http://localhost:5000"

def test_health_endpoint():
    """Test the health check endpoint"""
    print("🏥 Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_ai_test_endpoint():
    """Test the AI test endpoint"""
    print("🤖 Testing AI test endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/test")
        if response.status_code in [200, 503]:  # 503 is expected without API key
            data = response.json()
            print(f"✅ AI test completed: {data}")
            return True
        else:
            print(f"❌ AI test failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ AI test error: {e}")
        return False

def test_chat_endpoint():
    """Test the chat endpoint"""
    print("💬 Testing chat endpoint...")
    try:
        payload = {"message": "Hello, this is a test message"}
        response = requests.post(
            f"{BASE_URL}/api/chat",
            headers={"Content-Type": "application/json"},
            json=payload
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Chat test passed: {data}")
            return True
        else:
            print(f"❌ Chat test failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Chat test error: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting JetFriend API tests...\n")
    
    tests = [
        test_health_endpoint,
        test_ai_test_endpoint,
        test_chat_endpoint
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()  # Add spacing between tests
    
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! JetFriend API is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the configuration.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
