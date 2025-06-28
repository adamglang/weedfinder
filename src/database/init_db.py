"""Database initialization script using SQLAlchemy ORM"""

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import get_database_url, Base
from ..models import *  # Import all models to ensure they're registered

logger = logging.getLogger(__name__)

def create_tables():
    """Create all database tables"""
    try:
        # Get database URL
        database_url = get_database_url()
        
        # Create engine
        engine = create_engine(database_url)
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        logger.info("✅ Database tables created successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating database tables: {e}")
        return False

def drop_tables():
    """Drop all database tables (use with caution!)"""
    try:
        # Get database URL
        database_url = get_database_url()
        
        # Create engine
        engine = create_engine(database_url)
        
        # Drop all tables
        Base.metadata.drop_all(bind=engine)
        
        logger.info("✅ Database tables dropped successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error dropping database tables: {e}")
        return False

def reset_database():
    """Reset database by dropping and recreating all tables"""
    logger.info("🔄 Resetting database...")
    
    if drop_tables():
        if create_tables():
            logger.info("✅ Database reset completed successfully")
            return True
    
    logger.error("❌ Database reset failed")
    return False

def init_sample_data():
    """Initialize database with sample data for testing"""
    from ..services import StoreService
    from ..models.enums import POSSystem
    from .config import get_session
    
    with get_session() as session:
        try:
            store_service = StoreService()
            
            # Create sample store
            sample_store_data = {
                'name': 'Pend Oreille Cannabis Co',
                'slug': 'pend-oreille-cannabis-co',
                'address': '123 Main St, Newport, WA 99156',
                'phone': '(509) 447-3500',
                'email': 'info@pendoreillecannabis.com',
                'pos_system': POSSystem.POSABIT,
                'is_active': True
            }
            
            # Check if store already exists
            existing_store = store_service.get_by_slug(session, 'pend-oreille-cannabis-co')
            if not existing_store:
                store = store_service.create(session, sample_store_data)
                session.commit()
                logger.info(f"✅ Created sample store: {store.name}")
            else:
                logger.info("ℹ️ Sample store already exists")
            
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Error creating sample data: {e}")
            return False

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🚀 WeedFinder Database Initialization")
    print("=" * 40)
    
    # Create tables
    if create_tables():
        print("✅ Database tables created")
        
        # Initialize sample data
        if init_sample_data():
            print("✅ Sample data initialized")
        else:
            print("❌ Failed to initialize sample data")
    else:
        print("❌ Failed to create database tables")
    
    print("=" * 40)
    print("🏁 Database initialization complete")