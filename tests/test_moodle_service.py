"""
Unit tests for MoodleService

Tests for the Moodle REST API service with mocked HTTP calls
to ensure proper parameter encoding, error handling, and retry logic.
"""

import pytest
import requests
from unittest.mock import patch, Mock
import json
import os

from lms_api.services.moodle_service import (
    MoodleService, MoodleError, MoodleAuthError, 
    MoodleValidationError, MoodleNotFoundError, MoodleParamEncoder
)


class TestMoodleParamEncoder:
    """Test the parameter encoding utility for Moodle's bracket syntax"""
    
    def test_simple_params(self):
        """Test encoding of simple key-value pairs"""
        data = {'username': 'testuser', 'email': 'test@example.com'}
        result = MoodleParamEncoder.encode_params(data)
        
        assert result == {
            'username': 'testuser',
            'email': 'test@example.com'
        }
    
    def test_nested_dict(self):
        """Test encoding of nested dictionaries"""
        data = {
            'user': {
                'firstname': 'John',
                'lastname': 'Doe',
                'email': 'john@example.com'
            }
        }
        result = MoodleParamEncoder.encode_params(data)
        
        assert result == {
            'user[firstname]': 'John',
            'user[lastname]': 'Doe',
            'user[email]': 'john@example.com'
        }
    
    def test_array_params(self):
        """Test encoding of array parameters"""
        data = {
            'courses': [
                {'fullname': 'Course 1', 'shortname': 'C1'},
                {'fullname': 'Course 2', 'shortname': 'C2'}
            ]
        }
        result = MoodleParamEncoder.encode_params(data)
        
        expected = {
            'courses[0][fullname]': 'Course 1',
            'courses[0][shortname]': 'C1',
            'courses[1][fullname]': 'Course 2',
            'courses[1][shortname]': 'C2'
        }
        assert result == expected
    
    def test_array_param_utility(self):
        """Test the array parameter utility method"""
        values = ['email', 'username', 'id']
        result = MoodleParamEncoder.encode_array_param(values, 'fields')
        
        expected = {
            'fields[0]': 'email',
            'fields[1]': 'username',
            'fields[2]': 'id'
        }
        assert result == expected
    
    def test_none_values(self):
        """Test handling of None values"""
        data = {'name': 'Test', 'description': None, 'active': True}
        result = MoodleParamEncoder.encode_params(data)
        
        assert result == {
            'name': 'Test',
            'description': '',  # None becomes empty string
            'active': 'True'
        }


class TestMoodleService:
    """Test the MoodleService class"""
    
    @pytest.fixture
    def mock_env(self):
        """Mock environment variables for testing"""
        with patch.dict(os.environ, {
            'MOODLE_BASE_URL': 'https://moodle.test.com',
            'MOODLE_TOKEN': 'test_token_123',
            'MOODLE_TIMEOUT_MS': '15000',
            'MOODLE_DEBUG': 'false'
        }):
            yield
    
    @pytest.fixture
    def moodle_service(self, mock_env):
        """Create a MoodleService instance for testing"""
        return MoodleService()
    
    def test_initialization(self, mock_env):
        """Test proper initialization of MoodleService"""
        service = MoodleService()
        
        assert service.base_url == 'https://moodle.test.com/webservice/rest/server.php'
        assert service.token == 'test_token_123'
        assert service.timeout == 15000
        assert service.timeout_seconds == 15.0
        assert service.debug_mode is False
    
    def test_initialization_missing_config(self):
        """Test initialization fails with missing configuration"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Moodle base URL is required"):
                MoodleService()
    
    def test_base_url_normalization(self):
        """Test that base URL is properly normalized to include webservice endpoint"""
        service = MoodleService(
            base_url='https://moodle.test.com/',
            token='test_token'
        )
        assert service.base_url == 'https://moodle.test.com/webservice/rest/server.php'
        
        service2 = MoodleService(
            base_url='https://moodle.test.com/webservice/rest/server.php',
            token='test_token'
        )
        assert service2.base_url == 'https://moodle.test.com/webservice/rest/server.php'
    
    @patch('requests.post')
    def test_successful_api_call(self, mock_post, moodle_service):
        """Test successful API call with proper request format"""
        # Mock successful response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {'sitename': 'Test Site', 'version': '4.0'}
        mock_post.return_value = mock_response
        
        result = moodle_service.call('core_webservice_get_site_info')
        
        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Check URL
        assert call_args[0][0] == 'https://moodle.test.com/webservice/rest/server.php'
        
        # Check request data
        expected_data = {
            'wstoken': 'test_token_123',
            'wsfunction': 'core_webservice_get_site_info',
            'moodlewsrestformat': 'json'
        }
        assert call_args[1]['data'] == expected_data
        
        # Check headers
        assert call_args[1]['headers']['Content-Type'] == 'application/x-www-form-urlencoded'
        assert 'User-Agent' in call_args[1]['headers']
        
        # Check timeout
        assert call_args[1]['timeout'] == 15.0
        
        # Check result
        assert result == {'sitename': 'Test Site', 'version': '4.0'}
    
    @patch('requests.post')
    def test_api_call_with_params(self, mock_post, moodle_service):
        """Test API call with complex parameters"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [{'id': 1, 'fullname': 'Test Course'}]
        mock_post.return_value = mock_response
        
        params = {
            'courses': [
                {'fullname': 'New Course', 'shortname': 'NC', 'categoryid': 1}
            ]
        }
        
        result = moodle_service.call('core_course_create_courses', params)
        
        # Check that parameters were properly encoded
        call_data = mock_post.call_args[1]['data']
        assert call_data['courses[0][fullname]'] == 'New Course'
        assert call_data['courses[0][shortname]'] == 'NC'
        assert call_data['courses[0][categoryid]'] == '1'
    
    @patch('requests.post')
    def test_moodle_error_handling(self, mock_post, moodle_service):
        """Test handling of Moodle-specific errors"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'exception': 'invalid_parameter_exception',
            'errorcode': 'invalidparameter',
            'message': 'Invalid parameter value detected'
        }
        mock_post.return_value = mock_response
        
        with pytest.raises(MoodleValidationError) as exc_info:
            moodle_service.call('core_course_create_courses', {})
        
        assert exc_info.value.error_code == 'invalidparameter'
        assert 'Validation error' in str(exc_info.value)
    
    @patch('requests.post')
    def test_auth_error_handling(self, mock_post, moodle_service):
        """Test handling of authentication errors"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'exception': 'webservice_access_exception',
            'errorcode': 'invalidtoken',
            'message': 'Invalid token'
        }
        mock_post.return_value = mock_response
        
        with pytest.raises(MoodleAuthError) as exc_info:
            moodle_service.call('core_webservice_get_site_info')
        
        assert exc_info.value.error_code == 'invalidtoken'
        assert exc_info.value.status_code == 401
    
    @patch('requests.post')
    def test_not_found_error_handling(self, mock_post, moodle_service):
        """Test handling of not found errors"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'exception': 'dml_missing_record_exception',
            'errorcode': 'invaliduser',
            'message': 'User not found'
        }
        mock_post.return_value = mock_response
        
        with pytest.raises(MoodleNotFoundError) as exc_info:
            moodle_service.call('core_user_get_users_by_field', {'field': 'id', 'values': [999]})
        
        assert exc_info.value.error_code == 'invaliduser'
        assert exc_info.value.status_code == 404
    
    @patch('requests.post')
    def test_timeout_handling(self, mock_post, moodle_service):
        """Test handling of request timeouts"""
        mock_post.side_effect = requests.exceptions.Timeout()
        
        with pytest.raises(MoodleError) as exc_info:
            moodle_service.call('core_webservice_get_site_info')
        
        assert 'timeout' in str(exc_info.value).lower()
        assert exc_info.value.status_code == 504
    
    @patch('requests.post')
    def test_connection_error_handling(self, mock_post, moodle_service):
        """Test handling of connection errors"""
        mock_post.side_effect = requests.exceptions.ConnectionError()
        
        with pytest.raises(MoodleError) as exc_info:
            moodle_service.call('core_webservice_get_site_info')
        
        assert 'connection error' in str(exc_info.value).lower()
        assert exc_info.value.status_code == 503
    
    @patch('requests.post')
    def test_retry_logic_for_idempotent_operations(self, mock_post, moodle_service):
        """Test retry logic for idempotent GET-like operations"""
        # First call fails with timeout, second succeeds
        mock_response_success = Mock()
        mock_response_success.raise_for_status.return_value = None
        mock_response_success.json.return_value = {'sitename': 'Test Site'}
        
        mock_post.side_effect = [
            requests.exceptions.Timeout(),
            mock_response_success
        ]
        
        result = moodle_service.call('core_webservice_get_site_info')
        
        # Should have been called twice (original + 1 retry)
        assert mock_post.call_count == 2
        assert result == {'sitename': 'Test Site'}
    
    @patch('requests.post')
    def test_no_retry_for_non_idempotent_operations(self, mock_post, moodle_service):
        """Test that non-idempotent operations are not retried"""
        mock_post.side_effect = requests.exceptions.Timeout()
        
        with pytest.raises(MoodleError):
            moodle_service.call('core_course_create_courses', {})
        
        # Should have been called only once (no retry)
        assert mock_post.call_count == 1
    
    @patch('requests.post')
    def test_invalid_json_response(self, mock_post, moodle_service):
        """Test handling of invalid JSON responses"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = mock_response
        
        with pytest.raises(MoodleError) as exc_info:
            moodle_service.call('core_webservice_get_site_info')
        
        assert 'Invalid JSON response' in str(exc_info.value)
        assert exc_info.value.status_code == 502


class TestMoodleServiceHelpers:
    """Test the helper methods of MoodleService"""
    
    @pytest.fixture
    def mock_env(self):
        with patch.dict(os.environ, {
            'MOODLE_BASE_URL': 'https://moodle.test.com',
            'MOODLE_TOKEN': 'test_token_123'
        }):
            yield
    
    @pytest.fixture
    def moodle_service(self, mock_env):
        return MoodleService()
    
    @patch('lms_api.services.moodle_service.MoodleService.call')
    def test_get_site_info(self, mock_call, moodle_service):
        """Test get_site_info helper method"""
        mock_call.return_value = {'sitename': 'Test Site', 'version': '4.0'}
        
        result = moodle_service.get_site_info()
        
        mock_call.assert_called_once_with('core_webservice_get_site_info')
        assert result == {'sitename': 'Test Site', 'version': '4.0'}
    
    @patch('lms_api.services.moodle_service.MoodleService.call')
    def test_list_courses(self, mock_call, moodle_service):
        """Test list_courses helper method"""
        mock_call.return_value = [
            {'id': 1, 'fullname': 'Course 1'},
            {'id': 2, 'fullname': 'Course 2'}
        ]
        
        result = moodle_service.list_courses()
        
        mock_call.assert_called_once_with('core_course_get_courses')
        assert len(result) == 2
        assert result[0]['fullname'] == 'Course 1'
    
    @patch('lms_api.services.moodle_service.MoodleService.call')
    def test_create_course(self, mock_call, moodle_service):
        """Test create_course helper method"""
        mock_call.return_value = [{'id': 123, 'fullname': 'New Course'}]
        
        course_data = {
            'fullname': 'New Course',
            'shortname': 'NC',
            'categoryid': 1
        }
        
        result = moodle_service.create_course(course_data)
        
        mock_call.assert_called_once_with('core_course_create_courses', {'courses': [course_data]})
        assert result == {'id': 123, 'fullname': 'New Course'}
    
    def test_create_course_validation(self, moodle_service):
        """Test create_course validation of required fields"""
        with pytest.raises(MoodleValidationError, match="Required field missing: fullname"):
            moodle_service.create_course({'shortname': 'TEST'})
        
        with pytest.raises(MoodleValidationError, match="Required field missing: shortname"):
            moodle_service.create_course({'fullname': 'Test Course'})
        
        with pytest.raises(MoodleValidationError, match="Required field missing: categoryid"):
            moodle_service.create_course({'fullname': 'Test Course', 'shortname': 'TEST'})
    
    @patch('lms_api.services.moodle_service.MoodleService.call')
    def test_update_course(self, mock_call, moodle_service):
        """Test update_course helper method"""
        mock_call.return_value = None
        
        update_data = {'id': 123, 'fullname': 'Updated Course'}
        
        moodle_service.update_course(update_data)
        
        mock_call.assert_called_once_with('core_course_update_courses', {'courses': [update_data]})
    
    def test_update_course_validation(self, moodle_service):
        """Test update_course validation"""
        with pytest.raises(MoodleValidationError, match="Course ID is required"):
            moodle_service.update_course({'fullname': 'Test'})
    
    @patch('lms_api.services.moodle_service.MoodleService.call')
    def test_get_users_by_field(self, mock_call, moodle_service):
        """Test get_users_by_field helper method"""
        mock_call.return_value = [
            {'id': 1, 'username': 'user1', 'email': 'user1@test.com'},
            {'id': 2, 'username': 'user2', 'email': 'user2@test.com'}
        ]
        
        result = moodle_service.get_users_by_field('email', ['user1@test.com', 'user2@test.com'])
        
        expected_params = {
            'field': 'email',
            'values': ['user1@test.com', 'user2@test.com']
        }
        mock_call.assert_called_once_with('core_user_get_users_by_field', expected_params)
        assert len(result) == 2
    
    @patch('lms_api.services.moodle_service.MoodleService.call')
    def test_enrol_users(self, mock_call, moodle_service):
        """Test enrol_users helper method"""
        mock_call.return_value = None
        
        enrolments = [
            {'roleid': 5, 'userid': 123, 'courseid': 456}
        ]
        
        moodle_service.enrol_users(enrolments)
        
        mock_call.assert_called_once_with('enrol_manual_enrol_users', {'enrolments': enrolments})
    
    def test_enrol_users_validation(self, moodle_service):
        """Test enrol_users validation"""
        # Test missing required fields
        with pytest.raises(MoodleValidationError, match="Required field missing in enrolment: roleid"):
            moodle_service.enrol_users([{'userid': 123, 'courseid': 456}])
        
        # Test empty enrolments list
        result = moodle_service.enrol_users([])
        assert result is None
    
    @patch('lms_api.services.moodle_service.MoodleService.call')
    def test_get_popup_notifications(self, mock_call, moodle_service):
        """Test get_popup_notifications with fallback logic"""
        mock_call.return_value = {'notifications': [], 'unreadcount': 0}
        
        result = moodle_service.get_popup_notifications(123, limit=10, offset=5)
        
        expected_params = {
            'useridto': 123,
            'limitfrom': 5,
            'limitnum': 10
        }
        mock_call.assert_called_once_with('message_popup_get_popup_notifications', expected_params)
        assert 'notifications' in result
    
    @patch('lms_api.services.moodle_service.MoodleService.call')
    def test_get_popup_notifications_fallback(self, mock_call, moodle_service):
        """Test get_popup_notifications fallback to core_message functions"""
        # First call fails with function not found, second succeeds
        mock_call.side_effect = [
            MoodleError('Function not found'),
            {'notifications': [], 'unreadcount': 0}
        ]
        
        result = moodle_service.get_popup_notifications(123)
        
        # Should have called both functions
        assert mock_call.call_count == 2
        
        # Check fallback was called with correct params
        fallback_call = mock_call.call_args_list[1]
        assert fallback_call[0][0] == 'core_message_get_popup_notifications'
        assert fallback_call[0][1]['userid'] == 123
    
    @patch('lms_api.services.moodle_service.MoodleService.call')
    def test_get_users(self, mock_call, moodle_service):
        """Test get_users helper method"""
        mock_call.return_value = {
            'users': [
                {'id': 1, 'username': 'user1', 'email': 'user1@test.com'},
                {'id': 2, 'username': 'user2', 'email': 'user2@test.com'}
            ]
        }
        
        criteria = [{'key': 'email', 'value': 'user1@test.com'}]
        result = moodle_service.get_users(criteria)
        
        mock_call.assert_called_once_with('core_user_get_users', {'criteria': criteria})
        assert len(result) == 2
        assert result[0]['username'] == 'user1'
    
    @patch('lms_api.services.moodle_service.MoodleService.call')
    def test_upload_file_core(self, mock_call, moodle_service):
        """Test upload_file_core helper method"""
        mock_call.return_value = [{'filename': 'test.txt', 'fileurl': 'http://example.com/file'}]
        
        file_data = b'test file content'
        result = moodle_service.upload_file_core(
            file_data=file_data,
            filename='test.txt',
            contextid=1,
            component='user',
            filearea='draft'
        )
        
        # Verify the call was made with base64 encoded content
        mock_call.assert_called_once()
        call_args = mock_call.call_args[0][1]
        assert call_args['filename'] == 'test.txt'
        assert call_args['contextid'] == 1
        assert call_args['component'] == 'user'
        assert call_args['filearea'] == 'draft'
        assert 'filecontent' in call_args  # Base64 encoded content
        
        assert len(result) == 1
        assert result[0]['filename'] == 'test.txt'