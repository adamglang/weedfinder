"""Database configuration and session management"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

def get_database_url() -> str:
    """Get database URL from environment"""
    return os.getenv("DATABASE_URL", "postgresql://user:password@localhost/weedfinder")

# Database URL from environment
DATABASE_URL = get_database_url()

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=os.getenv("SQL_DEBUG", "false").lower() == "true"
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for database sessions"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database operation failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

# Alias for consistency with service layer
get_session = get_db_session


# Import Base for external use
from ..models.base import Base

def init_database():
    """Initialize database schema"""
    
    try:
        # Import all models to ensure they're registered
        from ..models import (
            Store, Strain, StrainEffect, Product, 
            SearchLog, SalesBaseline, SalesCurrent, StoreMetrics
        )
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise