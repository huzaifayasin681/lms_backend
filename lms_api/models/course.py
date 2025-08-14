from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.sql import func
from . import Base
import json


class Course(Base):
    __tablename__ = 'courses'
    
    id = Column(Integer, primary_key=True)
    course_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    short_name = Column(String(100), nullable=False)
    description = Column(Text)
    category = Column(String(100))
    lms = Column(String(50), nullable=False)  # 'moodle', 'canvas', or 'local'
    external_id = Column(String(100))  # ID in external LMS
    visibility = Column(String(20), nullable=False, default='private')  # 'public', 'private'
    access_level = Column(String(50), nullable=False, default='enrolled')  # 'everyone', 'enrolled', 'instructors'
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def to_dict(self):
        return {
            'id': self.id,
            'course_id': self.course_id,
            'name': self.name,
            'short_name': self.short_name,
            'description': self.description,
            'category': self.category,
            'lms': self.lms,
            'external_id': self.external_id,
            'visibility': self.visibility,
            'access_level': self.access_level,
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            course_id=data.get('course_id'),
            name=data.get('name'),
            short_name=data.get('short_name'),
            description=data.get('description'),
            category=data.get('category'),
            lms=data.get('lms', 'local'),
            external_id=data.get('external_id'),
            visibility=data.get('visibility', 'private'),
            access_level=data.get('access_level', 'enrolled'),
            active=data.get('active', True)
        )