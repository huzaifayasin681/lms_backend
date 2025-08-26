#!/usr/bin/env python3
"""
Direct Moodle API test script
"""

import os
import sys
from dotenv import load_dotenv

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

from lms_api.services.moodle_service import MoodleService

def test_moodle_connection():
    """Test direct connection to Moodle"""
    print("=== Moodle Direct Connection Test ===")
    
    # Print environment variables
    print(f"MOODLE_BASE_URL: {os.getenv('MOODLE_BASE_URL', 'NOT SET')}")
    print(f"MOODLE_TOKEN: {'SET' if os.getenv('MOODLE_TOKEN') else 'NOT SET'}")
    
    try:
        # Create Moodle service
        moodle = MoodleService()
        print("✅ Moodle service created successfully")
        
        # Test site info
        print("\n--- Testing Site Info ---")
        site_info = moodle.get_site_info()
        print(f"Site Name: {site_info.get('sitename', 'Unknown')}")
        print(f"Version: {site_info.get('version', 'Unknown')}")
        print(f"Release: {site_info.get('release', 'Unknown')}")
        
        # Test courses
        print("\n--- Testing Courses ---")
        courses = moodle.list_courses()
        print(f"Total courses found: {len(courses)}")
        
        if courses:
            print("First 3 courses:")
            for i, course in enumerate(courses[:3]):
                print(f"  {i+1}. {course.get('fullname', 'No name')} (ID: {course.get('id', 'No ID')})")
        else:
            print("No courses found - this might be normal if Moodle is empty")
            
        # Test categories
        print("\n--- Testing Categories ---")
        categories = moodle.get_course_categories()
        print(f"Total categories found: {len(categories)}")
        
        if categories:
            print("Categories:")
            for cat in categories[:5]:
                print(f"  - {cat.get('name', 'No name')} (ID: {cat.get('id', 'No ID')})")
        
        print("\n✅ All tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_moodle_connection()
    sys.exit(0 if success else 1)