"""Add content visibility settings

Revision ID: add_content_visibility
Revises: 9ad4721bff26
Create Date: 2024-08-14 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_content_visibility'
down_revision = '9ad4721bff26'
branch_labels = None
depends_on = None


def upgrade():
    # Add visibility column to course_content table
    op.add_column('course_content', sa.Column('visibility', sa.String(20), nullable=False, server_default='private'))
    op.add_column('course_content', sa.Column('access_level', sa.String(50), nullable=False, server_default='course_members'))
    
    # Add visibility column to courses table
    op.add_column('courses', sa.Column('visibility', sa.String(20), nullable=False, server_default='private'))
    op.add_column('courses', sa.Column('access_level', sa.String(50), nullable=False, server_default='enrolled'))


def downgrade():
    # Remove visibility columns
    op.drop_column('course_content', 'visibility')
    op.drop_column('course_content', 'access_level')
    op.drop_column('courses', 'visibility')
    op.drop_column('courses', 'access_level')