# Missing CRUD operations for Moodle backend

@view_config(route_name='moodle_course_contents', request_method='GET', renderer='json')
def get_moodle_course_contents(request):
    """
    GET /api/moodle/courses/{course_id}/contents
    
    Get course contents/modules
    """
    course_id = request.matchdict['course_id']
    
    try:
        course_id_int = int(course_id)
    except ValueError:
        raise HTTPBadRequest('Invalid course ID')
    
    try:
        moodle = get_moodle_service()
        contents = moodle.get_course_contents(course_id_int)
        
        return normalize_moodle_response(contents)
        
    except Exception as e:
        handle_moodle_error(e)


@view_config(route_name='moodle_content_delete', request_method='DELETE', renderer='json')
def delete_moodle_content(request):
    """
    DELETE /api/moodle/content/{module_id}
    
    Delete specific course content/module
    """
    module_id = request.matchdict['module_id']
    
    try:
        module_id_int = int(module_id)
    except ValueError:
        raise HTTPBadRequest('Invalid module ID')
    
    try:
        moodle = get_moodle_service()
        result = moodle.delete_course_module(module_id_int)
        
        log.info(f"Course module deleted from Moodle: {module_id}")
        return normalize_moodle_response({'message': 'Content deleted successfully'})
        
    except Exception as e:
        handle_moodle_error(e)


@view_config(route_name='moodle_add_url', request_method='POST', renderer='json')
def add_url_to_moodle_course(request):
    """
    POST /api/moodle/courses/{course_id}/url
    
    Add URL resource to Moodle course
    """
    course_id = request.matchdict['course_id']
    
    try:
        course_id_int = int(course_id)
    except ValueError:
        raise HTTPBadRequest('Invalid course ID')
    
    try:
        data = request.json_body
    except ValueError:
        raise HTTPBadRequest('Invalid JSON')
    
    required_fields = ['name', 'externalurl']
    for field in required_fields:
        if field not in data:
            raise HTTPBadRequest(f'{field} is required')
    
    try:
        moodle = get_moodle_service()
        result = moodle.add_url_to_course(
            courseid=course_id_int,
            section=data.get('section', 0),
            name=data['name'],
            externalurl=data['externalurl'],
            intro=data.get('intro', '')
        )
        
        log.info(f"URL resource added to Moodle course {course_id}")
        return normalize_moodle_response(result)
        
    except Exception as e:
        handle_moodle_error(e)


@view_config(route_name='moodle_add_page', request_method='POST', renderer='json')
def add_page_to_moodle_course(request):
    """
    POST /api/moodle/courses/{course_id}/page
    
    Add page resource to Moodle course
    """
    course_id = request.matchdict['course_id']
    
    try:
        course_id_int = int(course_id)
    except ValueError:
        raise HTTPBadRequest('Invalid course ID')
    
    try:
        data = request.json_body
    except ValueError:
        raise HTTPBadRequest('Invalid JSON')
    
    required_fields = ['name', 'content']
    for field in required_fields:
        if field not in data:
            raise HTTPBadRequest(f'{field} is required')
    
    try:
        moodle = get_moodle_service()
        result = moodle.add_page_to_course(
            courseid=course_id_int,
            section=data.get('section', 0),
            name=data['name'],
            content=data['content'],
            intro=data.get('intro', '')
        )
        
        log.info(f"Page resource added to Moodle course {course_id}")
        return normalize_moodle_response(result)
        
    except Exception as e:
        handle_moodle_error(e)


@view_config(route_name='moodle_file_upload_course', request_method='POST', renderer='json')
def upload_file_to_course(request):
    """
    POST /api/moodle/courses/{course_id}/upload
    
    Upload file directly to a course
    """
    course_id = request.matchdict['course_id']
    
    try:
        course_id_int = int(course_id)
    except ValueError:
        raise HTTPBadRequest('Invalid course ID')
    
    # Check if file was uploaded
    if 'file' not in request.POST:
        raise HTTPBadRequest('No file uploaded')
    
    file_obj = request.POST['file']
    if not hasattr(file_obj, 'filename') or not file_obj.filename:
        raise HTTPBadRequest('Invalid file')
    
    # Validate file size (100MB limit)
    file_obj.file.seek(0, 2)  # Seek to end
    file_size = file_obj.file.tell()
    file_obj.file.seek(0)  # Reset to beginning
    
    MAX_SIZE = 100 * 1024 * 1024  # 100MB
    if file_size > MAX_SIZE:
        raise HTTPBadRequest(f'File too large. Maximum size is 100MB, got {file_size / 1024 / 1024:.1f}MB')
    
    try:
        # Read file data
        file_data = file_obj.file.read()
        
        moodle = get_moodle_service()
        
        # First upload to draft area
        upload_result = moodle.upload_file(
            file_data=file_data,
            filename=file_obj.filename,
            contextid=1,
            component='user',
            filearea='draft'
        )
        
        # Then attach to course
        if 'draftitemid' in upload_result:
            attach_result = moodle.attach_file_to_course_resource(
                courseid=course_id_int,
                draftitemid=upload_result['draftitemid'],
                name=request.POST.get('name', file_obj.filename),
                intro=request.POST.get('intro', '')
            )
            
            log.info(f"File uploaded and attached to Moodle course {course_id}")
            return normalize_moodle_response({
                'upload': upload_result,
                'attach': attach_result,
                'message': 'File uploaded successfully'
            })
        else:
            return normalize_moodle_response(upload_result)
        
    except Exception as e:
        handle_moodle_error(e)