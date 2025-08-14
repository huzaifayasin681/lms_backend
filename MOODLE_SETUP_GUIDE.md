# Moodle API Setup Guide

## Your Moodle Configuration

**WebService Name:** `moodleAPI`  
**Access Token:** `a4f1a823c7e33f22c8234e9edf759e7d`

## Quick Setup Steps

### 1. Configure Environment Variables

Create or update your `.env` file with your Moodle credentials:

```bash
# Copy example file if it doesn't exist
cp .env.example .env
```

Update your `.env` file with these values:

```bash
# Moodle API Configuration
MOODLE_BASE_URL=https://your-moodle-instance.com
MOODLE_TOKEN=a4f1a823c7e33f22c8234e9edf759e7d
MOODLE_TIMEOUT_MS=15000
MOODLE_DEBUG=true

# Legacy - keeping for compatibility  
MOODLE_URL=https://your-moodle-instance.com
```

**⚠️ Replace `https://your-moodle-instance.com` with your actual Moodle URL**

### 2. Test the Connection

Start your LMS backend:

```bash
cd backend
pserve development.ini
```

Test the Moodle connection (you'll need a valid JWT token):

```bash
# Get a JWT token first by logging in
curl -X POST "http://localhost:6543/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "your_username", "password": "your_password"}'

# Test Moodle site info (replace JWT_TOKEN with actual token)
curl -X GET "http://localhost:6543/api/moodle/siteinfo" \
  -H "Authorization: Bearer JWT_TOKEN"
```

### 3. Moodle Admin Configuration

Ensure these settings are configured in your Moodle admin panel:

#### Enable Web Services
1. Go to **Site Administration → Advanced Features**
2. Enable **Web services** checkbox
3. Save changes

#### Configure the Web Service
1. Go to **Site Administration → Server → Web services → External services**
2. Find your `moodleAPI` service
3. Ensure these functions are enabled:
   - `core_webservice_get_site_info`
   - `core_course_get_courses`
   - `core_course_create_courses`
   - `core_course_update_courses`
   - `core_user_get_users_by_field`
   - `enrol_manual_enrol_users`
   - `message_popup_get_popup_notifications`
   - `core_message_get_unread_popup_notifications_count`

#### Token User Capabilities
Ensure the user associated with your token has these capabilities:
- `webservice/rest:use`
- `moodle/course:view`
- `moodle/course:create` (for course creation)
- `moodle/course:update` (for course updates)
- `moodle/user:viewdetails`
- `enrol/manual:enrol` (for user enrollment)
- `moodle/site:readallmessages` (for notifications)

### 4. Test Each Endpoint

#### Site Information
```bash
curl -X GET "http://localhost:6543/api/moodle/siteinfo" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

#### List Courses
```bash
curl -X GET "http://localhost:6543/api/moodle/courses" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

#### Create Course
```bash
curl -X POST "http://localhost:6543/api/moodle/courses" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "fullname": "Test Course via API",
    "shortname": "TESTAPI",
    "categoryid": 1,
    "summary": "Course created via REST API"
  }'
```

#### Get Users by Email
```bash
curl -X GET "http://localhost:6543/api/moodle/users/by-field?field=email&values=admin@yoursite.com" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Troubleshooting

### Common Issues

#### 1. "Invalid token" Error
**Error Response:**
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
- Verify your token: `a4f1a823c7e33f22c8234e9edf759e7d`
- Check that the token is enabled in Moodle admin
- Ensure the `moodleAPI` service is enabled
- Verify the token user has `webservice/rest:use` capability

#### 2. "Function not found" Error
**Solutions:**
- Go to **Site Administration → Server → Web services → External services**
- Edit your `moodleAPI` service
- Add the missing function to the service
- Save changes

#### 3. Connection Timeout
**Solutions:**
- Verify your `MOODLE_BASE_URL` is correct
- Test direct access to your Moodle instance
- Check firewall settings
- Increase `MOODLE_TIMEOUT_MS` if needed

#### 4. Permission Denied
**Error Response:**
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
- Check the token user's role and capabilities
- Ensure the user has required permissions for the specific operation
- Verify course enrollment for course-specific operations

### Debug Mode

Enable debug logging to see detailed request/response information:

```bash
# In your .env file
MOODLE_DEBUG=true
```

This will log:
- Request parameters (without sensitive data)
- Response status and timing
- Retry attempts
- Error details

### Direct Moodle API Testing

Test your token directly against Moodle:

```bash
curl -X POST "https://your-moodle-instance.com/webservice/rest/server.php" \
  -d "wstoken=a4f1a823c7e33f22c8234e9edf759e7d" \
  -d "wsfunction=core_webservice_get_site_info" \
  -d "moodlewsrestformat=json"
```

## Integration with Frontend

Your frontend can now call these endpoints:

```javascript
// Example: Get site info
const response = await fetch('/api/moodle/siteinfo', {
  headers: {
    'Authorization': `Bearer ${jwtToken}`,
    'Content-Type': 'application/json'
  }
});

const data = await response.json();
if (data.ok) {
  console.log('Moodle site:', data.data.sitename);
} else {
  console.error('Error:', data.error.message);
}
```

## Security Notes

🔒 **Important Security Reminders:**

1. **Never expose the Moodle token to your frontend clients**
2. **Always use HTTPS in production**
3. **Regularly rotate your Moodle token**
4. **Monitor API usage and implement rate limiting if needed**
5. **Keep your `.env` file out of version control**

## Next Steps

1. **Set your actual Moodle URL** in the environment variables
2. **Test each endpoint** with the provided curl commands
3. **Configure required Moodle functions** in your web service
4. **Set up proper user capabilities** for your token user
5. **Integrate with your frontend** using the standardized API responses

Your Moodle API integration is now ready for production use! 🚀