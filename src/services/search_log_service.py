from typing import Dict, Any
from sqlalchemy.orm import Session
from ..models.search_log import SearchLog
from .base_crud import BaseCRUDService

class SearchLogService(BaseCRUDService[SearchLog]):
    """Service for managing search logs"""
    
    def __init__(self):
        super().__init__(SearchLog)
    
    def log_search(
        self,
        session: Session,
        store_id: str,
        query: str,
        filters: Dict[str, Any],
        result_count: int,
        response_time_ms: int,
        cached: bool = False
    ) -> SearchLog:
        """Log a search query"""
        search_log_data = {
            'store_id': store_id,
            'query': query,
            'intent_json': filters,
            'results_count': result_count,
            'response_time_ms': response_time_ms,
            'cached': cached
        }
        
        return self.create(session, obj_in=search_log_data)
    
    def get_search_analytics(
        self,
        session: Session,
        store_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get search analytics for a store"""
        from sqlalchemy import func
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get basic stats
        stats = session.query(
            func.count(SearchLog.id).label('total_searches'),
            func.avg(SearchLog.response_time_ms).label('avg_response_time'),
            func.avg(SearchLog.result_count).label('avg_results'),
            func.sum(func.case([(SearchLog.cached == True, 1)], else_=0)).label('cached_searches')
        ).filter(
            SearchLog.store_id == store_id,
            SearchLog.created_at >= cutoff_date
        ).first()
        
        # Get top queries
        top_queries = session.query(
            SearchLog.query,
            func.count(SearchLog.id).label('count')
        ).filter(
            SearchLog.store_id == store_id,
            SearchLog.created_at >= cutoff_date
        ).group_by(SearchLog.query).order_by(
            func.count(SearchLog.id).desc()
        ).limit(10).all()
        
        return {
            'total_searches': stats.total_searches or 0,
            'avg_response_time': round(stats.avg_response_time or 0, 2),
            'avg_results': round(stats.avg_results or 0, 2),
            'cached_searches': stats.cached_searches or 0,
            'cache_hit_rate': round((stats.cached_searches or 0) / max(stats.total_searches or 1, 1) * 100, 2),
            'top_queries': [{'query': q.query, 'count': q.count} for q in top_queries]
        }