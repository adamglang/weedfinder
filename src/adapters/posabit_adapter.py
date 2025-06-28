import requests
import json
import os
import logging
from typing import List, Dict, Optional
from ..models.enums import ProductFamily, StrainType
from ..services import StoreService, ProductService, StrainService
from ..database.config import get_session

logger = logging.getLogger(__name__)

# Mapping of POSaBIT category strings to ProductFamily enums
POSABIT_CATEGORY_MAPPING = {
    'flower': ProductFamily.FLOWER,
    'edible_liquid': ProductFamily.EDIBLE_LIQUID,
    'edible_solid': ProductFamily.EDIBLE_SOLID,
    'preroll': ProductFamily.PREROLL,
    'topical': ProductFamily.TOPICAL,
    'concentrate': ProductFamily.CONCENTRATE,
    'cartridge': ProductFamily.CARTRIDGE,
    'cbd': ProductFamily.CBD,
    'apparel': ProductFamily.APPAREL,
    'paraphernalia': ProductFamily.PARAPHERNALIA,
    'sample': ProductFamily.SAMPLE,
    'seed': ProductFamily.SEED,
    'clone': ProductFamily.CLONE,
    'other': ProductFamily.OTHER
}

# Keywords for fuzzy matching POSaBIT categories
CATEGORY_KEYWORDS = {
    ProductFamily.FLOWER: ['flower', 'bud'],
    ProductFamily.EDIBLE_LIQUID: ['edible liquid', 'liquid', 'drink', 'beverage'],
    ProductFamily.EDIBLE_SOLID: ['edible solid', 'edible', 'gummy'],
    ProductFamily.CARTRIDGE: ['vape', 'cartridge', 'cart'],
    ProductFamily.PREROLL: ['pre-roll', 'preroll', 'joint'],
    ProductFamily.TOPICAL: ['topical'],
    ProductFamily.CONCENTRATE: ['concentrate', 'extract', 'wax', 'shatter'],
    ProductFamily.CBD: ['cbd'],
    ProductFamily.SEED: ['seed'],
    ProductFamily.CLONE: ['clone'],
    ProductFamily.SAMPLE: ['sample'],
    ProductFamily.APPAREL: ['apparel', 'clothing'],
    ProductFamily.PARAPHERNALIA: ['paraphernalia', 'accessory', 'accessories']
}

def map_posabit_category(category_str: str) -> ProductFamily:
    """Convert POSaBIT category string to ProductFamily enum"""
    if not category_str:
        return ProductFamily.OTHER
        
    category_lower = category_str.lower().strip()
    
    # Direct mapping first
    if category_lower in POSABIT_CATEGORY_MAPPING:
        return POSABIT_CATEGORY_MAPPING[category_lower]
    
    # Fuzzy matching using keywords
    for product_family, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in category_lower for keyword in keywords):
            return product_family
    
    return ProductFamily.OTHER

class POSaBITAdapter:
    """Adapter for POSaBIT POS system"""
    
    # Mapping from ProductFamily to form factors for backward compatibility
    _CATEGORY_TO_FORM_FACTOR = {
        ProductFamily.FLOWER: 'flower',
        ProductFamily.CARTRIDGE: 'vape',
        ProductFamily.EDIBLE_LIQUID: 'edible',
        ProductFamily.EDIBLE_SOLID: 'edible',
        ProductFamily.PREROLL: 'pre_roll',
        ProductFamily.TOPICAL: 'topical',
        ProductFamily.CONCENTRATE: 'concentrate',
    }
    
    # Strain type keywords mapping
    _STRAIN_TYPE_KEYWORDS = {
        StrainType.INDICA: ['indica'],
        StrainType.SATIVA: ['sativa'],
        StrainType.HYBRID: ['hybrid'],
        StrainType.CBD_DOMINANT: ['cbd', 'hemp', 'charlotte']
    }
    
    def __init__(self):
        self.base_url = "https://app.posabit.com"
        self.feed_id = os.getenv("POSABIT_FEED_ID")
        self.merchant_token = os.getenv("POSABIT_MERCHANT_TOKEN")
        self.api_token = os.getenv("POSABIT_API_TOKEN")
        
        # Initialize services
        self.store_service = StoreService()
        self.product_service = ProductService()
        self.strain_service = StrainService()
    
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
            raw_category = raw_product.get('category', '')
            product_family = map_posabit_category(raw_category)
            
            product = {
                'sku': raw_product.get('id', ''),
                'name': raw_product.get('name', ''),
                'brand': raw_product.get('brand', ''),
                'category': raw_category,  # Keep original category string
                'product_family': product_family,  # Normalized ProductFamily enum
                'strain': raw_product.get('strain', ''),
                'thc_pct': self._safe_float(raw_product.get('potency_thc')),
                'cbd_pct': self._safe_float(raw_product.get('potency_cbd')),
                'description': raw_product.get('description', ''),
                'json_raw': raw_product
            }
            
            # Map ProductFamily to form_factor for backward compatibility
            product['form_factor'] = self._CATEGORY_TO_FORM_FACTOR.get(product_family, 'other')
            
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
    
    def _determine_strain_type(self, strain_name: str, category: str) -> StrainType:
        """Determine strain type from name and category"""
        text_to_check = f"{strain_name} {category}".lower()
        
        # Check strain type keywords - simple heuristics, can be improved with ML later
        for strain_type, keywords in self._STRAIN_TYPE_KEYWORDS.items():
            if any(keyword in text_to_check for keyword in keywords):
                return strain_type
        
        return StrainType.HYBRID  # default assumption
    
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
        with get_session() as session:
            try:
                # Get store info using service
                store = self.store_service.get_by_slug(session, store_slug)
                if not store:
                    raise ValueError(f"Store not found: {store_slug}")
                
                store_id = store.id
                
                # Fetch and normalize products
                products = await self.fetch_products(store_slug)
                
                # Store products in database
                stored_products = []
                for product in products:
                    try:
                        # Handle strain classification
                        strain_name = product.get('strain', '').strip()
                        strain_id = None
                        if strain_name:
                            strain_type = self._determine_strain_type(strain_name, product.get('category', ''))
                            # Upsert strain using service
                            strain = self.strain_service.upsert_strain(
                                session,
                                canonical_name=strain_name,
                                strain_type=strain_type
                            )
                            strain_id = strain.id
                        
                        # Prepare product data for ORM
                        product_data = {
                            'store_id': store_id,
                            'sku': product.get('sku'),
                            'name': product.get('name'),
                            'brand': product.get('brand'),
                            'product_family': product.get('product_family'),
                            'strain_id': strain_id,
                            'thc_pct': product.get('thc_pct'),
                            'cbd_pct': product.get('cbd_pct'),
                            'price': product.get('price'),
                            'quantity': product.get('quantity', 0),
                            'json_raw': product.get('json_raw')
                        }
                        
                        # Store product using service
                        stored_product = self.product_service.upsert_product(session, store_id, product_data)
                        product['id'] = stored_product.id
                        stored_products.append(product)
                        
                    except Exception as e:
                        logger.error(f"Error storing product {product.get('sku', 'unknown')}: {e}")
                        continue
                
                # Commit all changes
                session.commit()
                logger.info(f"Stored {len(stored_products)} products for store {store_slug}")
                return stored_products
                
            except Exception as e:
                session.rollback()
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
            print(f"📋 Product family: {sample['product_family'].value}")
        
        return True
    except Exception as e:
        print(f"❌ POSaBIT connection failed: {e}")
        return False

if __name__ == "__main__":
    # Test the adapter
    test_posabit_connection()