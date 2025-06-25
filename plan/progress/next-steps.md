# Next Steps - WeedFinder.ai Development
**Date:** June 25, 2025  
**Priority:** High - Critical Issues & Quality Improvements

## 🎯 **Immediate Action Items**

### 1. **Human Code Review and Refactor for Quality and Maintainability**

#### **Current State Analysis**
- Codebase has ~2000+ lines across 15+ files
- Good separation of concerns with dedicated services
- Some areas need improvement for production readiness

#### **Refactoring Plan**

##### **A. Error Handling & Logging Improvements**
- **File:** [`src/posabit_adapter.py`](../src/posabit_adapter.py:95)
  - Add structured error handling in `normalize_product()`
  - Implement retry logic for API calls
  - Add detailed logging for debugging

- **File:** [`src/search_service.py`](../src/search_service.py:132)
  - Improve error handling in GPT API calls
  - Add timeout handling for OpenAI requests
  - Better fallback mechanisms

##### **B. Configuration Management**
- **Action:** Create [`src/config.py`](../src/config.py) for centralized configuration
- **Benefits:** Environment-specific settings, validation, type safety
- **Implementation:**
  ```python
  from pydantic import BaseSettings
  
  class Settings(BaseSettings):
      openai_api_key: str
      posabit_api_token: str
      database_url: str
      redis_url: str = "redis://localhost:6379"
      
      class Config:
          env_file = ".env"
  ```

##### **C. Type Safety & Validation**
- **Action:** Add comprehensive type hints and Pydantic models
- **Files to update:** All service classes
- **Benefits:** Better IDE support, runtime validation, documentation

##### **D. Code Organization**
- **Action:** Split large files into smaller, focused modules
- **Target:** [`src/posabit_adapter.py`](../src/posabit_adapter.py) (205 lines) → separate normalization logic
- **Create:** `src/adapters/` directory for POS system adapters

---

### 2. **Fix Critical Data Issues**

#### **A. THC Data Missing Issue**

**Problem:** All products show `THC: None%` because POSaBIT API fields aren't mapped correctly

**Root Cause Analysis:**
- Current mapping: [`src/posabit_adapter.py:55`](../src/posabit_adapter.py:55) uses `potency_thc`
- Need to investigate actual POSaBIT API field names

**Implementation Plan:**
1. **Debug POSaBIT API Structure**
   ```bash
   # Create debug script
   python debug_thc_fields.py
   ```
   
2. **Update Field Mapping**
   - **File:** [`src/posabit_adapter.py:55-56`](../src/posabit_adapter.py:55-56)
   - **Investigate fields:** `thc_percentage`, `thc_content`, `potency`, `cannabinoids`
   - **Add fallback logic** for multiple possible field names

3. **Test Data Extraction**
   ```python
   # Add to normalize_product()
   def _extract_thc_data(self, raw_product: Dict) -> Optional[float]:
       """Extract THC data from various possible fields"""
       thc_fields = ['thc_percentage', 'potency_thc', 'thc_content', 'thc']
       for field in thc_fields:
           if field in raw_product and raw_product[field] is not None:
               return self._safe_float(raw_product[field])
       
       # Check in variants or nested structures
       variants = raw_product.get('variants', [])
       if variants:
           for variant in variants:
               for field in thc_fields:
                   if field in variant and variant[field] is not None:
                       return self._safe_float(variant[field])
       return None
   ```

#### **B. Category Mapping Wrong Issue**

**Problem:** All products show `Type: other` instead of proper categories like "flower"

**Root Cause Analysis:**
- Current logic: [`src/posabit_adapter.py:62-76`](../src/posabit_adapter.py:62-76)
- Uses `category` field but mapping may be incomplete

**Implementation Plan:**
1. **Analyze POSaBIT Categories**
   ```python
   # Create category analysis script
   def analyze_categories(raw_data):
       categories = {}
       for item in raw_data['product_data']['menu_items']:
           cat = item.get('category', 'unknown')
           categories[cat] = categories.get(cat, 0) + 1
       return categories
   ```

2. **Improve Category Mapping**
   - **File:** [`src/posabit_adapter.py:61-76`](../src/posabit_adapter.py:61-76)
   - **Add comprehensive mapping:**
   ```python
   def _map_category_to_form_factor(self, category: str, name: str = "") -> str:
       """Enhanced category mapping with fallbacks"""
       category_lower = category.lower()
       name_lower = name.lower()
       
       # Flower products
       if any(term in category_lower for term in ['flower', 'bud', 'indoor', 'outdoor', 'greenhouse']):
           return 'flower'
       
       # Vape products  
       if any(term in category_lower for term in ['vape', 'cartridge', 'cart', 'pen']):
           return 'vape'
           
       # Edibles
       if any(term in category_lower for term in ['edible', 'gummy', 'chocolate', 'cookie', 'candy']):
           return 'edible'
           
       # Pre-rolls
       if any(term in category_lower for term in ['pre-roll', 'joint', 'blunt', 'preroll']):
           return 'pre_roll'
           
       # Concentrates
       if any(term in category_lower for term in ['concentrate', 'wax', 'shatter', 'rosin', 'hash']):
           return 'concentrate'
           
       # Check product name as fallback
       if any(term in name_lower for term in ['flower', 'bud']):
           return 'flower'
           
       return 'other'
   ```

#### **C. AI Hallucination Issue**

**Problem:** When null results are given, AI hallucinates products instead of throwing error

**Root Cause Analysis:**
- Current logic: [`src/search_service.py:98-135`](../src/search_service.py:98-135)
- No validation that recommended products exist in the input list

**Implementation Plan:**
1. **Add Product Validation**
   ```python
   def _validate_gpt_results(self, results: List[Dict], available_products: List[Dict]) -> List[Dict]:
       """Validate that GPT results match actual products"""
       available_names = {p.get('name', '').lower() for p in available_products}
       validated_results = []
       
       for result in results:
           result_name = result.get('name', '').lower()
           if result_name in available_names:
               validated_results.append(result)
           else:
               logger.warning(f"GPT hallucinated product: {result.get('name')}")
       
       return validated_results
   ```

2. **Improve GPT Prompt**
   - **File:** [`src/search_service.py:105-117`](../src/search_service.py:105-117)
   - **Add stricter constraints:**
   ```python
   prompt = f"""You are WeedFinder.ai, a cannabis product recommendation assistant.

   User Query: {query}

   Available Products (ONLY recommend from this list):
   {products_context}

   CRITICAL RULES:
   1. ONLY recommend products from the numbered list above
   2. Copy product names EXACTLY as shown (including numbers)
   3. If no products match the query, return {{"results": [], "message": "No matching products found"}}
   4. Do NOT create, modify, or invent product names
   5. Maximum {limit} recommendations

   Return JSON format:
   {{"results": [{{"name": "EXACT name from list", "reason": "why it matches", ...}}]}}
   """
   ```

3. **Add Empty Results Handling**
   ```python
   # In search_with_gpt_passthrough()
   if not products:
       return {"results": [], "message": "No products available for search"}
   
   validated_results = self._validate_gpt_results(result.get('results', []), products)
   if not validated_results and result.get('results'):
       logger.error(f"All GPT results were hallucinated for query: {query}")
       return self._fallback_keyword_search(query, products, limit)
   ```

---

### 3. **Cannabis Query Validation**

**Problem:** Need to fail calls that are not about cannabis

**Implementation Plan:**

#### **A. Create Query Classifier**
- **File:** Create [`src/query_classifier.py`](../src/query_classifier.py)
```python
import openai
from typing import Dict, bool

class QueryClassifier:
    """Classify if queries are cannabis-related"""
    
    def __init__(self):
        self.openai_client = openai.OpenAI()
    
    async def is_cannabis_related(self, query: str) -> Dict[str, any]:
        """Check if query is cannabis-related"""
        prompt = f"""
        Analyze this query to determine if it's related to cannabis/marijuana products:
        
        Query: "{query}"
        
        Cannabis-related topics include:
        - Cannabis strains, products, effects
        - THC, CBD, terpenes
        - Smoking, vaping, edibles
        - Medical marijuana
        - Dispensary products
        
        Non-cannabis topics include:
        - Other drugs, alcohol, tobacco
        - General shopping queries
        - Unrelated products/services
        
        Return JSON: {{"is_cannabis_related": true/false, "confidence": 0.0-1.0, "reason": "explanation"}}
        """
        
        response = await self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        return json.loads(response.choices[0].message.content)
```

#### **B. Integrate into Search Endpoint**
- **File:** [`app.py:80-111`](../app.py:80-111)
```python
from src.query_classifier import QueryClassifier

query_classifier = QueryClassifier()

@app.post("/search", response_model=SearchResponse)
async def search_products(request: SearchRequest):
    try:
        # Validate cannabis-related query
        classification = await query_classifier.is_cannabis_related(request.query)
        
        if not classification.get('is_cannabis_related', False):
            raise HTTPException(
                status_code=400, 
                detail={
                    "error": "Non-cannabis query detected",
                    "message": "This service only handles cannabis-related searches",
                    "reason": classification.get('reason', ''),
                    "confidence": classification.get('confidence', 0)
                }
            )
        
        # Continue with existing search logic...
```

---

### 4. **Implement Vector Search**

**Problem:** Currently dumping entire store inventory instead of using proper search

**Implementation Plan:**

#### **A. Product Embedding Generation**
- **File:** Create [`src/embedding_service.py`](../src/embedding_service.py)
```python
import openai
import numpy as np
from typing import List, Dict
from .database import update_product_embedding

class EmbeddingService:
    """Generate and manage product embeddings"""
    
    def __init__(self):
        self.openai_client = openai.OpenAI()
    
    def create_product_text(self, product: Dict) -> str:
        """Create searchable text representation of product"""
        parts = [
            product.get('name', ''),
            product.get('brand', ''),
            product.get('strain', ''),
            product.get('category', ''),
            product.get('form_factor', ''),
            product.get('description', ''),
            f"THC: {product.get('thc_pct', 0)}%",
            f"CBD: {product.get('cbd_pct', 0)}%"
        ]
        return " ".join(filter(None, parts))
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        response = await self.openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    
    async def embed_product(self, product: Dict) -> List[float]:
        """Generate embedding for a product"""
        product_text = self.create_product_text(product)
        return await self.generate_embedding(product_text)
```

#### **B. Database Schema Updates**
- **File:** [`src/database.py`](../src/database.py)
```python
def update_product_embedding(product_id: int, embedding: List[float]):
    """Update product embedding in database"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE products SET embedding = %s WHERE id = %s",
                (embedding, product_id)
            )
        conn.commit()
    finally:
        conn.close()

def vector_search_products(store_id: int, query_embedding: List[float], limit: int = 10) -> List[Dict]:
    """Search products using vector similarity"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, sku, name, brand, category, form_factor, 
                       thc_pct, cbd_pct, price, strain,
                       1 - (embedding <=> %s) as similarity
                FROM products 
                WHERE store_id = %s AND embedding IS NOT NULL
                ORDER BY similarity DESC
                LIMIT %s
            """, (query_embedding, store_id, limit))
            
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
    finally:
        conn.close()
```

#### **C. Update Search Service**
- **File:** [`src/search_service.py`](../src/search_service.py)
```python
from .embedding_service import EmbeddingService
from .database import vector_search_products

class SearchService:
    def __init__(self):
        # ... existing init ...
        self.embedding_service = EmbeddingService()
    
    async def vector_search(self, query: str, store_id: int, limit: int = 10) -> List[Dict]:
        """Perform vector-based search"""
        # Generate query embedding
        query_embedding = await self.embedding_service.generate_embedding(query)
        
        # Search similar products
        similar_products = vector_search_products(store_id, query_embedding, limit * 3)
        
        # Use GPT to rank and explain results
        if similar_products:
            return await self.search_with_gpt_passthrough(query, similar_products, limit)
        
        return []
```

---

### 5. **Remote Deployment**

**Implementation Plan:**

#### **A. Initial Deployment - Fly.io (Immediate)**
- **Platform:** Fly.io for fast, simple deployment
- **Database:** Fly.io Postgres with pgvector extension
- **Cache:** Fly.io Redis
- **Benefits:** Quick setup, cost-effective for POC/MVP stage

#### **B. Frontend Deployment - Vercel**
- **Platform:** Vercel for static web widget hosting
- **Benefits:** CDN, automatic deployments, great for React/Next.js
- **Integration:** API calls to Fly.io backend

#### **C. Fly.io Configuration**
- **File:** Create [`fly.toml`](../fly.toml)
```toml
app = "weedfinder-api"
primary_region = "sea"

[build]
  dockerfile = "Dockerfile"

[env]
  PORT = "8000"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true

[[services]]
  protocol = "tcp"
  internal_port = 8000
  processes = ["app"]

  [[services.ports]]
    port = 80
    handlers = ["http"]
    force_https = true

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

[deploy]
  release_command = "python init_db.py"
```

#### **D. Vercel Configuration**
- **File:** Create [`vercel.json`](../weedfinder-client/vercel.json)
```json
{
  "builds": [
    {
      "src": "index.html",
      "use": "@vercel/static"
    }
  ],
  "routes": [
    {
      "src": "/api/(.*)",
      "dest": "https://weedfinder-api.fly.dev/$1"
    }
  ]
}
```

#### **E. Deployment Commands**
```bash
# Deploy backend to Fly.io
fly launch --no-deploy
fly secrets set OPENAI_API_KEY=xxx POSABIT_API_TOKEN=xxx
fly deploy

# Deploy frontend to Vercel
cd weedfinder-client
vercel --prod
```

#### **F. Future AWS Migration Plan**
- **Timeline:** After reaching 10+ dispensary customers
- **Platform:** AWS ECS with Fargate for better enterprise features
- **Database:** AWS RDS PostgreSQL with pgvector
- **Benefits:** Better compliance, enterprise SLAs, advanced monitoring

---

### 6. **Automated Testing**

**Implementation Plan:**

#### **A. Unit Testing Framework**
- **File:** Create [`tests/unit/`](../tests/unit/) directory
- **Framework:** pytest with async support
- **Coverage:** pytest-cov for coverage reporting

#### **B. Integration Testing**
- **File:** Create [`tests/integration/`](../tests/integration/) directory
- **Database:** Test database with Docker
- **API Testing:** FastAPI TestClient

#### **C. End-to-End Testing**
- **File:** Create [`tests/e2e/`](../tests/e2e/) directory
- **Browser Testing:** Playwright for web widget testing
- **API Testing:** Full workflow tests

#### **D. Test Configuration**
```python
# tests/conftest.py
import pytest
import asyncio
from fastapi.testclient import TestClient
from app import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
```

---

## 📋 **Implementation Timeline**

### **Week 1 (June 25-July 1)**
- [ ] **Day 1-2:** Fix THC/CBD data mapping and category classification
- [ ] **Day 3-4:** Implement cannabis query validation and AI hallucination fixes
- [ ] **Day 5-7:** Code refactoring and quality improvements

### **Week 2 (July 2-8)**
- [ ] **Day 1-3:** Implement vector search and embedding generation
- [ ] **Day 4-5:** Set up automated testing framework
- [ ] **Day 6-7:** Prepare deployment infrastructure

### **Week 3 (July 9-15)**
- [ ] **Day 1-3:** Deploy to production environment
- [ ] **Day 4-5:** Performance testing and optimization
- [ ] **Day 6-7:** Documentation and monitoring setup

---

## 🎯 **Success Metrics**

### **Quality Metrics**
- [ ] **Code Coverage:** >80% test coverage
- [ ] **Type Safety:** 100% type hints on public APIs
- [ ] **Error Rate:** <1% API error rate
- [ ] **Response Time:** <2s average search response

### **Data Quality Metrics**
- [ ] **THC Data:** >90% products have THC data
- [ ] **Category Accuracy:** >95% correct category mapping
- [ ] **Search Relevance:** >90% user satisfaction (manual testing)

### **System Metrics**
- [ ] **Uptime:** 99.9% availability
- [ ] **Scalability:** Handle 1000+ concurrent searches
- [ ] **Cost:** <$0.05 per search (including infrastructure)

---

## 🚨 **Risk Mitigation**

### **Technical Risks**
1. **POSaBIT API Changes:** Implement robust field mapping with fallbacks
2. **OpenAI Rate Limits:** Add request queuing and retry logic
3. **Database Performance:** Implement connection pooling and query optimization

### **Business Risks**
1. **Data Quality Issues:** Comprehensive validation and monitoring
2. **Search Accuracy:** A/B testing and continuous improvement
3. **Scalability Concerns:** Load testing and performance monitoring

---

## 💡 **Future Enhancements**

### **Short Term (Month 2)**
- Multi-POS system support (Cova, Dutchie, Flowhub)
- Advanced filtering and sorting options
- Real-time inventory updates

### **Medium Term (Months 3-6)**
- Machine learning recommendation engine
- Personalized search results
- Analytics dashboard for dispensaries

### **Long Term (6+ Months)**
- Mobile app development
- Voice search capabilities
- Predictive inventory management

---

**Next Review Date:** July 1, 2025  
**Responsible:** Development Team  
**Priority:** Critical Path Items First