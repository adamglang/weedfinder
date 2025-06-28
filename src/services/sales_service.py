from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from ..models.sales import SalesBaseline, SalesCurrent
from .base_crud import BaseCRUDService

class SalesBaselineService(BaseCRUDService[SalesBaseline]):
    """Service for managing baseline sales data"""
    
    def __init__(self):
        super().__init__(SalesBaseline)
    
    def clear_store_baseline(self, session: Session, store_id: str) -> None:
        """Clear existing baseline data for a store"""
        session.query(SalesBaseline).filter(
            SalesBaseline.store_id == store_id
        ).delete()
    
    def get_baseline_stats(self, session: Session, store_id: str) -> Dict[str, Any]:
        """Get baseline statistics for a store"""
        stats = session.query(
            func.avg(SalesBaseline.subtotal).label('avg_subtotal'),
            func.count(SalesBaseline.id).label('count')
        ).filter(
            SalesBaseline.store_id == store_id
        ).first()
        
        return {
            'baseline_aov': float(stats.avg_subtotal or 0),
            'baseline_count': stats.count or 0
        }

class SalesCurrentService(BaseCRUDService[SalesCurrent]):
    """Service for managing current sales data"""
    
    def __init__(self):
        super().__init__(SalesCurrent)
    
    def get_current_stats(self, session: Session, store_id: str, days: int = 7) -> Dict[str, Any]:
        """Get current sales statistics for a store"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        stats = session.query(
            func.avg(SalesCurrent.subtotal).label('avg_subtotal'),
            func.count(SalesCurrent.id).label('count')
        ).filter(
            SalesCurrent.store_id == store_id,
            SalesCurrent.closed_at >= cutoff_date
        ).first()
        
        return {
            'current_aov': float(stats.avg_subtotal or 0),
            'current_count': stats.count or 0
        }
    
    def upsert_sale(self, session: Session, sale_data: Dict[str, Any]) -> SalesCurrent:
        """Insert or update a current sale record"""
        existing = session.query(SalesCurrent).filter(
            SalesCurrent.store_id == sale_data['store_id'],
            SalesCurrent.ticket_id == sale_data['ticket_id']
        ).first()
        
        if existing:
            return self.update(session, db_obj=existing, obj_in=sale_data)
        else:
            return self.create(session, obj_in=sale_data)