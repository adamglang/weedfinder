from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
import os
import json
import logging
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our modules (we'll create these)
from src.database import get_db_connection
from src.posabit_adapter import POSaBITAdapter
from src.search_service import SearchService
from src.roi_tracker import ROITracker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="WeedFinder.ai API",
    description="AI-powered cannabis product search and recommendation platform",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class SearchRequest(BaseModel):
    query: str
    store_id: str
    limit: Optional[int] = 3

class SearchResult(BaseModel):
    name: str
    reason: str
    thc: str
    cbd: Optional[str] = None
    price: str
    category: str
    strain_type: Optional[str] = None

class SearchResponse(BaseModel):
    results: List[SearchResult]
    query_time_ms: int
    cached: bool = False

class ROIMetrics(BaseModel):
    baseline_aov: float
    current_aov: float
    lift_abs: float
    lift_pct: float
    weekly_impact: float

# Initialize services
search_service = SearchService()
roi_tracker = ROITracker()

@app.get("/")
async def root():
    return {"message": "WeedFinder.ai API", "version": "0.1.0", "status": "healthy"}

@app.get("/ping")
async def ping():
    return {"pong": "🫡"}

@app.post("/search", response_model=SearchResponse)
async def search_products(request: SearchRequest):
    """
    Search for cannabis products using natural language queries
    """
    try:
        start_time = time.time()
        
        # Get products for the store
        adapter = POSaBITAdapter()
        products = await adapter.fetch_products(request.store_id)
        
        if not products:
            raise HTTPException(status_code=404, detail="No products found for store")
        
        # Perform search
        results = await search_service.search(
            query=request.query,
            products=products,
            limit=request.limit
        )
        
        query_time = int((time.time() - start_time) * 1000)
        
        return SearchResponse(
            results=results,
            query_time_ms=query_time
        )
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail="Search failed")

@app.get("/stores/{store_id}/products")
async def get_store_products(store_id: str):
    """
    Get all products for a specific store
    """
    try:
        adapter = POSaBITAdapter()
        products = await adapter.fetch_products(store_id)
        return {"products": products, "count": len(products)}
    except Exception as e:
        logger.error(f"Error fetching products: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch products")

@app.get("/stores/{store_id}/roi", response_model=ROIMetrics)
async def get_roi_metrics(store_id: str):
    """
    Get ROI metrics for a store
    """
    try:
        metrics = await roi_tracker.calculate_metrics(store_id)
        return metrics
    except Exception as e:
        logger.error(f"Error calculating ROI: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to calculate ROI")

@app.post("/stores/{store_id}/baseline")
async def import_baseline_data(store_id: str, csv_data: dict):
    """
    Import baseline sales data for ROI calculation
    """
    try:
        result = await roi_tracker.import_baseline(store_id, csv_data)
        return {"message": "Baseline data imported successfully", "baseline_aov": result}
    except Exception as e:
        logger.error(f"Error importing baseline: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to import baseline data")

@app.post("/ingest/{store_id}")
async def manual_ingest(store_id: str):
    """
    Manually trigger product ingestion for a store
    """
    try:
        adapter = POSaBITAdapter()
        products = await adapter.fetch_and_store_products(store_id)
        return {"message": f"Ingested {len(products)} products", "store_id": store_id}
    except Exception as e:
        logger.error(f"Ingestion error: {str(e)}")
        raise HTTPException(status_code=500, detail="Ingestion failed")

@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring
    """
    try:
        # Check database connection
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        conn.close()
        
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": time.time()
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
        )

if __name__ == "__main__":
    import uvicorn
    import time
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True if os.getenv("ENVIRONMENT") == "development" else False
    )