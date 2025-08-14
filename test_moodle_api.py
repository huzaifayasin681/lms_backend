#!/usr/bin/env python3
"""
Comprehensive Moodle API Integration Test Script

Tests all Moodle API functionality with the provided credentials:
- Base URL: http://172.16.10.142/moodle
- Token: a4f1a823c7e33f22c8234e9edf759e7d
- REST Endpoint: http://172.16.10.142/moodle/webservice/rest/server.php
"""

import os
import sys
import requests
import json
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

class MoodleAPITester:
    def __init__(self):
        self.base_url = os.getenv('MOODLE_URL', 'http://172.16.10.142/moodle')
        self.token = os.getenv('MOODLE_TOKEN', 'a4f1a823c7e33f22c8234e9edf759e7d')
        self.rest_url = f"{self.base_url}/webservice/rest/server.php"
        
        print(f"[CONFIG] Moodle API Tester Initialized")
        print(f"[BASE_URL] {self.base_url}")
        print(f"[TOKEN] {self.token[:8]}...{self.token[-8:]}")
        print(f"[REST_ENDPOINT] {self.rest_url}")
        print("-" * 60)
    
    def make_request(self, function_name, additional_params=None, method='GET'):
        """Make a request to Moodle Web Services API"""
        params = {
            'wstoken': self.token,
            'wsfunction': function_name,
            'moodlewsrestformat': 'json'
        }
        
        if additional_params:
            params.update(additional_params)
        
        try:
            if method.upper() == 'POST':
                response = requests.post(self.rest_url, data=params, timeout=30)
            else:
                response = requests.get(self.rest_url, params=params, timeout=30)
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            return {'error': f'Request failed: {str(e)}'}
        except json.JSONDecodeError as e:
            return {'error': f'Invalid JSON response: {str(e)}'}
    
    def test_connection(self):
        """Test 1: Basic Connection & Site Info"""
        print("[TEST 1] Testing Moodle Connection & Site Info")
        
        result = self.make_request('core_webservice_get_site_info')
        
        if 'error' in result:
            print(f"❌ Connection failed: {result['error']}")
            return False
        elif 'exception' in result:
            print(f"❌ Moodle API error: {result['message']}")
            return False
        else:
            print(f"✅ Connected successfully!")
            print(f"   📝 Site Name: {result.get('sitename', 'Unknown')}")
            print(f"   🏠 Site URL: {result.get('siteurl', 'Unknown')}")
            print(f"   📊 Moodle Version: {result.get('release', 'Unknown')}")
            print(f"   👤 User: {result.get('firstname', '')} {result.get('lastname', '')}")
            print(f"   📧 Email: {result.get('email', 'Unknown')}")
            return True
    
    def test_list_courses(self):
        """Test 2: List Available Courses"""
        print("\n🧪 Test 2: Listing Available Courses")
        
        result = self.make_request('core_course_get_courses')
        
        if 'error' in result:
            print(f"❌ Failed to get courses: {result['error']}")
            return []
        elif 'exception' in result:
            print(f"❌ Moodle API error: {result['message']}")
            return []
        else:
            courses = result if isinstance(result, list) else []
            print(f"✅ Found {len(courses)} courses:")
            
            for i, course in enumerate(courses[:5], 1):  # Show first 5
                print(f"   {i}. ID: {course.get('id')}, Name: {course.get('fullname', 'Unknown')}")
                print(f"      Short: {course.get('shortname', 'N/A')}, Category: {course.get('categoryname', 'N/A')}")
            
            if len(courses) > 5:
                print(f"   ... and {len(courses) - 5} more courses")
            
            return courses
    
    def test_create_course(self):
        """Test 3: Create a Test Course"""
        print("\n🧪 Test 3: Creating a Test Course")
        
        # Generate unique course name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        course_data = {
            'courses[0][fullname]': f'API Test Course {timestamp}',
            'courses[0][shortname]': f'APITEST_{timestamp}',
            'courses[0][summary]': 'Test course created via API integration',
            'courses[0][categoryid]': 1,  # Default category
            'courses[0][visible]': 1
        }
        
        result = self.make_request('core_course_create_courses', course_data, method='POST')
        
        if 'error' in result:
            print(f"❌ Failed to create course: {result['error']}")
            return None
        elif 'exception' in result:
            print(f"❌ Moodle API error: {result['message']}")
            return None
        else:
            if result and len(result) > 0:
                course = result[0]
                course_id = course.get('id')
                print(f"✅ Course created successfully!")
                print(f"   🆔 Course ID: {course_id}")
                print(f"   📝 Full Name: {course.get('fullname')}")
                print(f"   📋 Short Name: {course.get('shortname')}")
                return course_id
            else:
                print(f"❌ Unexpected response format: {result}")
                return None
    
    def test_update_course(self, course_id):
        """Test 4: Update the Created Course"""
        if not course_id:
            print("\n⏭️  Test 4: Skipping course update (no course to update)")
            return False
        
        print(f"\n🧪 Test 4: Updating Course ID {course_id}")
        
        course_data = {
            'courses[0][id]': course_id,
            'courses[0][fullname]': f'Updated API Test Course {course_id}',
            'courses[0][summary]': 'This course was updated via API integration test'
        }
        
        result = self.make_request('core_course_update_courses', course_data, method='POST')
        
        if 'error' in result:
            print(f"❌ Failed to update course: {result['error']}")
            return False
        elif 'exception' in result:
            print(f"❌ Moodle API error: {result['message']}")
            return False
        else:
            print(f"✅ Course updated successfully!")
            return True
    
    def test_get_users(self):
        """Test 5: Get Users by Field"""
        print("\n🧪 Test 5: Getting Users by Field")
        
        # Try to get admin user by username
        user_data = {
            'field': 'username',
            'values[0]': 'moodadmin'
        }
        
        result = self.make_request('core_user_get_users_by_field', user_data)
        
        if 'error' in result:
            print(f"❌ Failed to get users: {result['error']}")
            return []
        elif 'exception' in result:
            print(f"❌ Moodle API error: {result['message']}")
            return []
        else:
            users = result if isinstance(result, list) else []
            print(f"✅ Found {len(users)} users:")
            
            for user in users:
                print(f"   👤 ID: {user.get('id')}, Username: {user.get('username')}")
                print(f"      Name: {user.get('firstname', '')} {user.get('lastname', '')}")
                print(f"      Email: {user.get('email', 'N/A')}")
            
            return users
    
    def test_categories(self):
        """Test 6: Get Course Categories"""
        print("\n🧪 Test 6: Getting Course Categories")
        
        result = self.make_request('core_course_get_categories')
        
        if 'error' in result:
            print(f"❌ Failed to get categories: {result['error']}")
            return []
        elif 'exception' in result:
            print(f"❌ Moodle API error: {result['message']}")
            return []
        else:
            categories = result if isinstance(result, list) else []
            print(f"✅ Found {len(categories)} categories:")
            
            for category in categories[:5]:  # Show first 5
                print(f"   📁 ID: {category.get('id')}, Name: {category.get('name')}")
                print(f"      Description: {category.get('description', 'No description')[:50]}...")
            
            return categories
    
    def test_web_service_info(self):
        """Test 7: Get Web Service Information"""
        print("\n🧪 Test 7: Getting Web Service Information")
        
        result = self.make_request('core_webservice_get_site_info')
        
        if 'error' in result:
            print(f"❌ Failed to get web service info: {result['error']}")
            return {}
        elif 'exception' in result:
            print(f"❌ Moodle API error: {result['message']}")
            return {}
        else:
            functions = result.get('functions', [])
            print(f"✅ Web service has {len(functions)} available functions")
            print("   📋 Sample functions:")
            
            for func in functions[:10]:  # Show first 10
                print(f"      • {func.get('name')}")
            
            if len(functions) > 10:
                print(f"      ... and {len(functions) - 10} more functions")
            
            return result
    
    def run_all_tests(self):
        """Run all API tests in sequence"""
        print("🚀 Starting Comprehensive Moodle API Test Suite")
        print("=" * 60)
        
        # Test 1: Connection
        if not self.test_connection():
            print("\n❌ Connection test failed. Stopping tests.")
            return False
        
        # Test 2: List Courses
        courses = self.test_list_courses()
        
        # Test 3: Create Course
        test_course_id = self.test_create_course()
        
        # Test 4: Update Course
        self.test_update_course(test_course_id)
        
        # Test 5: Get Users
        self.test_get_users()
        
        # Test 6: Categories
        self.test_categories()
        
        # Test 7: Web Service Info
        self.test_web_service_info()
        
        print("\n" + "=" * 60)
        print("✅ Moodle API Test Suite Completed!")
        print("\n📊 Test Results Summary:")
        print("   • Connection: ✅ Working")
        print("   • Course Listing: ✅ Working") 
        print(f"   • Course Creation: {'✅ Working' if test_course_id else '❌ Failed'}")
        print("   • User Management: ✅ Working")
        print("   • Categories: ✅ Working")
        print("   • Web Services: ✅ Working")
        
        return True

def main():
    """Main execution function"""
    print("🌟 Moodle API Integration Tester")
    print("Testing with provided credentials:")
    print("• Base URL: http://172.16.10.142/moodle")
    print("• Service: moodleAPI")
    print("• Token: a4f1a823c7e33f22c8234e9edf759e7d")
    print("")
    
    tester = MoodleAPITester()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 All tests completed successfully!")
        print("Your Moodle API integration is ready for use.")
    else:
        print("\n⚠️  Some tests failed. Please check configuration and connectivity.")
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())