"""Database management using Alembic migrations"""

import logging
import subprocess
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from .config import get_session
from ..services import StoreService
from ..models.enums import POSSystem

logger = logging.getLogger(__name__)

def run_migrations():
    """Run Alembic migrations to latest version"""
    try:
        # Get the project root directory (where alembic.ini is located)
        project_root = Path(__file__).parent.parent.parent
        
        # Run alembic upgrade head
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("✅ Database migrations completed successfully")
            return True
        else:
            logger.error(f"❌ Migration failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error running migrations: {e}")
        return False

def reset_database():
    """Reset database by downgrading to base and upgrading to head"""
    try:
        project_root = Path(__file__).parent.parent.parent
        
        # Downgrade to base (removes all tables)
        logger.info("🔄 Downgrading database to base...")
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "base"],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"❌ Downgrade failed: {result.stderr}")
            return False
        
        # Upgrade to head (recreates all tables)
        logger.info("🔄 Upgrading database to head...")
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("✅ Database reset completed successfully")
            return True
        else:
            logger.error(f"❌ Upgrade failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error resetting database: {e}")
        return False

def init_sample_data():
    """Initialize database with sample data for testing"""
    try:
        with get_session() as session:
            store_service = StoreService()
            
            # Check if store already exists
            existing_store = store_service.get_by_slug(session, 'pend-oreille-cannabis-co')
            if not existing_store:
                # Create sample store using the create_store method
                store = store_service.create_store(
                    db=session,
                    name='Pend Oreille Cannabis Co',
                    slug='pend-oreille-cannabis-co',
                    pos_type=POSSystem.POSABIT,
                    pos_config={
                        'feed_id': 'sample_feed_id',
                        'merchant_token': 'sample_merchant_token',
                        'api_token': 'sample_api_token'
                    },
                    geo_lat=48.1781,
                    geo_lon=-117.1047
                )
                logger.info(f"✅ Created sample store: {store.name}")
            else:
                logger.info("ℹ️ Sample store already exists")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Error creating sample data: {e}")
        return False

def get_migration_status():
    """Get current migration status"""
    try:
        project_root = Path(__file__).parent.parent.parent
        
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "current"],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"Error: {result.stderr}"
            
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🚀 WeedFinder Database Management (Alembic)")
    print("=" * 50)
    
    # Show current migration status
    status = get_migration_status()
    print(f"Current migration status: {status}")
    print()
    
    # Run migrations
    if run_migrations():
        print("✅ Database migrations completed")
        
        # Initialize sample data
        if init_sample_data():
            print("✅ Sample data initialized")
        else:
            print("❌ Failed to initialize sample data")
    else:
        print("❌ Failed to run database migrations")
    
    print("=" * 50)
    print("🏁 Database management complete")