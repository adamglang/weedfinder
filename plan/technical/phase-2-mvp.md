# Phase 2: MVP Development (Months 2-6)
*Multi-Store Platform with Automated Onboarding*

## Objectives

**Primary Goal**: Scale from 1 store to 25+ stores with automated systems
- Build canonical data schema supporting multiple POS systems
- Implement pgvector for improved search quality and cost reduction
- Create self-service onboarding flow
- Establish sustainable unit economics ($1.2k MRR target)
- Lay foundation for budtender copilot development

**Success Metrics**:
- 25+ paying stores across 2-3 POS systems
- $1,200+ MRR with 70%+ gross margin
- Search latency < 500ms (p95)
- Customer acquisition cost < $200 per store
- Churn rate < 5% monthly

## Month 2: Canonical Schema & Vector Search

### Database Migration
```sql
-- Migration: POC to Production Schema
-- File: migrations/001_canonical_schema.sql

-- Stores table
CREATE TABLE stores (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    slug            TEXT UNIQUE NOT NULL,
    pos_type        TEXT NOT NULL, -- 'posabit', 'cova', 'dutchie'
    api_credentials JSONB,          -- encrypted credentials
    geo_lat         NUMERIC,
    geo_lon         NUMERIC,
    subscription_id TEXT,           -- Stripe subscription ID
    status          TEXT DEFAULT 'active',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Strains master table (deduplicated across stores)
CREATE TABLE strains (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name  TEXT UNIQUE NOT NULL,
    strain_type     TEXT,           -- indica/sativa/hybrid/cbd
    vector          VECTOR(768),    -- OpenAI text-embedding-3-small
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Strain effects (many-to-many)
CREATE TABLE strain_effects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strain_id       UUID REFERENCES strains(id) ON DELETE CASCADE,
    effect          TEXT NOT NULL,  -- 'focus', 'sleep', 'euphoric'
    confidence      NUMERIC DEFAULT 1.0,
    source          TEXT DEFAULT 'llm_classified',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(strain_id, effect)
);

-- Products (store-specific inventory)
CREATE TABLE products (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id        UUID REFERENCES stores(id) ON DELETE CASCADE,
    strain_id       UUID REFERENCES strains(id),
    sku             TEXT NOT NULL,
    name            TEXT NOT NULL,
    brand           TEXT,
    form_factor     TEXT,           -- flower/vape/edible/concentrate/topical
    thc_pct         NUMERIC,
    cbd_pct         NUMERIC,
    price           NUMERIC,
    quantity        INTEGER DEFAULT 0,
    json_raw        JSONB,          -- original POS data for debugging
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(store_id, sku)
);

-- Search analytics
CREATE TABLE search_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id        UUID REFERENCES stores(id),
    query_text      TEXT,
    intent_json     JSONB,          -- extracted intent
    results_count   INTEGER,
    clicked_sku     TEXT,           -- if user clicked a result
    session_id      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_products_store_active ON products(store_id, updated_at) WHERE quantity > 0;
CREATE INDEX idx_strains_vector ON strains USING ivfflat (vector vector_cosine_ops