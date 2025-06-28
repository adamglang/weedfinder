from typing import Optional
from sqlalchemy.orm import Session
from datetime import date
from ..models.store_metrics import StoreMetrics
from .base_crud import BaseCRUDService

class StoreMetricsService(BaseCRUDService[StoreMetrics]):
    """Service for managing store metrics"""
    
    def __init__(self):
        super().__init__(StoreMetrics)
    
    def upsert_daily_metrics(
        self,
        session: Session,
        store_id: str,
        metrics_date: date,
        baseline_aov: float,
        current_aov: float,
        lift_abs: float,
        lift_pct: float
    ) -> StoreMetrics:
        """Insert or update daily metrics for a store"""
        existing = session.query(StoreMetrics).filter(
            StoreMetrics.store_id == store_id,
            StoreMetrics.date == metrics_date
        ).first()
        
        metrics_data = {
            'store_id': store_id,
            'date': metrics_date,
            'baseline_aov': baseline_aov,
            'current_aov': current_aov,
            'lift_abs': lift_abs,
            'lift_pct': lift_pct
        }
        
        if existing:
            return self.update(session, db_obj=existing, obj_in=metrics_data)
        else:
            return self.create(session, obj_in=metrics_data)
    
    def get_latest_metrics(self, session: Session, store_id: str) -> Optional[StoreMetrics]:
        """Get the latest metrics for a store"""
        return session.query(StoreMetrics).filter(
            StoreMetrics.store_id == store_id
        ).order_by(StoreMetrics.date.desc()).first()
    
    def get_metrics_history(
        self,
        session: Session,
        store_id: str,
        days: int = 30
    ) -> list[StoreMetrics]:
        """Get metrics history for a store"""
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.utcnow().date() - timedelta(days=days)
        
        return session.query(StoreMetrics).filter(
            StoreMetrics.store_id == store_id,
            StoreMetrics.date >= cutoff_date
        ).order_by(StoreMetrics.date.desc()).all()