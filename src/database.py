import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector
import json
import os
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

def get_db_connection():
    """Get a database connection"""
    try:
        conn = psycopg2.connect(
            os.getenv("DATABASE_URL"),
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        register_vector(conn)
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

@contextmanager
def get_db_cursor():
    """Context manager for database operations"""
    conn = None
    try:
        conn = get_db_connection()
        yield conn.cursor()
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database operation failed: {e}")
        raise
    finally:
        if conn:
            conn.close()

def init_database():
    """Initialize database schema"""
    schema_sql = """
    -- Enable pgvector extension
    CREATE EXTENSION IF NOT EXISTS vector;
    
    -- Stores table
    CREATE TABLE IF NOT EXISTS stores (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(255) NOT NULL,
        slug VARCHAR(100) UNIQUE NOT NULL,
        pos_type VARCHAR(50) NOT NULL DEFAULT 'posabit',
        pos_config JSONB,
        geo_lat DECIMAL(10, 8),
        geo_lon DECIMAL(11, 8),
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    
    -- Strains table (canonical strain data)
    CREATE TABLE IF NOT EXISTS strains (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        canonical_name VARCHAR(255) NOT NULL UNIQUE,
        cultivar VARCHAR(255),
        strain_type VARCHAR(50), -- indica, sativa, hybrid, cbd_dominant
        lineage TEXT,
        vector VECTOR(768), -- OpenAI embedding dimension
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    
    -- Strain effects (many-to-many)
    CREATE TABLE IF NOT EXISTS strain_effects (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        strain_id UUID REFERENCES strains(id) ON DELETE CASCADE,
        effect VARCHAR(100) NOT NULL,
        confidence DECIMAL(3,2) DEFAULT 1.0,
        created_at TIMESTAMP DEFAULT NOW()
    );
    
    -- Products table (store inventory)
    CREATE TABLE IF NOT EXISTS products (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        store_id UUID REFERENCES stores(id) ON DELETE CASCADE,
        strain_id UUID REFERENCES strains(id),
        sku VARCHAR(255),
        name VARCHAR(255) NOT NULL,
        brand VARCHAR(255),
        form_factor VARCHAR(100), -- flower, vape, edible, tincture, topical
        thc_pct DECIMAL(5,2),
        cbd_pct DECIMAL(5,2),
        price DECIMAL(10,2),
        quantity INTEGER DEFAULT 0,
        json_raw JSONB, -- original POS data
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(store_id, sku)
    );
    
    -- Search logs for analytics
    CREATE TABLE IF NOT EXISTS search_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        store_id UUID REFERENCES stores(id),
        query TEXT NOT NULL,
        intent_json JSONB,
        results_count INTEGER,
        response_time_ms INTEGER,
        cached BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT NOW()
    );
    
    -- Sales data for ROI tracking
    CREATE TABLE IF NOT EXISTS sales_baseline (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        store_id UUID REFERENCES stores(id),
        ticket_id VARCHAR(255),
        subtotal DECIMAL(10,2),
        closed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT NOW()
    );
    
    CREATE TABLE IF NOT EXISTS sales_current (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        store_id UUID REFERENCES stores(id),
        ticket_id VARCHAR(255),
        subtotal DECIMAL(10,2),
        item_notes TEXT, -- for tracking WF_UPSELL tags
        closed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT NOW()
    );
    
    -- Store metrics for ROI calculation
    CREATE TABLE IF NOT EXISTS store_metrics (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        store_id UUID REFERENCES stores(id),
        date DATE NOT NULL,
        baseline_aov DECIMAL(10,2),
        current_aov DECIMAL(10,2),
        lift_abs DECIMAL(10,2),
        lift_pct DECIMAL(5,2),
        searches_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(store_id, date)
    );
    
    -- Indexes for performance
    CREATE INDEX IF NOT EXISTS idx_strains_vector ON strains USING ivfflat (vector vector_cosine_ops) WITH (lists = 100);
    CREATE INDEX IF NOT EXISTS idx_products_store_id ON products(store_id);
    CREATE INDEX IF NOT EXISTS idx_products_strain_id ON products(strain_id);
    CREATE INDEX IF NOT EXISTS idx_search_logs_store_created ON search_logs(store_id, created_at);
    CREATE INDEX IF NOT EXISTS idx_sales_baseline_store_closed ON sales_baseline(store_id, closed_at);
    CREATE INDEX IF NOT EXISTS idx_sales_current_store_closed ON sales_current(store_id, closed_at);
    CREATE INDEX IF NOT EXISTS idx_store_metrics_store_date ON store_metrics(store_id, date);
    """
    
    with get_db_cursor() as cur:
        cur.execute(schema_sql)
        logger.info("Database schema initialized successfully")

def insert_store(name: str, slug: str, pos_type: str = "posabit", pos_config: Dict = None) -> str:
    """Insert a new store and return its ID"""
    with get_db_cursor() as cur:
        cur.execute("""
            INSERT INTO stores (name, slug, pos_type, pos_config)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (name, slug, pos_type, json.dumps(pos_config or {})))
        
        return str(cur.fetchone()['id'])

def get_store_by_slug(slug: str) -> Optional[Dict]:
    """Get store by slug"""
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM stores WHERE slug = %s", (slug,))
        result = cur.fetchone()
        return dict(result) if result else None

def upsert_strain(canonical_name: str, strain_type: str = None, effects: list = None) -> str:
    """Insert or update a strain and return its ID"""
    with get_db_cursor() as cur:
        # Check if strain exists
        cur.execute("SELECT id FROM strains WHERE canonical_name = %s", (canonical_name,))
        existing = cur.fetchone()
        
        if existing:
            strain_id = str(existing['id'])
        else:
            # Insert new strain
            cur.execute("""
                INSERT INTO strains (canonical_name, strain_type)
                VALUES (%s, %s)
                RETURNING id
            """, (canonical_name, strain_type))
            strain_id = str(cur.fetchone()['id'])
        
        # Insert effects if provided
        if effects:
            for effect in effects:
                cur.execute("""
                    INSERT INTO strain_effects (strain_id, effect)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                """, (strain_id, effect))
        
        return strain_id

def upsert_product(store_id: str, product_data: Dict) -> str:
    """Insert or update a product"""
    with get_db_cursor() as cur:
        cur.execute("""
            INSERT INTO products (
                store_id, sku, name, brand, form_factor, 
                thc_pct, cbd_pct, price, quantity, json_raw
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (store_id, sku) 
            DO UPDATE SET
                name = EXCLUDED.name,
                brand = EXCLUDED.brand,
                form_factor = EXCLUDED.form_factor,
                thc_pct = EXCLUDED.thc_pct,
                cbd_pct = EXCLUDED.cbd_pct,
                price = EXCLUDED.price,
                quantity = EXCLUDED.quantity,
                json_raw = EXCLUDED.json_raw,
                updated_at = NOW()
            RETURNING id
        """, (
            store_id,
            product_data.get('sku'),
            product_data.get('name'),
            product_data.get('brand'),
            product_data.get('form_factor'),
            product_data.get('thc_pct'),
            product_data.get('cbd_pct'),
            product_data.get('price'),
            product_data.get('quantity', 0),
            product_data
        ))
        
        return str(cur.fetchone()['id'])

def log_search(store_id: str, query: str, intent_json: Dict, results_count: int, response_time_ms: int, cached: bool = False):
    """Log a search query for analytics"""
    with get_db_cursor() as cur:
        cur.execute("""
            INSERT INTO search_logs (store_id, query, intent_json, results_count, response_time_ms, cached)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (store_id, query, intent_json, results_count, response_time_ms, cached))

if __name__ == "__main__":
    # Initialize database when run directly
    init_database()
    print("Database initialized successfully!")