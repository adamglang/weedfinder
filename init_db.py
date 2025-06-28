#!/usr/bin/env python3
"""
Database initialization script for WeedFinder.ai
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.database.alembic_db import reset_database_with_sample_data
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Initialize the database and create initial data"""
    try:
        logger.info("Initializing WeedFinder.ai database...")
        
        # Initialize database schema
        init_database()
        logger.info("✅ Database schema created successfully")
        
        # Create initial store (Pend Oreille Cannabis Co)
        try:
            store_id = insert_store(
                name="Pend Oreille Cannabis Co",
                slug="pend-oreille-cannabis-co",
                pos_type="posabit",
                pos_config={
                    "feed_id": os.getenv("POSABIT_FEED_ID"),
                    "merchant_token": os.getenv("POSABIT_MERCHANT_TOKEN"),
                    "api_token": os.getenv("POSABIT_API_TOKEN"),
                    "venue": "newport"
                }
            )
            logger.info(f"✅ Created initial store with ID: {store_id}")
        except Exception as e:
            if "duplicate key" in str(e).lower():
                logger.info("ℹ️  Initial store already exists")
            else:
                raise
        
        logger.info("🎉 Database initialization completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Run: python -m src.posabit_adapter  # Test POSaBIT connection")
        logger.info("2. Run: python app.py  # Start the API server")
        logger.info("3. Test: curl http://localhost:8000/ping")
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()