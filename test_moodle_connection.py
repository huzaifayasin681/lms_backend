#!/usr/bin/env python3
"""
Moodle Connection Test Script

Tests the Moodle API connection using the existing MoodleService class.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lms_api.services.moodle_service import MoodleService, MoodleError

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_moodle_connection():
    """Test Moodle API connection and basic functionality"""
    
    print("=" * 60)
    print("MOODLE API CONNECTION TEST")
    print("=" * 60)
    
    try:
        # Initialize Moodle service
        print("1. Initializing Moodle service...")
        moodle = MoodleService()
        print(f"   ✓ Base URL: {moodle.base_url}")
        print(f"   ✓ Token configured: {'Yes' if moodle.token else 'No'}")
        print(f"   ✓ Timeout: {moodle.timeout_seconds}s")
        
        # Test 1: Get site info
        print("\n2. Testing site info...")
        site_info = moodle.get_site_info()
        print(f"   ✓ Site name: {site_info.get('sitename', 'N/A')}")
        print(f"   ✓ Version: {site_info.get('version', 'N/A')}")
        print(f"   ✓ Release: {site_info.get('release', 'N/A')}")
        print(f"   ✓ User ID: {site_info.get('userid', 'N/A')}")
        print(f"   ✓ Username: {site_info.get('username', 'N/A')}")
        
        # Test 2: List available functions
        print("\n3. Available web service functions:")
        functions = site_info.get('functions', [])
        if functions:
            print(f"   ✓ Total functions available: {len(functions)}")
            # Show some key functions
            key_functions = [
                'core_course_get_courses',
                'core_course_create_courses', 
                'core_user_get_users_by_field',
                'enrol_manual_enrol_users'
            ]
            for func_name in key_functions:
                found = any(f.get('name') == func_name for f in functions)
                status = "✓" if found else "✗"
                print(f"   {status} {func_name}")
        else:
            print("   ⚠ No functions list available")
        
        # Test 3: List courses
        print("\n4. Testing course listing...")
        courses = moodle.list_courses()
        print(f"   ✓ Found {len(courses)} courses")
        
        if courses:
            print("   Sample courses:")
            for i, course in enumerate(courses[:3]):  # Show first 3 courses
                print(f"     - ID: {course.get('id')}, Name: {course.get('fullname', 'N/A')}")
        
        # Test 4: Test user lookup (if available)
        print("\n5. Testing user lookup...")
        try:
            # Try to find the admin user
            admin_username = site_info.get('username')
            if admin_username:
                users = moodle.get_users_by_field('username', [admin_username])
                if users:
                    user = users[0]
                    print(f"   ✓ Found admin user: {user.get('fullname', 'N/A')} ({user.get('email', 'N/A')})")
                else:
                    print("   ⚠ Admin user not found in lookup")
            else:
                print("   ⚠ No username available for lookup test")
        except Exception as e:
            print(f"   ⚠ User lookup test failed: {str(e)}")
        
        print("\n" + "=" * 60)
        print("✅ MOODLE CONNECTION TEST PASSED")
        print("✅ All basic functionality is working")
        print("=" * 60)
        
        return True
        
    except MoodleError as e:
        print(f"\n❌ Moodle API Error: {str(e)}")
        if hasattr(e, 'error_code'):
            print(f"   Error Code: {e.error_code}")
        if hasattr(e, 'status_code'):
            print(f"   HTTP Status: {e.status_code}")
        return False
        
    except Exception as e:
        print(f"\n❌ Unexpected Error: {str(e)}")
        return False

def test_environment_config():
    """Test environment configuration"""
    print("\n" + "=" * 60)
    print("ENVIRONMENT CONFIGURATION CHECK")
    print("=" * 60)
    
    required_vars = {
        'MOODLE_BASE_URL': os.getenv('MOODLE_BASE_URL'),
        'MOODLE_TOKEN': os.getenv('MOODLE_TOKEN')
    }
    
    all_configured = True
    for var_name, var_value in required_vars.items():
        if var_value:
            # Mask token for security
            display_value = var_value if var_name != 'MOODLE_TOKEN' else f"{var_value[:8]}...{var_value[-4:]}"
            print(f"✓ {var_name}: {display_value}")
        else:
            print(f"❌ {var_name}: Not configured")
            all_configured = False
    
    optional_vars = {
        'MOODLE_TIMEOUT_MS': os.getenv('MOODLE_TIMEOUT_MS', '15000'),
        'MOODLE_DEBUG': os.getenv('MOODLE_DEBUG', 'false')
    }
    
    print("\nOptional configuration:")
    for var_name, var_value in optional_vars.items():
        print(f"  {var_name}: {var_value}")
    
    return all_configured

if __name__ == "__main__":
    print("Starting Moodle API connection test...\n")
    
    # Test environment configuration first
    config_ok = test_environment_config()
    
    if not config_ok:
        print("\n❌ Environment configuration incomplete. Please check your .env file.")
        sys.exit(1)
    
    # Test Moodle connection
    success = test_moodle_connection()
    
    if success:
        print("\n🎉 Ready to integrate with LMS frontend!")
        sys.exit(0)
    else:
        print("\n💥 Connection test failed. Please check your Moodle configuration.")
        sys.exit(1)