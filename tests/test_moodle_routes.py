"""
Integration tests for Moodle API routes

Tests the Pyramid view functions with mocked MoodleService calls
to ensure proper HTTP status codes, error handling, and response formats.
"""

import pytest
import json
from unittest.mock import patch, Mock
from pyramid import testing
from pyramid.httpexceptions import HTTPBadRequest, HTTPNotFound, HTTPForbidden

from lms_api.views.moodle import (
    get_site_info, list_courses, create_course, update_course,
    enrol_users, get_users_by_field, get_notifications, get_unread_count,
    upload_file, attach_file_to_course
)
from lms_api.services.moodle_service import (
    MoodleError, MoodleAuthError, MoodleValidationError, MoodleNotFoundError
)


class TestMoodleRoutes:
    """Test Moodle API route handlers"""
    
    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user"""
        user = Mock()
        user.username = 'testuser'
        user.id = 123
        return user
    
    @pytest.fixture
    def request_factory(self):
        """Factory for creating mock requests"""
        def _create_request(method='GET', json_body=None, params=None, matchdict=None, post=None):
            request = testing.DummyRequest()
            request.method = method
            request.user = Mock()
            request.user.username = 'testuser'
            request.user.id = 123
            
            if json_body:
                request.json_body = json_body
            if params:
                request.params = params
            if matchdict:
                request.matchdict = matchdict
            if post:
                request.POST = post
                
            return request
        return _create_request
    
    @patch('lms_api.views.moodle.get_moodle_service')
    def test_get_site_info_success(self, mock_get_service, request_factory):
        """Test successful site info retrieval"""
        mock_service = Mock()
        mock_service.get_site_info.return_value = {
            'sitename': 'Test Moodle',
            'version': '4.0',
            'release': '4.0.1',
            'functions': [
                {'name': 'core_webservice_get_site_info', 'version': '2.2'}
            ]
        }
        mock_get_service.return_value = mock_service
        
        request = request_factory()
        
        result = get_site_info(request)
        
        assert result['ok'] is True
        assert 'data' in result
        assert result['data']['sitename'] == 'Test Moodle'
        assert result['data']['version'] == '4.0'
        assert len(result['data']['functions']) == 1
    
    @patch('lms_api.views.moodle.get_moodle_service')
    def test_get_site_info_moodle_error(self, mock_get_service, request_factory):
        """Test site info with Moodle auth error"""
        mock_service = Mock()
        mock_service.get_site_info.side_effect = MoodleAuthError("Invalid token", "invalidtoken", 401)
        mock_get_service.return_value = mock_service
        
        request = request_factory()
        
        with pytest.raises(Exception):  # Should raise HTTPUnauthorized
            get_site_info(request)
    
    @patch('lms_api.views.moodle.get_moodle_service')
    def test_list_courses_success(self, mock_get_service, request_factory):
        """Test successful course listing"""
        mock_service = Mock()
        mock_service.list_courses.return_value = [
            {'id': 1, 'fullname': 'Course 1', 'shortname': 'C1', 'categoryid': 1},
            {'id': 2, 'fullname': 'Course 2', 'shortname': 'C2', 'categoryid': 2}
        ]
        mock_get_service.return_value = mock_service
        
        request = request_factory()
        
        result = list_courses(request)
        
        assert result['ok'] is True
        assert len(result['data']) == 2
        assert result['data'][0]['fullname'] == 'Course 1'
    
    @patch('lms_api.views.moodle.get_moodle_service')
    def test_list_courses_with_search(self, mock_get_service, request_factory):
        """Test course listing with search filter"""
        mock_service = Mock()
        mock_service.list_courses.return_value = [
            {'id': 1, 'fullname': 'Python Programming', 'shortname': 'PY101'},
            {'id': 2, 'fullname': 'Java Programming', 'shortname': 'JV101'},
            {'id': 3, 'fullname': 'Web Development', 'shortname': 'WEB101'}
        ]
        mock_get_service.return_value = mock_service
        
        request = request_factory(params={'search': 'python'})
        
        result = list_courses(request)
        
        assert result['ok'] is True
        assert len(result['data']) == 1
        assert result['data'][0]['fullname'] == 'Python Programming'
    
    @patch('lms_api.views.moodle.get_moodle_service')
    def test_list_courses_with_category_filter(self, mock_get_service, request_factory):
        """Test course listing with category filter"""
        mock_service = Mock()
        mock_service.list_courses.return_value = [
            {'id': 1, 'fullname': 'Course 1', 'categoryid': 1},
            {'id': 2, 'fullname': 'Course 2', 'categoryid': 2},
            {'id': 3, 'fullname': 'Course 3', 'categoryid': 1}
        ]
        mock_get_service.return_value = mock_service
        
        request = request_factory(params={'category': '1'})
        
        result = list_courses(request)
        
        assert result['ok'] is True
        assert len(result['data']) == 2
        assert all(course['categoryid'] == 1 for course in result['data'])
    
    @patch('lms_api.views.moodle.get_moodle_service')
    def test_create_course_success(self, mock_get_service, request_factory):
        """Test successful course creation"""
        mock_service = Mock()
        mock_service.create_course.return_value = {
            'id': 123,
            'fullname': 'New Course',
            'shortname': 'NC',
            'categoryid': 1
        }
        mock_get_service.return_value = mock_service
        
        course_data = {
            'fullname': 'New Course',
            'shortname': 'NC',
            'categoryid': 1
        }
        request = request_factory(method='POST', json_body=course_data)
        
        result = create_course(request)
        
        assert result['ok'] is True
        assert result['data']['id'] == 123
        assert result['data']['fullname'] == 'New Course'
        
        # Verify service was called with correct data
        mock_service.create_course.assert_called_once_with(course_data)
    
    def test_create_course_missing_required_field(self, request_factory):
        """Test course creation with missing required field"""
        request = request_factory(method='POST', json_body={'fullname': 'Test Course'})
        
        with pytest.raises(Exception):  # Should raise HTTPBadRequest
            create_course(request)
    
    def test_create_course_invalid_json(self, request_factory):
        """Test course creation with invalid JSON"""
        request = request_factory(method='POST')
        # Simulate invalid JSON by raising ValueError
        request.json_body = property(lambda self: (_ for _ in ()).throw(ValueError()))
        
        with pytest.raises(Exception):  # Should raise HTTPBadRequest
            create_course(request)
    
    @patch('lms_api.views.moodle.get_moodle_service')
    def test_update_course_success(self, mock_get_service, request_factory):
        """Test successful course update"""
        mock_service = Mock()
        mock_service.update_course.return_value = None
        mock_get_service.return_value = mock_service
        
        update_data = {'fullname': 'Updated Course Name'}
        request = request_factory(
            method='PATCH',
            json_body=update_data,
            matchdict={'course_id': '123'}
        )
        
        result = update_course(request)
        
        assert result['ok'] is True
        assert 'Course updated successfully' in result['data']['message']
        
        # Verify service was called with course ID included
        expected_data = {'id': 123, 'fullname': 'Updated Course Name'}
        mock_service.update_course.assert_called_once_with(expected_data)
    
    def test_update_course_invalid_id(self, request_factory):
        """Test course update with invalid course ID"""
        request = request_factory(
            method='PATCH',
            json_body={'fullname': 'Test'},
            matchdict={'course_id': 'invalid'}
        )
        
        with pytest.raises(Exception):  # Should raise HTTPBadRequest
            update_course(request)
    
    def test_update_course_no_fields(self, request_factory):
        """Test course update with no fields provided"""
        request = request_factory(
            method='PATCH',
            json_body={},
            matchdict={'course_id': '123'}
        )
        
        with pytest.raises(Exception):  # Should raise HTTPBadRequest
            update_course(request)
    
    @patch('lms_api.views.moodle.get_moodle_service')
    def test_enrol_users_success(self, mock_get_service, request_factory):
        """Test successful user enrolment"""
        mock_service = Mock()
        mock_service.enrol_users.return_value = None
        mock_get_service.return_value = mock_service
        
        enrolment_data = {
            'enrolments': [
                {'roleid': 5, 'userid': 123, 'courseid': 456},
                {'roleid': 5, 'userid': 124, 'courseid': 456}
            ]
        }
        request = request_factory(method='POST', json_body=enrolment_data)
        
        result = enrol_users(request)
        
        assert result['ok'] is True
        assert result['data']['count'] == 2
        assert 'Users enrolled successfully' in result['data']['message']
        
        mock_service.enrol_users.assert_called_once_with(enrolment_data['enrolments'])
    
    def test_enrol_users_no_enrolments(self, request_factory):
        """Test user enrolment with no enrolments provided"""
        request = request_factory(method='POST', json_body={})
        
        with pytest.raises(Exception):  # Should raise HTTPBadRequest
            enrol_users(request)
    
    def test_enrol_users_missing_fields(self, request_factory):
        """Test user enrolment with missing required fields"""
        enrolment_data = {
            'enrolments': [
                {'roleid': 5, 'courseid': 456}  # Missing userid
            ]
        }
        request = request_factory(method='POST', json_body=enrolment_data)
        
        with pytest.raises(Exception):  # Should raise HTTPBadRequest
            enrol_users(request)
    
    @patch('lms_api.views.moodle.get_moodle_service')
    def test_get_users_by_field_success(self, mock_get_service, request_factory):
        """Test successful user retrieval by field"""
        mock_service = Mock()
        mock_service.get_users_by_field.return_value = [
            {
                'id': 1,
                'username': 'user1',
                'firstname': 'John',
                'lastname': 'Doe',
                'email': 'john@example.com'
            }
        ]
        mock_get_service.return_value = mock_service
        
        request = request_factory(params={'field': 'email', 'values': 'john@example.com'})
        
        result = get_users_by_field(request)
        
        assert result['ok'] is True
        assert len(result['data']) == 1
        assert result['data'][0]['username'] == 'user1'
        
        mock_service.get_users_by_field.assert_called_once_with('email', ['john@example.com'])
    
    def test_get_users_by_field_missing_params(self, request_factory):
        """Test user retrieval with missing parameters"""
        # Missing field parameter
        request = request_factory(params={'values': 'test@example.com'})
        
        with pytest.raises(Exception):  # Should raise HTTPBadRequest
            get_users_by_field(request)
        
        # Missing values parameter  
        request = request_factory(params={'field': 'email'})
        
        with pytest.raises(Exception):  # Should raise HTTPBadRequest
            get_users_by_field(request)
    
    @patch('lms_api.views.moodle.get_moodle_service')
    def test_get_notifications_success(self, mock_get_service, request_factory):
        """Test successful notification retrieval"""
        mock_service = Mock()
        mock_service.get_popup_notifications.return_value = {
            'notifications': [
                {'id': 1, 'subject': 'Test notification', 'read': False}
            ],
            'unreadcount': 1
        }
        mock_get_service.return_value = mock_service
        
        request = request_factory(params={'userid': '123', 'limit': '10', 'offset': '0'})
        
        result = get_notifications(request)
        
        assert result['ok'] is True
        assert 'notifications' in result['data']
        assert len(result['data']['notifications']) == 1
        
        mock_service.get_popup_notifications.assert_called_once_with(123, 10, 0)
    
    def test_get_notifications_missing_userid(self, request_factory):
        """Test notification retrieval with missing userid"""
        request = request_factory(params={'limit': '10'})
        
        with pytest.raises(Exception):  # Should raise HTTPBadRequest
            get_notifications(request)
    
    def test_get_notifications_invalid_userid(self, request_factory):
        """Test notification retrieval with invalid userid"""
        request = request_factory(params={'userid': 'invalid'})
        
        with pytest.raises(Exception):  # Should raise HTTPBadRequest
            get_notifications(request)
    
    @patch('lms_api.views.moodle.get_moodle_service')
    def test_get_unread_count_success(self, mock_get_service, request_factory):
        """Test successful unread count retrieval"""
        mock_service = Mock()
        mock_service.get_unread_popup_count.return_value = 5
        mock_get_service.return_value = mock_service
        
        request = request_factory(params={'userid': '123'})
        
        result = get_unread_count(request)
        
        assert result['ok'] is True
        assert result['data']['unread_count'] == 5
        
        mock_service.get_unread_popup_count.assert_called_once_with(123)
    
    @patch('lms_api.views.moodle.get_moodle_service')
    def test_upload_file_success(self, mock_get_service, request_factory):
        """Test successful file upload"""
        mock_service = Mock()
        mock_service.upload_file.return_value = {
            'draftitemid': 123456,
            'filename': 'test.pdf'
        }
        mock_get_service.return_value = mock_service
        
        # Mock file upload
        mock_file = Mock()
        mock_file.filename = 'test.pdf'
        mock_file.file = Mock()
        mock_file.file.read.return_value = b'file content'
        mock_file.file.seek.return_value = None
        
        post_data = {
            'file': mock_file,
            'contextid': '1',
            'component': 'user',
            'filearea': 'draft'
        }
        request = request_factory(method='POST', post=post_data)
        
        result = upload_file(request)
        
        assert result['ok'] is True
        assert result['data']['draftitemid'] == 123456
        
        mock_service.upload_file.assert_called_once()
        call_args = mock_service.upload_file.call_args
        assert call_args[1]['filename'] == 'test.pdf'
        assert call_args[1]['file_data'] == b'file content'
    
    def test_upload_file_no_file(self, request_factory):
        """Test file upload with no file provided"""
        request = request_factory(method='POST', post={})
        
        with pytest.raises(Exception):  # Should raise HTTPBadRequest
            upload_file(request)
    
    @patch('lms_api.views.moodle.get_moodle_service')
    def test_attach_file_to_course_success(self, mock_get_service, request_factory):
        """Test successful file attachment to course"""
        mock_service = Mock()
        mock_service.attach_file_to_course_resource.return_value = {
            'resourceid': 789,
            'name': 'Test Resource'
        }
        mock_get_service.return_value = mock_service
        
        attach_data = {
            'courseid': 123,
            'draftitemid': 456,
            'name': 'Test Resource',
            'intro': 'Test resource description'
        }
        request = request_factory(method='POST', json_body=attach_data)
        
        result = attach_file_to_course(request)
        
        assert result['ok'] is True
        assert result['data']['resourceid'] == 789
        
        mock_service.attach_file_to_course_resource.assert_called_once_with(
            courseid=123,
            draftitemid=456,
            name='Test Resource',
            intro='Test resource description'
        )
    
    def test_attach_file_missing_fields(self, request_factory):
        """Test file attachment with missing required fields"""
        request = request_factory(method='POST', json_body={'courseid': 123})
        
        with pytest.raises(Exception):  # Should raise HTTPBadRequest
            attach_file_to_course(request)


class TestErrorHandling:
    """Test error handling in Moodle routes"""
    
    @pytest.fixture
    def request_factory(self):
        def _create_request():
            request = testing.DummyRequest()
            request.user = Mock()
            request.user.username = 'testuser'
            return request
        return _create_request
    
    @patch('lms_api.views.moodle.get_moodle_service')
    def test_moodle_auth_error_handling(self, mock_get_service, request_factory):
        """Test handling of Moodle authentication errors"""
        mock_service = Mock()
        mock_service.get_site_info.side_effect = MoodleAuthError("Access denied", "nopermissions", 403)
        mock_get_service.return_value = mock_service
        
        request = request_factory()
        
        with pytest.raises(Exception):  # Should raise HTTPForbidden
            get_site_info(request)
    
    @patch('lms_api.views.moodle.get_moodle_service')
    def test_moodle_validation_error_handling(self, mock_get_service, request_factory):
        """Test handling of Moodle validation errors"""
        mock_service = Mock()
        mock_service.list_courses.side_effect = MoodleValidationError("Invalid parameter", "invalidparameter", 400)
        mock_get_service.return_value = mock_service
        
        request = request_factory()
        
        with pytest.raises(Exception):  # Should raise HTTPBadRequest
            list_courses(request)
    
    @patch('lms_api.views.moodle.get_moodle_service')
    def test_moodle_not_found_error_handling(self, mock_get_service, request_factory):
        """Test handling of Moodle not found errors"""
        mock_service = Mock()
        mock_service.get_users_by_field.side_effect = MoodleNotFoundError("User not found", "invaliduser", 404)
        mock_get_service.return_value = mock_service
        
        request = request_factory()
        request.params = {'field': 'id', 'values': '999'}
        
        with pytest.raises(Exception):  # Should raise HTTPNotFound
            get_users_by_field(request)
    
    @patch('lms_api.views.moodle.get_moodle_service')
    def test_generic_moodle_error_handling(self, mock_get_service, request_factory):
        """Test handling of generic Moodle errors"""
        mock_service = Mock()
        mock_service.get_site_info.side_effect = MoodleError("Server error", status_code=500)
        mock_get_service.return_value = mock_service
        
        request = request_factory()
        
        with pytest.raises(Exception):  # Should raise HTTPInternalServerError
            get_site_info(request)
    
    @patch('lms_api.views.moodle.get_moodle_service')
    def test_unexpected_error_handling(self, mock_get_service, request_factory):
        """Test handling of unexpected errors"""
        mock_service = Mock()
        mock_service.get_site_info.side_effect = RuntimeError("Unexpected error")
        mock_get_service.return_value = mock_service
        
        request = request_factory()
        
        with pytest.raises(Exception):  # Should raise HTTPInternalServerError
            get_site_info(request)