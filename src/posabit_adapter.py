import requests
import json
import os
import logging
from typing import List, Dict, Optional
from datetime import datetime
from .database import get_store_by_slug, upsert_product, upsert_strain

logger = logging.getLogger(__name__)

class POSaBITAdapter:
    """Adapter for POSaBIT POS system"""
    
    def __init__(self):
        self.base_url = "https://app.posabit.com"
        self.feed_id = os.getenv("POSABIT_FEED_ID")
        self.merchant_token = os.getenv("POSABIT_MERCHANT_TOKEN")
        self.api_token = os.getenv("POSABIT_API_TOKEN")
    
    def fetch_raw_feed(self, store_slug: str = "pend-oreille-cannabis-co") -> Dict:
        """Fetch raw product data from POSaBIT API"""
        url = f"{self.base_url}/mcx/{store_slug}/venue/newport/v1/menu_feeds/{self.feed_id}/product_data"
        
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "merchantToken": self.merchant_token,
            "Accept": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Fetched {len(data.get('product_data', {}).get('menu_items', []))} products from POSaBIT")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch POSaBIT feed: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse POSaBIT response: {e}")
            raise
    
    def normalize_product(self, raw_product: Dict) -> Dict:
        """Convert POSaBIT product format to canonical format"""
        try:
            # Extract basic product info
            product = {
                'sku': raw_product.get('id', ''),
                'name': raw_product.get('name', ''),
                'brand': raw_product.get('brand', ''),
                'category': raw_product.get('category', ''),
                'strain': raw_product.get('strain', ''),
                'thc_pct': self._safe_float(raw_product.get('potency_thc')),
                'cbd_pct': self._safe_float(raw_product.get('potency_cbd')),
                'description': raw_product.get('description', ''),
                'json_raw': raw_product
            }
            
            # Map category to form_factor
            category = product['category'].lower()
            if 'flower' in category or 'bud' in category:
                product['form_factor'] = 'flower'
            elif 'vape' in category or 'cartridge' in category:
                product['form_factor'] = 'vape'
            elif 'edible' in category or 'gummy' in category:
                product['form_factor'] = 'edible'
            elif 'pre-roll' in category or 'joint' in category:
                product['form_factor'] = 'pre_roll'
            elif 'tincture' in category:
                product['form_factor'] = 'tincture'
            elif 'topical' in category:
                product['form_factor'] = 'topical'
            else:
                product['form_factor'] = 'other'
            
            # Extract price from variants (take first/cheapest)
            variants = raw_product.get('variants', [])
            if variants:
                first_variant = variants[0]
                # Convert price_cents to dollars
                price_cents = first_variant.get('price_cents')
                product['price'] = price_cents / 100.0 if price_cents else None
                product['quantity'] = first_variant.get('quantity_on_hand', 0)
                # Get supplier as brand if available
                if not product['brand'] and first_variant.get('supplier'):
                    product['brand'] = first_variant.get('supplier')
            else:
                product['price'] = None
                product['quantity'] = 0
            
            return product
            
        except Exception as e:
            logger.error(f"Error normalizing product {raw_product.get('id', 'unknown')}: {e}")
            return None
    
    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float"""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _determine_strain_type(self, strain_name: str, category: str) -> str:
        """Determine strain type from name and category"""
        strain_lower = strain_name.lower()
        category_lower = category.lower()
        
        # Simple heuristics - can be improved with ML later
        if 'indica' in strain_lower or 'indica' in category_lower:
            return 'indica'
        elif 'sativa' in strain_lower or 'sativa' in category_lower:
            return 'sativa'
        elif 'hybrid' in strain_lower or 'hybrid' in category_lower:
            return 'hybrid'
        elif 'cbd' in strain_lower or any(word in strain_lower for word in ['hemp', 'charlotte']):
            return 'cbd_dominant'
        else:
            return 'hybrid'  # default assumption
    
    async def fetch_products(self, store_slug: str) -> List[Dict]:
        """Fetch and return normalized products for a store"""
        try:
            raw_data = self.fetch_raw_feed(store_slug)
            menu_items = raw_data.get('product_data', {}).get('menu_items', [])
            
            products = []
            for raw_product in menu_items:
                normalized = self.normalize_product(raw_product)
                if normalized:
                    products.append(normalized)
            
            logger.info(f"Normalized {len(products)} products for store {store_slug}")
            return products
            
        except Exception as e:
            logger.error(f"Error fetching products for {store_slug}: {e}")
            return []
    
    async def fetch_and_store_products(self, store_slug: str) -> List[Dict]:
        """Fetch products and store them in database"""
        try:
            # Get store info
            store = get_store_by_slug(store_slug)
            if not store:
                raise ValueError(f"Store not found: {store_slug}")
            
            store_id = store['id']
            
            # Fetch and normalize products
            products = await self.fetch_products(store_slug)
            
            # Store products in database
            stored_products = []
            for product in products:
                try:
                    # Handle strain classification
                    strain_name = product.get('strain', '').strip()
                    if strain_name:
                        strain_type = self._determine_strain_type(strain_name, product.get('category', ''))
                        strain_id = upsert_strain(strain_name, strain_type)
                        product['strain_id'] = strain_id
                    
                    # Store product
                    product_id = upsert_product(store_id, product)
                    product['id'] = product_id
                    stored_products.append(product)
                    
                except Exception as e:
                    logger.error(f"Error storing product {product.get('sku', 'unknown')}: {e}")
                    continue
            
            logger.info(f"Stored {len(stored_products)} products for store {store_slug}")
            return stored_products
            
        except Exception as e:
            logger.error(f"Error in fetch_and_store_products for {store_slug}: {e}")
            raise

def test_posabit_connection():
    """Test POSaBIT API connection"""
    adapter = POSaBITAdapter()
    try:
        data = adapter.fetch_raw_feed()
        print(f"✅ POSaBIT connection successful!")
        print(f"📦 Found {len(data.get('product_data', {}).get('menu_items', []))} products")
        
        # Show sample product
        menu_items = data.get('product_data', {}).get('menu_items', [])
        if menu_items:
            sample = adapter.normalize_product(menu_items[0])
            print(f"📋 Sample product: {sample['name']} - {sample['thc_pct']}% THC - ${sample['price']}")
        
        return True
    except Exception as e:
        print(f"❌ POSaBIT connection failed: {e}")
        return False

if __name__ == "__main__":
    # Test the adapter
    test_posabit_connection()