#!/usr/bin/env python
"""
Debug script to test direct file serving
"""
import requests
import json

def test_file_endpoint():
    # Test the specific HTML file
    content_id = 3  # From the database query above
    
    base_url = "http://localhost:6543"  # Adjust if needed
    
    print("Testing file serving endpoints...")
    print("-" * 50)
    
    # Test 1: Get content info
    try:
        url = f"{base_url}/api/content/{content_id}"
        print(f"Testing: {url}")
        
        # You'll need to add authentication headers if required
        headers = {
            'Authorization': 'Bearer YOUR_TOKEN_HERE',  # Add your token
            'Content-Type': 'application/json'
        }
        
        response = requests.get(url, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Content info: {json.dumps(data, indent=2)}")
        else:
            print(f"Error response: {response.text}")
            
    except Exception as e:
        print(f"Error testing content endpoint: {e}")
    
    print("\n" + "-" * 50)
    
    # Test 2: Get file directly
    try:
        file_url = f"{base_url}/api/content/{content_id}/file"
        print(f"Testing file URL: {file_url}")
        
        response = requests.get(file_url, headers=headers)
        print(f"File response status: {response.status_code}")
        print(f"File response headers: {dict(response.headers)}")
        print(f"File content length: {len(response.content)}")
        
        if response.status_code != 200:
            print(f"File error response: {response.text}")
            
    except Exception as e:
        print(f"Error testing file endpoint: {e}")

if __name__ == "__main__":
    print("Note: Update the authorization token and base URL as needed")
    test_file_endpoint()