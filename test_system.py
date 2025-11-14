#!/usr/bin/env python3
"""
Complete System Test for Zalo Bot with AWS Bedrock
Tests AWS connection, MongoDB, and Agent functionality
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_aws_connection():
    """Test AWS Bedrock connection"""
    print("=" * 60)
    print("1. Testing AWS Bedrock Connection")
    print("=" * 60)
    
    try:
        import boto3
        
        profile = os.getenv('AWS_PROFILE', 'david_gapv')
        region = os.getenv('AWS_REGION', 'us-west-2')
        
        print(f"Profile: {profile}")
        print(f"Region: {region}")
        
        session = boto3.Session(profile_name=profile, region_name=region)
        bedrock = session.client('bedrock-runtime')
        
        credentials = session.get_credentials()
        print(f"Access Key: {credentials.access_key[:8]}...")
        print(f"✓ Successfully connected to AWS Bedrock")
        print(f"✓ Using region: {bedrock.meta.region_name}")
        
        return True
    except Exception as e:
        print(f"✗ AWS Connection Failed: {e}")
        return False


def test_mongodb_connection():
    """Test MongoDB connection"""
    print("\n" + "=" * 60)
    print("2. Testing MongoDB Connection")
    print("=" * 60)
    
    try:
        from uit_knowledge_base_mongodb import UITMongoKnowledgeBase
        
        mongodb_uri = os.getenv('MONGODB_URI')
        print(f"URI: {mongodb_uri[:30]}...")
        
        kb = UITMongoKnowledgeBase(mongodb_uri=mongodb_uri)
        doc_count = kb.count_documents()
        
        print(f"✓ Connected to MongoDB")
        print(f"✓ Total documents: {doc_count}")
        
        # Test search
        results = kb.full_text_search("UIT tuyển sinh", limit=1)
        if results:
            print(f"✓ Full-text search working")
            print(f"  Sample result: {results[0]['title'][:50]}...")
        
        return True
    except Exception as e:
        print(f"✗ MongoDB Connection Failed: {e}")
        return False


def test_agent():
    """Test Google Search Agent"""
    print("\n" + "=" * 60)
    print("3. Testing Google Search Agent")
    print("=" * 60)
    
    try:
        from google_search_agent_mongodb import GoogleSearchAgent
        
        print("Initializing agent...")
        agent = GoogleSearchAgent()
        print("✓ Agent initialized successfully")
        
        print("\nTesting with a simple query...")
        response = agent.chat("Hello, can you help me?")
        
        if response and len(response) > 0:
            print("✓ Agent responded successfully")
            print(f"✓ Response length: {len(response)} characters")
            print(f"\nResponse preview:\n{response[:200]}...")
            return True
        else:
            print("✗ Agent returned empty response")
            return False
            
    except Exception as e:
        print(f"✗ Agent Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_flask_service():
    """Test Flask service status"""
    print("\n" + "=" * 60)
    print("4. Testing Flask Service")
    print("=" * 60)
    
    try:
        import requests
        
        # Test health endpoint
        response = requests.get('http://localhost:5000/health', timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print("✓ Flask service is running")
            print(f"✓ Status: {data.get('status')}")
            print(f"✓ Agent: {data.get('agent')}")
            print(f"✓ MongoDB: {data.get('mongodb')}")
            return True
        else:
            print(f"✗ Service returned status code: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("✗ Flask service is not running")
        print("  Run './restart.sh' to start the service")
        return False
    except Exception as e:
        print(f"✗ Service Test Failed: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "█" * 60)
    print("█" + " " * 58 + "█")
    print("█" + "  ZALO BOT SYSTEM TEST - AWS BEDROCK & MONGODB".center(58) + "█")
    print("█" + " " * 58 + "█")
    print("█" * 60 + "\n")
    
    results = {}
    
    # Run tests
    results['AWS'] = test_aws_connection()
    results['MongoDB'] = test_mongodb_connection()
    results['Agent'] = test_agent()
    results['Flask'] = test_flask_service()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name:15} : {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED - SYSTEM IS READY!")
    else:
        print("✗ SOME TESTS FAILED - CHECK LOGS ABOVE")
    print("=" * 60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
