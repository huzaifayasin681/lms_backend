from setuptools import setup, find_packages

requires = [
    'pyramid',
    'pyramid-jinja2',
    'pyramid-debugtoolbar',
    'SQLAlchemy',
    'alembic',
    'psycopg2-binary',
    'PyJWT',
    'bcrypt',
    'requests',
    'marshmallow',
    'waitress',
    'python-dotenv',
]

tests_require = [
    'pytest',
    'pytest-cov',
    'webtest',
]

setup(
    name='lms_api',
    version='0.0.1',
    description='LMS Course Management API',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=requires,
    extras_require={
        'testing': tests_require,
    },
    entry_points={
        'paste.app_factory': [
            'main = lms_api:main',
        ],
    },
)