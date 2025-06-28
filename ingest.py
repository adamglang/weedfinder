#!/usr/bin/env python3
"""
Manual ingestion script for POSaBIT data
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.adapters import POSaBITAdapter
from src.ml import StrainClassifier
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    """Run the ingestion process"""
    try:
        logger.info("Starting WeedFinder.ai ingestion process...")
        
        # Initialize services
        adapter = POSaBITAdapter()
        classifier = StrainClassifier()
        
        # Test POSaBIT connection first
        logger.info("Testing POSaBIT connection...")
        try:
            raw_data = adapter.fetch_raw_feed()
            menu_items = raw_data.get('product_data', {}).get('menu_items', [])
            logger.info(f"✅ Successfully connected to POSaBIT - found {len(menu_items)} products")
        except Exception as e:
            logger.error(f"❌ POSaBIT connection failed: {e}")
            logger.error("Please check your POSaBIT credentials in .env file")
            return
        
        # Fetch and store products
        logger.info("Fetching and storing products...")
        store_slug = "pend-oreille-cannabis-co"
        
        try:
            products = await adapter.fetch_and_store_products(store_slug)
            logger.info(f"✅ Successfully stored {len(products)} products")
            
            # Extract unique strains for classification
            unique_strains = set()
            for product in products:
                strain = product.get('strain', '').strip()
                if strain and len(strain) > 2:  # Filter out empty or very short strain names
                    unique_strains.add(strain)
            
            logger.info(f"Found {len(unique_strains)} unique strains to classify")
            
            # Classify strains
            if unique_strains:
                logger.info("Classifying strains with AI...")
                strain_results = classifier.batch_classify_strains(list(unique_strains))
                
                successful_classifications = len([r for r in strain_results.values() if r])
                logger.info(f"✅ Successfully classified {successful_classifications} out of {len(unique_strains)} strains")
                
                # Show some examples
                logger.info("\nSample strain classifications:")
                for strain_name, strain_id in list(strain_results.items())[:3]:
                    if strain_id:
                        strain_info = classifier.get_strain_effects(strain_id)
                        logger.info(f"  {strain_name}: {strain_info.get('strain_type', 'unknown')} - {', '.join(strain_info.get('effects', [])[:3])}")
            
            logger.info("\n🎉 Ingestion completed successfully!")
            logger.info(f"📊 Summary:")
            logger.info(f"   - Products stored: {len(products)}")
            logger.info(f"   - Strains classified: {len([r for r in strain_results.values() if r]) if unique_strains else 0}")
            logger.info(f"   - Store: {store_slug}")
            
            logger.info("\nNext steps:")
            logger.info("1. Start the API: python app.py")
            logger.info("2. Test search: curl -X POST http://localhost:8000/search -H 'Content-Type: application/json' -d '{\"query\": \"something for relaxation\", \"store_id\": \"pend-oreille-cannabis-co\"}'")
            
        except Exception as e:
            logger.error(f"❌ Error during product ingestion: {e}")
            raise
            
    except Exception as e:
        logger.error(f"❌ Ingestion failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())