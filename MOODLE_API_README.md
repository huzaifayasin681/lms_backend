# Moodle REST API Integration

Complete Moodle REST API wrapper for the LMS backend, providing secure, typed access to Moodle web services with proper error handling, retry logic, and parameter encoding.

## Features

- 🔒 **Secure**: Token never exposed to clients or logged
- 🚀 **Reliable**: Automatic retry logic with exponential backoff
- 📝 **Typed**: TypeScript-style parameter validation and helpers
- 🎯 **Clean**: Standard HTTP status codes and JSON responses
- 📊 **Observable**: Structured logging with request tracking
- 🧪 **Tested**: Comprehensive unit and integration tests

## Quick Start

### 1. Environment Setup

Copy the environment configuration:

```bash
cp .env.example .env
```

Configure your Moodle settings in `.env`:

```bash
# Moodle API Configuration
MOODLE_BASE_URL=https://your-moodle-instance.com
MOODLE_TOKEN=your_moodle_webservice_token_here
MOODLE_TIMEOUT_MS=15000
MOODLE_DEBUG=false
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the Server

```bash
pserve development.ini
```

The Moodle API endpoints will be available at `/api/moodle/*`

## API Endpoints

All endpoints require authentication via `Authorization: Bearer <jwt_token>` header.

### Site Information

**GET /api/moodle/siteinfo**

Get Moodle site information including version and available functions.

```bash
curl -X GET "http://localhost:6543/api/moodle/siteinfo" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response:**
```json
{
  "ok": true,
  "data": {
    "sitename": "My Moodle Site",
    "release": "4.0.1+",
    "version": "2022041901",
    "functions": [
      {"name": "core_webservice_get_site_info", "version": "2.2"}
    ]
  }
}
```

### Courses

**GET /api/moodle/courses**

List all courses visible to the user with optional filtering.

Query Parameters:
- `search`: Search term for course names
- `category`: Filter by category ID

```bash
# List all courses
curl -X GET "http://localhost:6543/api/moodle/courses" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Search courses
curl -X GET "http://localhost:6543/api/moodle/courses?search=python" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Filter by category
curl -X GET "http://localhost:6543/api/moodle/courses?category=1" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**POST /api/moodle/courses**

Create a new course in Moodle.

```bash
curl -X POST "http://localhost:6543/api/moodle/courses" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "fullname": "Introduction to Python",
    "shortname": "PY101",
    "categoryid": 1,
    "summary": "Learn Python programming from scratch",
    "format": "topics",
    "visible": 1
  }'
```

**PATCH /api/moodle/courses/{course_id}**

Update subset of course fields.

```bash
curl -X PATCH "http://localhost:6543/api/moodle/courses/123" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "fullname": "Advanced Python Programming",
    "summary": "Updated course description",
    "visible": 1
  }'
```

### User Management

**GET /api/moodle/users/by-field**

Get users by field value(s).

Query Parameters:
- `field`: Field to search by (username, email, id, etc.)
- `values`: Comma-separated list of values

```bash
# Get users by email
curl -X GET "http://localhost:6543/api/moodle/users/by-field?field=email&values=user1@example.com,user2@example.com" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Get users by username
curl -X GET "http://localhost:6543/api/moodle/users/by-field?field=username&values=student1,student2" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Enrollment

**POST /api/moodle/enrol**

Manually enroll users in courses.

```bash
curl -X POST "http://localhost:6543/api/moodle/enrol" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enrolments": [
      {
        "roleid": 5,
        "userid": 123,
        "courseid": 456
      },
      {
        "roleid": 5,
        "userid": 124,
        "courseid": 456
      }
    ]
  }'
```

**Common Role IDs:**
- `5`: Student
- `4`: Teacher (non-editing)
- `3`: Teacher (editing)
- `1`: Manager

### Notifications

**GET /api/moodle/notifications**

Get popup notifications for a user.

Query Parameters:
- `userid`: User ID (required)
- `limit`: Maximum notifications (default 20, max 100)
- `offset`: Pagination offset (default 0)

```bash
curl -X GET "http://localhost:6543/api/moodle/notifications?userid=123&limit=10&offset=0" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**GET /api/moodle/notifications/unread-count**

Get count of unread notifications for a user.

Query Parameters:
- `userid`: User ID (required)

```bash
curl -X GET "http://localhost:6543/api/moodle/notifications/unread-count?userid=123" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### File Upload & Attachment

**POST /api/moodle/files/upload**

Upload a file to Moodle's draft area.

```bash
curl -X POST "http://localhost:6543/api/moodle/files/upload" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@/path/to/your/file.pdf" \
  -F "contextid=1" \
  -F "component=user" \
  -F "filearea=draft"
```

**POST /api/moodle/files/attach**

Attach uploaded file to course as resource.

```bash
curl -X POST "http://localhost:6543/api/moodle/files/attach" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "courseid": 123,
    "draftitemid": 456789,
    "name": "Course Materials PDF",
    "intro": "Essential reading materials for the course"
  }'
```

## Response Format

All endpoints return responses in a consistent format:

**Success Response:**
```json
{
  "ok": true,
  "data": { ... }
}
```

**Error Response:**
```json
{
  "ok": false,
  "error": {
    "code": "invalidparameter",
    "message": "Validation error: Missing required field",
    "details": null
  }
}
```

## HTTP Status Codes

- `200 OK`: Successful operation
- `400 Bad Request`: Validation errors, missing parameters
- `401 Unauthorized`: Invalid or missing authentication token
- `403 Forbidden`: Insufficient permissions in Moodle
- `404 Not Found`: Resource not found (user, course, etc.)
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server or Moodle errors
- `502 Bad Gateway`: Invalid response from Moodle
- `503 Service Unavailable`: Moodle server connection issues
- `504 Gateway Timeout`: Request timeout

## Route to Function Mapping

| Route | Moodle Function | Required Capabilities |
|-------|----------------|----------------------|
| `GET /api/moodle/siteinfo` | `core_webservice_get_site_info` | `webservice/rest:use` |
| `GET /api/moodle/courses` | `core_course_get_courses` | `moodle/course:view` |
| `POST /api/moodle/courses` | `core_course_create_courses` | `moodle/course:create` |
| `PATCH /api/moodle/courses/{id}` | `core_course_update_courses` | `moodle/course:update` |
| `POST /api/moodle/enrol` | `enrol_manual_enrol_users` | `enrol/manual:enrol` |
| `GET /api/moodle/users/by-field` | `core_user_get_users_by_field` | `moodle/user:viewdetails` |
| `GET /api/moodle/notifications` | `message_popup_get_popup_notifications`<br/>or `core_message_get_popup_notifications` | `moodle/site:readallmessages` |
| `GET /api/moodle/notifications/unread-count` | `core_message_get_unread_popup_notifications_count` | `moodle/site:readallmessages` |
| `POST /api/moodle/files/upload` | File upload endpoint | `moodle/course:managefiles` |
| `POST /api/moodle/files/attach` | `mod_resource_add_resource` | `mod/resource:addinstance` |

## Error Handling

The integration automatically normalizes Moodle errors to appropriate HTTP status codes:

### Authentication Errors (401/403)
- `invalidtoken` → 401 Unauthorized
- `accessexception`, `nopermissions`, `notloggedin` → 403 Forbidden

### Validation Errors (400)
- `invalidparameter`, `missingparam`, `invalidrecord` → 400 Bad Request

### Not Found Errors (404)
- `invaliduser`, `invalidcourse`, `coursenotexist` → 404 Not Found

### Server Errors (5xx)
- Connection timeouts → 504 Gateway Timeout
- Connection failures → 503 Service Unavailable
- Other errors → 500 Internal Server Error

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `MOODLE_BASE_URL` | Moodle instance URL | - | Yes |
| `MOODLE_TOKEN` | Web service token | - | Yes |
| `MOODLE_TIMEOUT_MS` | Request timeout (ms) | 15000 | No |
| `MOODLE_DEBUG` | Enable debug logging | false | No |

### Timeouts and Retries

- **Default timeout**: 15 seconds
- **Retry logic**: Idempotent operations (GET-like) retry up to 2 times
- **Backoff strategy**: Exponential backoff (0.1s, 0.2s, 0.4s)
- **Non-idempotent operations**: No retries (create, update, delete)

### Debug Mode

Set `MOODLE_DEBUG=true` to enable detailed logging:

```bash
MOODLE_DEBUG=true
```

Debug logs include:
- Request/response schemas (not bodies for security)
- Request duration and status
- Retry attempts
- Parameter encoding details

## Troubleshooting

### Common Issues

#### 1. Invalid Token Error (401)

**Symptoms:**
```json
{
  "ok": false,
  "error": {
    "code": "invalidtoken",
    "message": "Invalid Moodle token"
  }
}
```

**Solutions:**
- Verify `MOODLE_TOKEN` environment variable
- Check token hasn't expired in Moodle
- Ensure web services are enabled for the token user
- Verify token has required capabilities

#### 2. Access Denied (403)

**Symptoms:**
```json
{
  "ok": false,
  "error": {
    "code": "nopermissions",
    "message": "Access denied: Insufficient permissions"
  }
}
```

**Solutions:**
- Check user role and capabilities in Moodle
- Ensure web service user has required permissions
- Verify course enrollment status for course-specific operations

#### 3. Function Not Found

**Symptoms:**
```json
{
  "ok": false,
  "error": {
    "code": "unknown",
    "message": "Function not found"
  }
}
```

**Solutions:**
- Enable the required web service function in Moodle admin
- Check Moodle version compatibility
- Verify external service configuration includes the function

#### 4. Parameter Encoding Issues

**Symptoms:**
- Unexpected validation errors
- Parameters not recognized by Moodle

**Solutions:**
- Verify parameter names match Moodle API documentation
- Check array parameter encoding (uses bracket notation)
- Ensure required parameters are included

#### 5. Connection Timeouts (504)

**Symptoms:**
```json
{
  "ok": false,
  "error": {
    "code": "unknown",
    "message": "Request timeout after 15s"
  }
}
```

**Solutions:**
- Increase `MOODLE_TIMEOUT_MS` value
- Check Moodle server performance
- Verify network connectivity
- Consider reducing request payload size

#### 6. File Upload Issues

**Symptoms:**
- Upload fails silently
- Files not appearing in Moodle

**Solutions:**
- Check file size limits in Moodle and server
- Verify upload directory permissions
- Ensure proper context and component parameters
- Check Moodle file handling configuration

### Getting Help

1. **Enable debug logging**: Set `MOODLE_DEBUG=true`
2. **Check Moodle logs**: Review Moodle's web service logs
3. **Test with Moodle's API tester**: Use `/admin/webservice/documentation.php`
4. **Verify capabilities**: Check user permissions in Moodle admin
5. **Network debugging**: Use `curl` to test direct Moodle API calls

### Development & Testing

#### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_moodle_service.py

# Run with coverage
pytest --cov=lms_api.services.moodle_service tests/test_moodle_service.py
```

#### Manual Testing with curl

Test the Moodle service directly:

```bash
# Test authentication
curl -X POST "https://your-moodle.com/webservice/rest/server.php" \
  -d "wstoken=YOUR_TOKEN" \
  -d "wsfunction=core_webservice_get_site_info" \
  -d "moodlewsrestformat=json"
```

#### Integration Testing

The integration uses mocked HTTP calls for testing. For full integration testing:

1. Set up a test Moodle instance
2. Configure test environment variables
3. Run integration tests against real Moodle API

## Security Considerations

- **Token Security**: Never log or expose the Moodle token
- **Input Validation**: All parameters are validated before sending to Moodle
- **Error Sanitization**: Error messages are sanitized to prevent information disclosure
- **HTTPS Only**: Always use HTTPS for production Moodle instances
- **Capability Checks**: Rely on Moodle's capability system for authorization
- **Audit Logging**: All operations are logged with user context

## Performance Optimization

- **Connection Pooling**: Reuse HTTP connections where possible
- **Caching**: Consider caching site info and course lists
- **Batch Operations**: Use bulk operations when available
- **Async Processing**: Consider async patterns for bulk operations
- **Rate Limiting**: Implement client-side rate limiting if needed

## Future Enhancements

- **Bulk Operations**: Add support for bulk user creation/updates
- **Event Streaming**: Real-time notifications via WebSocket
- **Caching Layer**: Redis/Memcached for frequently accessed data
- **Async Operations**: Background task processing for large operations
- **GraphQL**: GraphQL wrapper for more flexible queries
- **Webhooks**: Moodle event webhook integration