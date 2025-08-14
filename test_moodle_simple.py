#!/usr/bin/env python3
"""
Simple Moodle API Connection Test
"""

import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_moodle_connection():
    """Test basic Moodle API connection"""
    
    # Configuration
    base_url = os.getenv('MOODLE_URL', 'http://172.16.10.142/moodle')
    token = os.getenv('MOODLE_TOKEN', 'a4f1a823c7e33f22c8234e9edf759e7d')
    rest_url = f"{base_url}/webservice/rest/server.php"
    
    print("="*50)
    print("MOODLE API CONNECTION TEST")
    print("="*50)
    print(f"Base URL: {base_url}")
    print(f"Token: {token[:8]}...{token[-8:]}")
    print(f"REST Endpoint: {rest_url}")
    print("-"*50)
    
    # Test 1: Basic Connection
    print("\n[TEST 1] Testing basic connection...")
    
    params = {
        'wstoken': token,
        'wsfunction': 'core_webservice_get_site_info',
        'moodlewsrestformat': 'json'
    }
    
    try:
        response = requests.get(rest_url, params=params, timeout=30)
        print(f"HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if 'exception' in data:
                print(f"ERROR: {data['message']}")
                return False
            else:
                print("SUCCESS: Connected to Moodle!")
                print(f"Site Name: {data.get('sitename', 'Unknown')}")
                print(f"Site URL: {data.get('siteurl', 'Unknown')}")
                print(f"Moodle Version: {data.get('release', 'Unknown')}")
                print(f"User: {data.get('firstname', '')} {data.get('lastname', '')}")
        else:
            print(f"ERROR: HTTP {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Network request failed - {str(e)}")
        return False
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON response - {str(e)}")
        return False
    
    # Test 2: List Courses
    print("\n[TEST 2] Testing course listing...")
    
    params = {
        'wstoken': token,
        'wsfunction': 'core_course_get_courses',
        'moodlewsrestformat': 'json'
    }
    
    try:
        response = requests.get(rest_url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if 'exception' in data:
                print(f"ERROR: {data['message']}")
            else:
                courses = data if isinstance(data, list) else []
                print(f"SUCCESS: Found {len(courses)} courses")
                
                for i, course in enumerate(courses[:3], 1):  # Show first 3
                    print(f"  {i}. ID: {course.get('id')} - {course.get('fullname', 'Unknown')}")
        else:
            print(f"ERROR: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return False
    
    # Test 3: Test Course Creation Function (without actually creating)
    print("\n[TEST 3] Testing course creation access...")
    
    # Just test if we have the function available
    params = {
        'wstoken': token,
        'wsfunction': 'core_webservice_get_site_info',
        'moodlewsrestformat': 'json'
    }
    
    try:
        response = requests.get(rest_url, params=params, timeout=30)
        data = response.json()
        
        if 'functions' in data:
            available_functions = [f['name'] for f in data['functions']]
            
            # Check for course creation function
            if 'core_course_create_courses' in available_functions:
                print("SUCCESS: Course creation function is available")
            else:
                print("WARNING: Course creation function not available")
            
            # Check for other important functions
            important_functions = [
                'core_course_get_courses',
                'core_course_update_courses',
                'core_user_get_users_by_field',
                'core_course_get_categories'
            ]
            
            available_important = [f for f in important_functions if f in available_functions]
            print(f"Available functions: {len(available_important)}/{len(important_functions)}")
            
            for func in available_important:
                print(f"  + {func}")
                
        else:
            print("INFO: Function list not available in site info")
            
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return False
    
    print("\n" + "="*50)
    print("MOODLE API TEST COMPLETED SUCCESSFULLY!")
    print("Your Moodle integration is ready to use.")
    print("="*50)
    
    return True

if __name__ == '__main__':
    success = test_moodle_connection()
    exit(0 if success else 1)