from sqlalchemy import create_engine, MetaData, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from contextlib import contextmanager
import os
import logging

log = logging.getLogger(__name__)

DBSession = scoped_session(sessionmaker())
Base = declarative_base()

def initialize_sql(engine):
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    Base.metadata.create_all(engine)
    
    # Add event listeners for connection monitoring
    @event.listens_for(engine, "connect")
    def receive_connect(dbapi_connection, connection_record):
        log.debug("Database connection established")

    @event.listens_for(engine, "close")
    def receive_close(dbapi_connection, connection_record):
        log.debug("Database connection closed")

@contextmanager
def database_transaction():
    """Context manager for database transactions with automatic rollback on error"""
    session = DBSession()
    transaction = session.begin()
    
    try:
        yield session
        transaction.commit()
        log.debug("Database transaction committed successfully")
    except Exception as e:
        transaction.rollback()
        log.error(f"Database transaction rolled back due to error: {str(e)}")
        raise
    finally:
        session.close()

# Event listeners will be added to the engine in initialize_sql function