#!/usr/bin/env python3
"""
Moodle Connection Test Script

Quick script to test your Moodle API connection with your specific credentials.
Run this to verify your setup before integrating with the full application.
"""

import os
import sys
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lms_api.services.moodle_service import MoodleService, MoodleError

def test_moodle_connection():
    """Test Moodle API connection with your credentials"""
    
    # Load environment variables
    load_dotenv()
    
    print("🔧 Moodle API Connection Test")
    print("=" * 40)
    
    # Check environment variables
    base_url = os.getenv('MOODLE_BASE_URL')
    token = os.getenv('MOODLE_TOKEN')
    
    print(f"Base URL: {base_url}")
    print(f"Token: {token[:8]}...{token[-8:] if token else 'NOT SET'}")
    print()
    
    if not base_url or not token:
        print("❌ ERROR: Missing environment variables!")
        print("Please set MOODLE_BASE_URL and MOODLE_TOKEN in your .env file")
        return False
    
    # Initialize Moodle service
    try:
        moodle = MoodleService()
        print("✅ MoodleService initialized successfully")
    except Exception as e:
        print(f"❌ ERROR: Failed to initialize MoodleService: {e}")
        return False
    
    # Test 1: Site Information
    print("\n🧪 Test 1: Getting site information...")
    try:
        site_info = moodle.get_site_info()
        print(f"✅ Success! Site: {site_info.get('sitename', 'Unknown')}")
        print(f"   Version: {site_info.get('version', 'Unknown')}")
        print(f"   Functions available: {len(site_info.get('functions', []))}")
        
        # Check for required functions
        functions = {func['name'] for func in site_info.get('functions', [])}
        required_functions = [
            'core_course_get_courses',
            'core_course_create_courses', 
            'core_user_get_users_by_field',
            'enrol_manual_enrol_users'
        ]
        
        print("   Required functions check:")
        for func in required_functions:
            if func in functions:
                print(f"   ✅ {func}")
            else:
                print(f"   ❌ {func} - NOT AVAILABLE")
        
    except MoodleError as e:
        print(f"❌ Moodle Error: {e}")
        print(f"   Error Code: {e.error_code}")
        return False
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        return False
    
    # Test 2: List Courses
    print("\n🧪 Test 2: Listing courses...")
    try:
        courses = moodle.list_courses()
        print(f"✅ Success! Found {len(courses)} courses")
        
        if courses:
            # Show first few courses
            for i, course in enumerate(courses[:3]):
                print(f"   Course {i+1}: {course.get('fullname', 'Unknown')} (ID: {course.get('id')})")
            if len(courses) > 3:
                print(f"   ... and {len(courses) - 3} more courses")
        else:
            print("   No courses found (this might be normal)")
            
    except MoodleError as e:
        print(f"❌ Moodle Error: {e}")
        if 'nopermissions' in str(e).lower():
            print("   💡 Tip: Check that your token user has 'moodle/course:view' capability")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
    
    # Test 3: Parameter Encoding
    print("\n🧪 Test 3: Testing parameter encoding...")
    try:
        from lms_api.services.moodle_service import MoodleParamEncoder
        
        test_data = {
            'courses': [
                {'fullname': 'Test Course', 'shortname': 'TEST'},
                {'fullname': 'Another Course', 'shortname': 'ANOTHER'}
            ],
            'options': {'limit': 10}
        }
        
        encoded = MoodleParamEncoder.encode_params(test_data)
        print("✅ Parameter encoding works correctly")
        print("   Sample encoded parameters:")
        for key, value in list(encoded.items())[:3]:
            print(f"   {key}: {value}")
        
    except Exception as e:
        print(f"❌ Parameter encoding error: {e}")
    
    print("\n" + "=" * 40)
    print("🎉 Connection test completed!")
    print("\nNext steps:")
    print("1. If any tests failed, check the Moodle admin configuration")
    print("2. Ensure your web service has the required functions enabled")
    print("3. Verify user capabilities for your token")
    print("4. Start your LMS backend: pserve development.ini")
    print("5. Test the API endpoints with curl commands")
    
    return True

if __name__ == "__main__":
    # Set your actual Moodle credentials here for testing
    test_credentials = {
        'MOODLE_BASE_URL': 'https://your-moodle-instance.com',  # Replace with your Moodle URL
        'MOODLE_TOKEN': 'a4f1a823c7e33f22c8234e9edf759e7d',     # Your actual token
        'MOODLE_TIMEOUT_MS': '15000',
        'MOODLE_DEBUG': 'true'
    }
    
    # Set environment variables for testing
    for key, value in test_credentials.items():
        os.environ[key] = value
    
    print("🚀 Using test credentials:")
    print(f"Token: a4f1a823c7e33f22c8234e9edf759e7d")
    print("Please update MOODLE_BASE_URL in this script with your actual Moodle URL")
    print()
    
    success = test_moodle_connection()
    sys.exit(0 if success else 1)