# Technical Architecture & Implementation Strategy

## Core Technology Stack

### Backend Architecture
```
┌────────────┐     cron     ┌────────────┐     SQL+vec    ┌────────────┐
│ Fetcher    │ ───────────▶ │  Postgres  │◀────────────── │  FastAPI   │
│ (Python)   │             │ + pgvector │                │  /search   │
└────────────┘             └────────────┘─────────┐       └─────┬──────┘
                                                  │             │
                   GPT-3.5 function-call + rerank │             │
                                                  ▼             ▼
                                              OpenAI API   Next.js UI
```

### Technology Choices & Justification

| Component | Technology | POC Reason | Scale Path |
|-----------|------------|------------|------------|
| **Data Store** | Postgres 15 + pgvector | 1-click install; relational + vector in same DB | Lift & shift to AWS RDS; read-replicas, partitioned tables |
| **Fetcher** | Python script in Docker | cron-driven = no queue infra | Switch to Lambda or Kinesis consumers when >500 stores |
| **API** | FastAPI (uvicorn) | async, type hints, Pydantic models | Same app can be deployed behind ALB & auto-scale |
| **LLM** | OpenAI GPT-3.5 for intent & rerank | $0 infra; function-calling JSON = deterministic | Drop-in Mistral-7B fine-tune on GPU box to cut cost 80% |
| **Cache** | Built-in Redis (£0 in Docker) | store prompt→answer + product-list hash 1h TTL | Move to AWS ElastiCache cluster |
| **Frontend** | Next.js 14/React | Free Vercel hobby tier | Keep; add auth & PWA later |

## Canonical Data Schema

### Core Tables
```sql
CREATE TABLE stores (
    id              UUID PRIMARY KEY,
    name            TEXT,
    pos_type        TEXT,           -- 'posabit', 'cova', 'dutchie'
    api_credentials JSONB,          -- encrypted tokens
    geo_lat         NUMERIC,
    geo_lon         NUMERIC,
    created_at      TIMESTAMPTZ
);

CREATE TABLE strains (
    id              UUID PRIMARY KEY,
    canonical_name  TEXT UNIQUE,    -- 'Blue Dream'
    cultivar        TEXT,           -- normalized name
    strain_type     TEXT,           -- indica/sativa/hybrid
    vector          VECTOR(768),    -- OpenAI ada-002 embedding
    created_at      TIMESTAMPTZ
);

CREATE TABLE strain_effects (
    id              UUID PRIMARY KEY,
    strain_id       UUID REFERENCES strains(id),
    effect          TEXT,           -- 'focus', 'sleep', 'euphoric'
    confidence      NUMERIC,        -- 0-1 from LLM classification
    created_at      TIMESTAMPTZ
);

CREATE TABLE products (
    id              UUID PRIMARY KEY,
    store_id        UUID REFERENCES stores(id),
    strain_id       UUID REFERENCES strains(id),
    sku             TEXT,
    name            TEXT,
    brand           TEXT,
    form_factor     TEXT,           -- flower/vape/edible/etc
    thc_pct         NUMERIC,
    cbd_pct         NUMERIC,
    price           NUMERIC,
    quantity        INTEGER,
    json_raw        JSONB,          -- original POS data
    updated_at      TIMESTAMPTZ,
    
    UNIQUE(store_id, sku)
);

CREATE INDEX idx_products_store_qty ON products(store_id, quantity) WHERE quantity > 0;
CREATE INDEX idx_strains_vector ON strains USING ivfflat (vector vector_cosine_ops);
```

## Search Pipeline Architecture

### 1. Intent Extraction (GPT Function Call)
```python
def extract_intent(user_prompt: str) -> dict:
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo-0125",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
    )
    return json.loads(response.choices[0].message.content)

# Returns: {"effects": ["focus"], "thc": {"lte": 25}, "form": ["flower"], "semantic_query": "focus weed"}
```

### 2. Vector + SQL Search
```sql
WITH candidates AS (
    SELECT p.id, p.name, p.brand, p.thc_pct, p.price
    FROM products p
    JOIN strains s ON p.strain_id = s.id
    WHERE p.store_id = ANY(%(store_ids)s)
      AND p.quantity > 0
      AND (%(thc_lte)s IS NULL OR p.thc_pct <= %(thc_lte)s)
      AND (%(form_filter)s IS NULL OR p.form_factor = ANY(%(form_filter)s))
    ORDER BY s.vector <=> %(query_vector)s
    LIMIT 50
)
SELECT * FROM candidates ORDER BY thc_pct ASC LIMIT 10;
```

### 3. LLM Re-ranking & Explanation
```python
def rerank_with_explanation(candidates: list, user_prompt: str) -> list:
    context = format_candidates_for_llm(candidates)
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo-0125",
        messages=[
            {"role": "system", "content": RERANK_SYSTEM_PROMPT},
            {"role": "user", "content": f"Query: {user_prompt}\n\nCandidates:\n{context}"}
        ]
    )
    return parse_ranked_results(response.choices[0].message.content)
```

## Multi-POS Adapter Pattern

### Adapter Interface
```python
from abc import ABC, abstractmethod
from typing import Iterator
from pydantic import BaseModel

class CanonicalProduct(BaseModel):
    sku: str
    name: str
    brand: str
    strain: str
    form_factor: str
    thc_pct: Optional[float]
    cbd_pct: Optional[float]
    price: float
    quantity: int
    raw_data: dict

class POSAdapter(ABC):
    @abstractmethod
    def fetch_raw_data(self, store_config: dict) -> Iterator[dict]:
        """Fetch raw product data from POS API/feed"""
        pass
    
    @abstractmethod
    def normalize_product(self, raw_item: dict) -> CanonicalProduct:
        """Convert POS-specific format to canonical schema"""
        pass
```

### Example: POSaBIT Adapter
```python
class POSaBITAdapter(POSAdapter):
    def fetch_raw_data(self, store_config: dict) -> Iterator[dict]:
        url = f"https://app.posabit.com/mcx/{store_config['slug']}/venue/{store_config['venue']}/v1/menu_feeds/{store_config['feed_id']}/product_data"
        
        headers = {
            "Authorization": f"Bearer {store_config['api_token']}",
            "merchantToken": store_config['merchant_token']
        }
        
        response = requests.get(url, headers=headers)
        data = response.json()
        
        for item in data.get('product_data', {}).get('menu_items', []):
            yield item
    
    def normalize_product(self, raw_item: dict) -> CanonicalProduct:
        return CanonicalProduct(
            sku=raw_item['id'],
            name=raw_item['product_name'],
            brand=raw_item.get('brand', ''),
            strain=raw_item.get('strain', ''),
            form_factor=raw_item.get('category', ''),
            thc_pct=raw_item.get('potency_thc'),
            cbd_pct=raw_item.get('potency_cbd'),
            price=raw_item['variants'][0]['price'] if raw_item.get('variants') else 0,
            quantity=raw_item['variants'][0]['quantity'] if raw_item.get('variants') else 0,
            raw_data=raw_item
        )
```

## Caching Strategy

### Multi-Layer Cache Design
```python
# Layer 1: Intent JSON (after function-call)
intent_key = sha256(canonical_json_string)
cached_intent = redis.get(f"intent:{intent_key}")

# Layer 2: Vector search result IDs  
search_key = sha256(intent_key + store_ids_hash + menu_fingerprint)
cached_candidates = redis.get(f"search:{search_key}")

# Layer 3: LLM re-rank answer
answer_key = search_key  # same key as search results
cached_answer = redis.get(f"answer:{answer_key}")

# Layer 4: Product feed JSON
feed_key = f"feed:{store_id}:{feed_timestamp}"
cached_feed = redis.get(feed_key)
```

### Cache Invalidation
- **Intent cache**: 24h TTL (user language patterns stable)
- **Search cache**: 10min TTL or until menu fingerprint changes
- **Answer cache**: Same as search cache
- **Feed cache**: 5-10min TTL based on POS update frequency

## Deployment Architecture

### POC Deployment (Fly.io + Vercel)
```yaml
# fly.toml
app = "weedfinder-api"
primary_region = "sea"

[build]
  dockerfile = "Dockerfile"

[[services]]
  internal_port = 8080
  protocol = "tcp"

  [[services.ports]]
    port = 80
    handlers = ["http"]
  
  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

[[jobs]]
  name = "ingest-feeds"
  schedule = "*/10 * * * *"
  command = "python ingest.py"
```

### Production Migration Path (AWS)
```yaml
# docker-compose.yml for local dev
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8080:8080"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/weedfinder
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis

  db:
    image: pgvector/pgvector:pg15
    environment:
      - POSTGRES_DB=weedfinder
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

## Performance Targets

| Metric | POC Target | Production Target |
|--------|------------|-------------------|
| **Search Latency (p95)** | < 1s | < 500ms |
| **Intent Extraction** | 60-120ms | 50-80ms |
| **Vector Search** | 10-20ms | 5-10ms |
| **LLM Re-rank** | 150-300ms | 100-200ms |
| **Cache Hit Rate** | 30-40% | 70-80% |
| **Concurrent Users** | 10 | 1000+ |
| **Stores Supported** | 1 | 500+ |

## Security & Compliance

### Data Protection
- **PII Handling**: No customer PII stored; only anonymized search queries
- **API Security**: JWT tokens, rate limiting, CORS policies
- **POS Credentials**: Encrypted at rest using Fernet (Python) or AWS KMS
- **HTTPS Everywhere**: TLS 1.3 for all API endpoints and widget delivery

### Cannabis Compliance
- **Age Gating**: Widget includes age verification prompt
- **State Regulations**: Configurable disclaimers per state
- **Marketing Compliance**: No medical claims in search results
- **Data Retention**: Configurable retention periods per jurisdiction

### Monitoring & Observability
```python
# Key metrics to track
METRICS = {
    'search_requests_total': Counter('search_requests_total', ['store_id', 'status']),
    'search_latency': Histogram('search_latency_seconds', ['component']),
    'cache_hits': Counter('cache_hits_total', ['cache_layer']),
    'pos_sync_errors': Counter('pos_sync_errors_total', ['pos_type', 'error_type']),
    'revenue_attributed': Gauge('revenue_attributed_dollars', ['store_id'])
}
```

## Scalability Considerations

### Database Scaling
- **Read Replicas**: For search queries when > 100 stores
- **Partitioning**: Products table by store_id when > 1M products
- **Vector Index Tuning**: HNSW for better performance at scale

### API Scaling  
- **Horizontal Scaling**: Stateless FastAPI containers behind load balancer
- **Queue System**: Celery + Redis for background tasks when > 500 stores
- **CDN**: CloudFront for widget delivery and static assets

### Cost Optimization
- **LLM Migration**: Move to local Mistral-7B when token costs > $300/month
- **Caching**: Aggressive caching to reduce API calls by 70-80%
- **Spot Instances**: Use spot pricing for non-critical background jobs

---

*This architecture supports the full evolution from POC to acquisition-ready platform while maintaining simplicity and cost-effectiveness at each stage.*