"""Store service with custom business logic"""
from typing import Optional, List
from sqlalchemy.orm import Session
from .base_crud import BaseCRUDService
from ..models.store import Store
from ..models.enums import POSSystem

class StoreService(BaseCRUDService[Store]):
    """Store service with custom methods"""
    
    def __init__(self):
        super().__init__(Store)
    
    def get_by_slug(self, db: Session, slug: str) -> Optional[Store]:
        """Get store by slug"""
        return self.find_by(db, slug=slug)
    
    def get_by_pos_type(self, db: Session, pos_type: POSSystem) -> List[Store]:
        """Get all stores using a specific POS system"""
        return self.find_all_by(db, pos_type=pos_type)
    
    def get_stores_in_radius(
        self, 
        db: Session, 
        lat: float, 
        lon: float, 
        radius_km: float = 10.0
    ) -> List[Store]:
        """Get stores within a radius (simplified - would use PostGIS in production)"""
        # For now, just return all stores with geo coordinates
        # In production, you'd use ST_DWithin with PostGIS
        return db.query(Store).filter(
            Store.geo_lat.isnot(None),
            Store.geo_lon.isnot(None)
        ).all()
    
    def create_store(
        self, 
        db: Session, 
        name: str, 
        slug: str, 
        pos_type: POSSystem = POSSystem.POSABIT,
        pos_config: dict = None,
        geo_lat: float = None,
        geo_lon: float = None
    ) -> Store:
        """Create a new store with validation"""
        # Check if slug already exists
        existing = self.get_by_slug(db, slug)
        if existing:
            raise ValueError(f"Store with slug '{slug}' already exists")
        
        store_data = {
            "name": name,
            "slug": slug,
            "pos_type": pos_type,
            "pos_config": pos_config or {},
            "geo_lat": geo_lat,
            "geo_lon": geo_lon
        }
        
        return self.create(db, obj_in=store_data)

# Create singleton instance
store_service = StoreService()