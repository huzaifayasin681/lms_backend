from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, LargeBinary
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from . import Base
import json
import os


class CourseContent(Base):
    __tablename__ = 'course_content'
    
    id = Column(Integer, primary_key=True)
    course_id = Column(String(100), ForeignKey('courses.course_id'), nullable=False)
    title = Column(String(255), nullable=False)
    content_type = Column(String(50), nullable=False)  # 'file', 'text', 'url'
    content_data = Column(Text)  # JSON data or text content
    file_path = Column(String(500))  # Path to uploaded file
    file_name = Column(String(255))  # Original filename
    file_size = Column(Integer)  # File size in bytes
    mime_type = Column(String(100))  # MIME type of file
    external_id = Column(String(100))  # ID in external LMS
    lms_resource_id = Column(String(100))  # Resource ID in LMS
    uploaded_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    course = relationship("Course", backref="contents")
    user = relationship("User", backref="uploaded_content")
    
    def to_dict(self):
        content_data = {}
        if self.content_data:
            try:
                content_data = json.loads(self.content_data)
            except:
                content_data = {'raw': self.content_data}
        
        return {
            'id': self.id,
            'course_id': self.course_id,
            'title': self.title,
            'content_type': self.content_type,
            'content_data': content_data,
            'file_path': self.file_path,
            'file_name': self.file_name,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'external_id': self.external_id,
            'lms_resource_id': self.lms_resource_id,
            'uploaded_by': self.uploaded_by,
            'upload_date': self.upload_date.isoformat() if self.upload_date else None,
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_dict(cls, data, user_id):
        content_data_str = None
        if data.get('content_data'):
            content_data_str = json.dumps(data['content_data'])
        
        return cls(
            course_id=data.get('course_id'),
            title=data.get('title'),
            content_type=data.get('content_type'),
            content_data=content_data_str,
            file_path=data.get('file_path'),
            file_name=data.get('file_name'),
            file_size=data.get('file_size'),
            mime_type=data.get('mime_type'),
            external_id=data.get('external_id'),
            lms_resource_id=data.get('lms_resource_id'),
            uploaded_by=user_id,
            active=data.get('active', True)
        )
    
    def get_file_url(self, base_url=""):
        """Get the URL to access the file"""
        if self.file_path:
            return f"{base_url}/api/content/{self.id}/file"
        return None
    
    def get_display_size(self):
        """Get human-readable file size"""
        if not self.file_size:
            return "Unknown"
        
        size = self.file_size
        units = ['B', 'KB', 'MB', 'GB']
        unit_index = 0
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        return f"{size:.1f} {units[unit_index]}"
    
    def is_image(self):
        """Check if content is an image"""
        if self.mime_type:
            return self.mime_type.startswith('image/')
        if self.file_name:
            ext = os.path.splitext(self.file_name)[1].lower()
            return ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        return False
    
    def is_document(self):
        """Check if content is a document"""
        if self.mime_type:
            doc_types = [
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/vnd.ms-powerpoint',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation'
            ]
            return self.mime_type in doc_types
        if self.file_name:
            ext = os.path.splitext(self.file_name)[1].lower()
            return ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']
        return False