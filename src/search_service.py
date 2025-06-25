import openai
import json
import redis
import hashlib
import time
import logging
from typing import List, Dict, Optional
import os
from .database import log_search

logger = logging.getLogger(__name__)

class SearchService:
    """AI-powered search service for cannabis products"""
    
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Initialize Redis for caching (optional)
        try:
            self.redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
            self.redis_client.ping()
            self.cache_enabled = True
            logger.info("Redis cache enabled")
        except Exception as e:
            logger.warning(f"Redis not available, caching disabled: {e}")
            self.redis_client = None
            self.cache_enabled = False
    
    def _create_cache_key(self, query: str, products_hash: str) -> str:
        """Create cache key for query + products combination"""
        query_hash = hashlib.md5(query.lower().encode()).hexdigest()
        return f"search:{query_hash}:{products_hash}"
    
    def _get_products_hash(self, products: List[Dict]) -> str:
        """Create hash of products list for cache invalidation"""
        product_ids = sorted([p.get('sku', p.get('id', '')) for p in products])
        return hashlib.md5(str(product_ids).encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict]:
        """Get cached search result"""
        if not self.cache_enabled:
            return None
        
        try:
            cached = self.redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
        
        return None
    
    def _cache_result(self, cache_key: str, result: Dict, ttl: int = 3600):
        """Cache search result"""
        if not self.cache_enabled:
            return
        
        try:
            self.redis_client.setex(cache_key, ttl, json.dumps(result))
        except Exception as e:
            logger.warning(f"Cache write error: {e}")
    
    def _format_products_for_gpt(self, products: List[Dict], limit: int = 200) -> str:
        """Format products for GPT context"""
        product_lines = []
        
        for i, product in enumerate(products[:limit]):
            # Create concise product description
            line_parts = [
                f"{i+1}. {product.get('name', 'Unknown')}",
                f"Brand: {product.get('brand', 'N/A')}",
                f"Type: {product.get('form_factor', 'N/A')}",
            ]
            
            # Add THC/CBD info if available
            thc = product.get('thc_pct')
            cbd = product.get('cbd_pct')
            if thc is not None:
                line_parts.append(f"THC: {thc}%")
            if cbd is not None and cbd > 0:
                line_parts.append(f"CBD: {cbd}%")
            
            # Add price if available
            price = product.get('price')
            if price is not None:
                line_parts.append(f"Price: ${price}")
            
            # Add strain info
            strain = product.get('strain')
            if strain:
                line_parts.append(f"Strain: {strain}")
            
            product_lines.append(" | ".join(line_parts))
        
        return "\n".join(product_lines)
    
    async def search_with_gpt_passthrough(self, query: str, products: List[Dict], limit: int = 3) -> List[Dict]:
        """Simple pass-through search using GPT-3.5 (POC approach)"""
        try:
            # Format products for GPT
            products_context = self._format_products_for_gpt(products)
            
            # Create prompt
            prompt = f"""You are WeedFinder.ai, a cannabis product recommendation assistant.

User Query: {query}

Available Products:
{products_context}

IMPORTANT: You must ONLY recommend products from the list above. Do NOT create or invent product names.

Return the top {limit} most relevant products as JSON with this exact format:
{{"results": [{{"name": "EXACT product name from the list above", "reason": "brief explanation why this matches", "thc": "X%" or "N/A", "cbd": "X%" or "N/A", "price": "$X.XX" or "N/A", "category": "product type", "strain_type": "indica/sativa/hybrid" or "N/A"}}]}}

The "name" field must be copied EXACTLY from the numbered list above. Do not modify, shorten, or create new product names."""

            # Call OpenAI
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo-0125",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=1000
            )
            
            # Parse response
            result = json.loads(response.choices[0].message.content)
            return result.get('results', [])
            
        except Exception as e:
            logger.error(f"GPT search error: {e}")
            # Fallback to simple keyword matching
            return self._fallback_keyword_search(query, products, limit)
    
    def _fallback_keyword_search(self, query: str, products: List[Dict], limit: int = 3) -> List[Dict]:
        """Fallback keyword-based search"""
        query_words = query.lower().split()
        scored_products = []
        
        for product in products:
            score = 0
            searchable_text = " ".join([
                product.get('name', ''),
                product.get('brand', ''),
                product.get('strain', ''),
                product.get('category', ''),
                product.get('form_factor', ''),
                product.get('description', '')
            ]).lower()
            
            # Simple scoring based on word matches
            for word in query_words:
                if word in searchable_text:
                    score += 1
            
            if score > 0:
                scored_products.append({
                    'product': product,
                    'score': score
                })
        
        # Sort by score and return top results
        scored_products.sort(key=lambda x: x['score'], reverse=True)
        
        results = []
        for item in scored_products[:limit]:
            product = item['product']
            results.append({
                'name': product.get('name', 'Unknown'),
                'reason': f"Matched {item['score']} keywords from your search",
                'thc': f"{product.get('thc_pct', 'N/A')}%" if product.get('thc_pct') else "N/A",
                'cbd': f"{product.get('cbd_pct', 'N/A')}%" if product.get('cbd_pct') else "N/A",
                'price': f"${product.get('price', 'N/A')}" if product.get('price') else "N/A",
                'category': product.get('form_factor', 'N/A'),
                'strain_type': product.get('strain_type', 'N/A')
            })
        
        return results
    
    async def search(self, query: str, products: List[Dict], store_id: str = None, limit: int = 3) -> List[Dict]:
        """Main search method with caching"""
        start_time = time.time()
        
        try:
            # Create cache key
            products_hash = self._get_products_hash(products)
            cache_key = self._create_cache_key(query, products_hash)
            
            # Check cache first
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                response_time = int((time.time() - start_time) * 1000)
                
                # Log search
                if store_id:
                    log_search(store_id, query, {}, len(cached_result), response_time, cached=True)
                
                logger.info(f"Cache hit for query: {query[:50]}...")
                return cached_result
            
            # Perform search
            results = await self.search_with_gpt_passthrough(query, products, limit)
            
            # Cache result
            self._cache_result(cache_key, results)
            
            # Calculate response time
            response_time = int((time.time() - start_time) * 1000)
            
            # Log search
            if store_id:
                log_search(store_id, query, {}, len(results), response_time, cached=False)
            
            logger.info(f"Search completed: {query[:50]}... -> {len(results)} results in {response_time}ms")
            return results
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

def test_search_service():
    """Test the search service"""
    service = SearchService()
    
    # Sample products for testing
    sample_products = [
        {
            'sku': 'BD001',
            'name': 'Blue Dream 3.5g',
            'brand': 'Premium Cannabis',
            'form_factor': 'flower',
            'strain': 'Blue Dream',
            'thc_pct': 22.5,
            'cbd_pct': 0.1,
            'price': 35.00,
            'category': 'Flower'
        },
        {
            'sku': 'GG002',
            'name': 'Gorilla Glue #4 Vape Cart',
            'brand': 'Vape Co',
            'form_factor': 'vape',
            'strain': 'Gorilla Glue #4',
            'thc_pct': 85.0,
            'cbd_pct': 0.5,
            'price': 45.00,
            'category': 'Vape'
        }
    ]
    
    # Test search
    import asyncio
    
    async def run_test():
        results = await service.search("something for relaxation", sample_products)
        print(f"Search results: {json.dumps(results, indent=2)}")
    
    asyncio.run(run_test())

if __name__ == "__main__":
    test_search_service()