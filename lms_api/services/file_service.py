import os
import uuid
import mimetypes
from typing import Tuple, Optional, Dict, Any
import logging
from werkzeug.utils import secure_filename

log = logging.getLogger(__name__)

class FileService:
    
    # Maximum file size: 100MB
    MAX_FILE_SIZE = 100 * 1024 * 1024
    
    # Allowed file types
    ALLOWED_EXTENSIONS = {
        # Documents
        'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
        # Images
        'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg',
        # Text files
        'txt', 'rtf', 'csv', 'md', 'json', 'xml', 'html', 'css', 'js',
        # Archives
        'zip', 'rar', '7z',
        # Audio/Video (for reference materials)
        'mp3', 'wav', 'mp4', 'avi', 'mov', 'webm',
        # Code files
        'py', 'java', 'cpp', 'c', 'h', 'cs', 'php', 'rb', 'go', 'rs'
    }
    
    ALLOWED_MIME_TYPES = {
        # Documents
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        
        # Images
        'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 
        'image/bmp', 'image/webp', 'image/svg+xml',
        
        # Text files
        'text/plain', 'text/rtf', 'text/csv', 'text/markdown', 
        'text/html', 'text/css', 'text/javascript',
        'application/json', 'application/xml', 'text/xml',
        
        # Code files
        'text/x-python', 'text/x-java-source', 'text/x-c', 'text/x-csrc',
        'text/x-chdr', 'text/x-csharp', 'application/x-php',
        
        # Archives
        'application/zip', 'application/x-rar-compressed',
        'application/x-zip-compressed', 'application/x-7z-compressed',
        'application/octet-stream',
        
        # Audio/Video
        'audio/mpeg', 'audio/wav', 'audio/mp3',
        'video/mp4', 'video/avi', 'video/quicktime', 'video/webm'
    }
    
    def __init__(self, upload_dir: str = None):
        self.upload_dir = upload_dir or os.path.abspath(os.path.join(os.getcwd(), 'uploads'))
        self.ensure_upload_dir()
    
    def ensure_upload_dir(self):
        """Ensure upload directory exists"""
        if not os.path.exists(self.upload_dir):
            os.makedirs(self.upload_dir, exist_ok=True)
            log.info(f"Created upload directory: {self.upload_dir}")
    
    def validate_file(self, filename: str, file_size: int, mime_type: str = None) -> Tuple[bool, str]:
        """
        Validate uploaded file
        
        Args:
            filename: Original filename
            file_size: File size in bytes
            mime_type: MIME type of the file
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check file size
        if file_size > self.MAX_FILE_SIZE:
            return False, f"File size exceeds maximum limit of {self.MAX_FILE_SIZE / (1024*1024):.0f}MB"
        
        if file_size <= 0:
            return False, "File is empty"
        
        # Check filename
        if not filename or filename.strip() == '':
            return False, "Filename is required"
        
        # Get file extension
        file_ext = os.path.splitext(filename)[1][1:].lower()
        
        # Check extension
        if file_ext not in self.ALLOWED_EXTENSIONS:
            return False, f"File type '{file_ext}' is not allowed. Allowed types: {', '.join(self.ALLOWED_EXTENSIONS)}"
        
        # Check MIME type if provided
        if mime_type and mime_type not in self.ALLOWED_MIME_TYPES:
            # Sometimes browsers send different MIME types, so we'll log a warning but allow it
            log.warning(f"Unexpected MIME type '{mime_type}' for file '{filename}'. Allowed based on extension.")
        
        return True, ""
    
    def generate_unique_filename(self, original_filename: str) -> str:
        """Generate a unique filename to prevent conflicts"""
        # Secure the filename
        secure_name = secure_filename(original_filename)
        
        # Get file extension
        name, ext = os.path.splitext(secure_name)
        
        # Generate unique ID
        unique_id = str(uuid.uuid4())[:8]
        
        # Create new filename: name_uniqueID.ext
        return f"{name}_{unique_id}{ext}"
    
    def save_file(self, file_data: bytes, filename: str, course_id: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Save file to disk
        
        Args:
            file_data: File content as bytes
            filename: Original filename
            course_id: Course ID for organization
            
        Returns:
            Tuple of (success, error_message_or_path, file_info)
        """
        try:
            # Create course-specific directory
            course_dir = os.path.join(self.upload_dir, course_id)
            if not os.path.exists(course_dir):
                os.makedirs(course_dir, exist_ok=True)
                log.info(f"Created course directory: {course_dir}")
            
            # Generate unique filename
            unique_filename = self.generate_unique_filename(filename)
            
            # Full file path (ensure absolute path)
            file_path = os.path.abspath(os.path.join(course_dir, unique_filename))
            
            # Save file
            with open(file_path, 'wb') as f:
                f.write(file_data)
            
            # Verify file was written successfully
            if not os.path.exists(file_path) or os.path.getsize(file_path) != len(file_data):
                raise Exception("File verification failed after write")
            
            # Get file info
            file_size = len(file_data)
            mime_type, _ = mimetypes.guess_type(filename)
            
            file_info = {
                'file_path': file_path,
                'file_name': filename,
                'unique_filename': unique_filename,
                'file_size': file_size,
                'mime_type': mime_type or 'application/octet-stream'
            }
            
            log.info(f"File saved successfully: {file_path} ({file_size} bytes)")
            return True, file_path, file_info
            
        except Exception as e:
            log.error(f"Error saving file: {str(e)}")
            return False, f"Failed to save file: {str(e)}", None
    
    def delete_file(self, file_path: str) -> bool:
        """Delete file from disk"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                log.info(f"File deleted: {file_path}")
                return True
            else:
                log.warning(f"File not found for deletion: {file_path}")
                return False
        except Exception as e:
            log.error(f"Error deleting file: {str(e)}")
            return False
    
    def get_file_content(self, file_path: str) -> Optional[bytes]:
        """Get file content as bytes"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    return f.read()
            return None
        except Exception as e:
            log.error(f"Error reading file: {str(e)}")
            return None
    
    def validate_url(self, url: str) -> Tuple[bool, str]:
        """Validate URL format"""
        if not url or url.strip() == '':
            return False, "URL is required"
        
        # Basic URL validation
        if not (url.startswith('http://') or url.startswith('https://')):
            return False, "URL must start with http:// or https://"
        
        # Check for malicious patterns
        malicious_patterns = ['javascript:', 'data:', 'vbscript:', 'file:', 'ftp:']
        url_lower = url.lower()
        for pattern in malicious_patterns:
            if pattern in url_lower:
                return False, f"URL contains forbidden protocol: {pattern}"
        
        return True, ""
    
    def validate_text_content(self, content: str) -> Tuple[bool, str]:
        """Validate text content"""
        if not content or content.strip() == '':
            return False, "Text content is required"
        
        # Check content length (max 50KB for text content)
        if len(content.encode('utf-8')) > 50 * 1024:
            return False, "Text content is too large (max 50KB)"
        
        return True, ""