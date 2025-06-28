"""Product service with custom business logic"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_
from .base_crud import BaseCRUDService
from ..models.product import Product
from ..models.enums import ProductFamily

class ProductService(BaseCRUDService[Product]):
    """Product service with custom methods"""
    
    def __init__(self):
        super().__init__(Product)
    
    def get_by_store_and_sku(self, db: Session, store_id: UUID, sku: str) -> Optional[Product]:
        """Get product by store and SKU"""
        return self.find_by(db, store_id=store_id, sku=sku)
    
    def get_products_by_store(self, db: Session, store_id: UUID, in_stock_only: bool = True) -> List[Product]:
        """Get all products for a store"""
        filters = {"store_id": store_id}
        if in_stock_only:
            # We'll need to handle this in the query since it's not a simple equality
            query = db.query(Product).filter(
                and_(
                    Product.store_id == store_id,
                    Product.quantity > 0
                )
            )
            return query.all()
        else:
            return self.find_all_by(db, **filters)
    
    def get_products_by_family(self, db: Session, product_family: ProductFamily) -> List[Product]:
        """Get products by product family"""
        return self.find_all_by(db, product_family=product_family)
    
    def search_products(
        self,
        db: Session,
        store_ids: List[UUID] = None,
        product_family: ProductFamily = None,
        min_thc: float = None,
        max_thc: float = None,
        min_cbd: float = None,
        max_cbd: float = None,
        in_stock_only: bool = True,
        limit: int = 50
    ) -> List[Product]:
        """Advanced product search with multiple filters"""
        query = db.query(Product)
        
        # Build filter conditions
        conditions = []
        
        if store_ids:
            conditions.append(Product.store_id.in_(store_ids))
        
        if product_family:
            conditions.append(Product.product_family == product_family)
        
        if min_thc is not None:
            conditions.append(Product.thc_pct >= min_thc)
        
        if max_thc is not None:
            conditions.append(Product.thc_pct <= max_thc)
        
        if min_cbd is not None:
            conditions.append(Product.cbd_pct >= min_cbd)
        
        if max_cbd is not None:
            conditions.append(Product.cbd_pct <= max_cbd)
        
        if in_stock_only:
            conditions.append(Product.quantity > 0)
        
        if conditions:
            query = query.filter(and_(*conditions))
        
        return query.limit(limit).all()
    
    def upsert_product(
        self,
        db: Session,
        store_id: UUID,
        product_data: Dict[str, Any]
    ) -> Product:
        """Insert or update product based on store_id and sku"""
        product_data["store_id"] = store_id
        return self.upsert(
            db,
            obj_in=product_data,
            unique_fields=["store_id", "sku"]
        )
    
    def get_low_stock_products(
        self,
        db: Session,
        store_id: UUID = None,
        threshold: int = 5
    ) -> List[Product]:
        """Get products with low stock"""
        query = db.query(Product).filter(
            and_(
                Product.quantity <= threshold,
                Product.quantity > 0
            )
        )
        
        if store_id:
            query = query.filter(Product.store_id == store_id)
        
        return query.all()
    
    def get_products_by_strain(self, db: Session, strain_id: UUID) -> List[Product]:
        """Get all products for a specific strain"""
        return self.find_all_by(db, strain_id=strain_id)

# Create singleton instance
product_service = ProductService()